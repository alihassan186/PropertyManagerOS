"""
app.py — Flask application entry point for PropertyOS
All 10 routes + /api/simulate + /api/autopilot/trace-stream
Run: python app.py  →  http://localhost:5000
"""

import json
import queue
import random
import time

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import autopilot
import database
from ai_engine import generate_reply, stream_triage, triage_request

app = Flask(__name__)

# Initialise DB on startup
database.init_db()


# ─── Demo simulator messages ────────────────────────────────────────────────────

SIMULATOR_MESSAGES = [
    {"message": "The shower in my bathroom has no hot water. Cold only since yesterday.", "apt": "Apt 2C"},
    {"message": "There's a strong smell of gas near the cooker. I'm scared to use it.", "apt": "Apt 8A"},
    {"message": "My living room window won't close properly. Cold draft coming in all night.", "apt": "Apt 3D"},
    {"message": "The electricity in my bedroom keeps tripping. Already reset 3 times today.", "apt": "Apt 5F"},
    {"message": "Washing machine is leaking water onto the kitchen floor when it spins.", "apt": "Apt 1B"},
    {"message": "There is a large crack appearing in the bedroom wall. Got bigger this week.", "apt": "Apt 6C"},
    {"message": "Saw a rat in the kitchen last night. Very worried. Have young children.", "apt": "Apt 4A"},
    {"message": "The intercom / door buzzer isn't working. Can't let anyone into the building.", "apt": "Apt 7E"},
    {"message": "Ceiling light in the hallway flickering non-stop for 3 days now.", "apt": "Apt 9B"},
    {"message": "Hay una gotera en el techo del salón cuando llueve. (Spanish — ceiling leak when it rains.)", "apt": "Apt 2F"},
    {"message": "Der Heizkörper im Schlafzimmer wird nicht warm. Es ist sehr kalt. (German — radiator cold.)", "apt": "Apt 3A"},
    {"message": "The bathroom extractor fan is broken and there is mould appearing on the ceiling.", "apt": "Apt 10C"},
    {"message": "Front door lock is stiff and sometimes won't open at all. Security concern.", "apt": "Apt 5B"},
    {"message": "Boiler pressure keeps dropping. I have to re-pressurise it every day.", "apt": "Apt 8D"},
    {"message": "Kitchen tap dripping constantly. Gets worse every day.", "apt": "Apt 1E"},
]


# ─── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def tenant_portal():
    """Tenant-facing request submission portal."""
    return render_template("tenant.html")


@app.route("/manager")
def manager_dashboard():
    """Property manager operations dashboard."""
    return render_template("manager.html")


@app.route("/api/triage", methods=["POST"])
def api_triage():
    """
    AI triage + save to DB.
    Body: { "message": str, "apartment_ref": str (optional) }
    Returns 201 + full request JSON.
    """
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    apt = (data.get("apartment_ref") or "").strip() or None

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        result = triage_request(message, apt)
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    record = database.create_request(
        tenant_message=message,
        urgency=result["urgency"],
        category=result["category"],
        contractor_brief=result["contractor_brief"],
        tenant_advice=result["tenant_advice"],
        response_time=result["response_time"],
        language_detected=result.get("language_detected"),
        apartment_ref=apt,
    )
    return jsonify(record), 201


@app.route("/api/stream")
def api_stream():
    """
    SSE endpoint — streams triage tokens word by word.
    Query params: message=..., apartment_ref=... (optional)
    """
    message = (request.args.get("message") or "").strip()
    apt = (request.args.get("apartment_ref") or "").strip() or None

    if not message:
        return jsonify({"error": "message query param required"}), 400

    def generate():
        try:
            for token in stream_triage(message, apt):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/requests", methods=["GET"])
def api_get_requests():
    """Return all requests, newest first."""
    return jsonify(database.get_all_requests()), 200


@app.route("/api/requests/<int:request_id>", methods=["GET"])
def api_get_request(request_id):
    """Return a single request by ID."""
    record = database.get_request_by_id(request_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    return jsonify(record), 200


@app.route("/api/requests/<int:request_id>/reply", methods=["POST"])
def api_generate_reply(request_id):
    """Generate + store AI tenant reply for an existing request."""
    record = database.get_request_by_id(request_id)
    if not record:
        return jsonify({"error": "Not found"}), 404

    try:
        reply = generate_reply(record["tenant_message"], record)
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    database.update_reply(request_id, reply)
    return jsonify({"reply": reply}), 200


@app.route("/api/requests/<int:request_id>/status", methods=["PATCH"])
def api_update_status(request_id):
    """Update request status (New / In Progress / Resolved)."""
    data = request.get_json(force=True, silent=True) or {}
    status = (data.get("status") or "").strip()

    if status not in {"New", "In Progress", "Resolved"}:
        return jsonify({"error": "status must be New, In Progress, or Resolved"}), 400

    record = database.update_status(request_id, status)
    if not record:
        return jsonify({"error": "Not found"}), 404
    return jsonify(record), 200


@app.route("/api/analytics")
def api_analytics():
    """Aggregated stats for dashboard charts."""
    return jsonify(database.get_analytics()), 200


@app.route("/api/autopilot/start", methods=["POST"])
def api_autopilot_start():
    """Start AutoPilot background thread."""
    autopilot.start()
    return jsonify({"running": True}), 200


@app.route("/api/autopilot/stop", methods=["POST"])
def api_autopilot_stop():
    """Stop AutoPilot."""
    autopilot.stop()
    return jsonify({"running": False}), 200


@app.route("/api/autopilot/trace-stream")
def api_autopilot_trace_stream():
    """
    SSE stream of AutoPilot trace entries.
    First sends all existing trace, then streams new ones live.
    """
    listener_q = queue.Queue()
    autopilot.register_listener(listener_q)

    # Seed with existing trace
    existing = autopilot.get_trace()

    def generate():
        try:
            # Send history
            for entry in existing:
                yield f"data: {json.dumps(entry)}\n\n"

            # Stream new entries
            while True:
                try:
                    entry = listener_q.get(timeout=20)
                    yield f"data: {json.dumps(entry)}\n\n"
                    # If AutoPilot just stopped and queue is empty, end stream
                    if not autopilot.is_running() and listener_q.empty():
                        time.sleep(0.5)
                        if listener_q.empty():
                            break
                except queue.Empty:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
                    if not autopilot.is_running():
                        break
        finally:
            autopilot.unregister_listener(listener_q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Add one random request from the simulator list."""
    choice = random.choice(SIMULATOR_MESSAGES)
    message = choice["message"]
    apt = choice["apt"]

    try:
        result = triage_request(message, apt)
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    record = database.create_request(
        tenant_message=message,
        urgency=result["urgency"],
        category=result["category"],
        contractor_brief=result["contractor_brief"],
        tenant_advice=result["tenant_advice"],
        response_time=result["response_time"],
        language_detected=result.get("language_detected"),
        apartment_ref=apt,
    )
    return jsonify(record), 201


# ─── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
