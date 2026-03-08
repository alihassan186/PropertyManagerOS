"""
app.py — Flask application entry point for PropertyOS
All 10 routes + /api/simulate + /api/autopilot/trace-stream
Run: python app.py  →  http://localhost:5000
"""

import json
import os
import queue
import random
import time

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import autopilot
import database
import comms_engine
import auto_resolve
from ai_engine import generate_reply, stream_triage, triage_request

app = Flask(__name__)

# Initialise DB on startup
database.init_db()
database.init_comms_tables()


# ─── Comms priority helpers ──────────────────────────────────────────────────────

_COMMS_PRIORITY_LEVELS = ("critical", "important", "medium", "low")


def _to_comms_priority_level(urgency: str | None) -> str:
    value = (urgency or "").strip().lower()
    if value == "critical":
        return "critical"
    if value == "high":
        return "important"
    if value == "medium":
        return "medium"
    # Treat low/info/unknown as low in the 4-level model.
    return "low"


def _attach_priority_level(record: dict) -> dict:
    enriched = dict(record)
    enriched["priority_level"] = _to_comms_priority_level(record.get("urgency"))
    return enriched


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


@app.route("/manager-legacy")
def manager_legacy():
    """Legacy manager dashboard (backup)."""
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


# ─── Comms Intelligence Routes ──────────────────────────────────────────────────

@app.route("/api/comms")
def api_get_comms():
    """Return comms issues, optionally filtered by 4-level priority."""
    priority = (request.args.get("priority") or "").strip().lower()
    comms = [_attach_priority_level(c) for c in database.get_all_communications()]

    if priority and priority != "all":
        if priority not in _COMMS_PRIORITY_LEVELS:
            return jsonify({"error": "priority must be one of: critical, important, medium, low, all"}), 400
        comms = [c for c in comms if c.get("priority_level") == priority]

    return jsonify(comms), 200


@app.route("/api/comms/categorized")
def api_get_comms_categorized():
    """Return comms issues grouped into critical/important/medium/low."""
    include_items = (request.args.get("include_items") or "true").strip().lower() != "false"
    comms = [_attach_priority_level(c) for c in database.get_all_communications()]

    buckets = {level: [] for level in _COMMS_PRIORITY_LEVELS}
    for item in comms:
        buckets[item["priority_level"]].append(item)

    counts = {level: len(items) for level, items in buckets.items()}
    payload = {"counts": counts}
    if include_items:
        payload["issues"] = buckets
    return jsonify(payload), 200


@app.route("/api/comms/threads")
def api_comms_threads():
    """Return all threads sorted by urgency score."""
    threads = database.get_all_threads()
    return jsonify(threads), 200


@app.route("/api/comms/analytics")
def api_comms_analytics():
    """Aggregated comms stats."""
    analytics = database.get_comms_analytics()
    by_priority = analytics.get("by_priority", {})
    analytics["critical"] = by_priority.get("critical", analytics.get("critical", 0))
    analytics["important"] = by_priority.get("important", analytics.get("high", 0))
    analytics["medium"] = by_priority.get("medium", analytics.get("by_urgency", {}).get("medium", 0))
    analytics["low"] = by_priority.get("low", analytics.get("by_urgency", {}).get("low", 0))
    return jsonify(analytics), 200


@app.route("/api/comms/actions")
def api_get_comms_actions():
    """Return all action items sorted by urgency."""
    return jsonify(database.get_all_action_items()), 200


@app.route("/api/comms/actions/<int:action_id>/status", methods=["PATCH"])
def api_update_action_status(action_id):
    """Update an action item status (open / done / snoozed)."""
    data = request.get_json(force=True, silent=True) or {}
    status = (data.get("status") or "").strip()
    if status not in {"open", "done", "snoozed"}:
        return jsonify({"error": "status must be open, done, or snoozed"}), 400
    item = database.update_action_item_status(action_id, status)
    if not item:
        return jsonify({"error": "Not found"}), 404
    return jsonify(item), 200


@app.route("/api/comms/<string:email_id>/reply", methods=["POST"])
def api_comms_reply(email_id):
    """Generate a draft reply for an email (FAQ template first, AI fallback)."""
    comm = database.get_communication_by_email_id(email_id)
    if not comm:
        return jsonify({"error": "Not found"}), 404

    import json as _json
    flags = _json.loads(comm.get("flags") or "[]")
    analysis = {
        "urgency": comm.get("urgency"),
        "urgency_score": comm.get("urgency_score", 0),
        "ai_summary": comm.get("ai_summary"),
        "recommended_action": comm.get("recommended_action"),
        "flags": flags,
    }
    email_data = {
        "subject": comm.get("subject"),
        "body": comm.get("body"),
        "from": {
            "name": comm.get("from_name"),
            "email": comm.get("from_email"),
            "type": comm.get("from_type"),
            "unit": comm.get("from_unit"),
            "property_id": comm.get("from_property_id"),
        }
    }

    # Attempt deterministic FAQ auto-reply before using AI.
    thread_rows = database.get_thread_emails(comm.get("thread_id") or "") or [comm]
    thread_text = "\n\n".join(
        f"From: {row.get('from_name', '')}\nSubject: {row.get('subject', '')}\n{row.get('body', '')}"
        for row in thread_rows
    )
    thread_bundle = {
        "subject": comm.get("subject", ""),
        "thread_text": thread_text,
        "latest_sender_name": comm.get("from_name", ""),
        "property_manager": "Property Manager",
        "property_name": comm.get("from_property_id", "") or "your property",
    }
    auto_decision = auto_resolve.evaluate_auto_resolve(
        thread_bundle=thread_bundle,
        templates=auto_resolve.load_templates(),
    )
    if auto_decision.get("is_auto"):
        return jsonify(
            {
                "reply": auto_decision.get("draft_reply", ""),
                "mode": "template",
                "template_id": auto_decision.get("template_id"),
                "handling_reason": auto_decision.get("handling_reason", ""),
                "strong_signal_present": auto_decision.get("strong_signal_present", False),
            }
        ), 200

    try:
        reply = comms_engine.draft_reply(email_data, analysis)
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    return jsonify(
        {
            "reply": reply,
            "mode": "ai",
            "template_id": auto_decision.get("template_id"),
            "handling_reason": auto_decision.get("handling_reason", ""),
            "strong_signal_present": auto_decision.get("strong_signal_present", False),
        }
    ), 200


@app.route("/api/comms/<string:email_id>/stream-analysis")
def api_comms_stream_analysis(email_id):
    """SSE endpoint — streams live AI analysis of a single email."""
    comm = database.get_communication_by_email_id(email_id)
    if not comm:
        return jsonify({"error": "Not found"}), 404

    email_data = {
        "id": comm.get("email_id"),
        "subject": comm.get("subject"),
        "body": comm.get("body"),
        "timestamp": comm.get("timestamp"),
        "from": {
            "name": comm.get("from_name"),
            "email": comm.get("from_email"),
            "type": comm.get("from_type"),
            "unit": comm.get("from_unit"),
            "property_id": comm.get("from_property_id"),
        }
    }

    def generate():
        try:
            for token in comms_engine.stream_analysis(email_data):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/comms/priority-board")
def api_comms_priority_board():
    """Return top 10 critical/important emails plus all open actions."""
    all_comms = [_attach_priority_level(c) for c in database.get_all_communications()]
    priority = [c for c in all_comms if c.get("priority_level") in ("critical", "important")][:10]
    actions = database.get_all_action_items()
    analytics = database.get_comms_analytics()
    return jsonify({
        "priority_emails": priority,
        "open_actions": [a for a in actions if a.get("status") == "open"],
        "analytics": analytics,
    }), 200


@app.route("/api/comms/thread/<string:thread_id>")
def api_get_thread_emails(thread_id):
    """Return all emails in a specific thread."""
    emails = database.get_thread_emails(thread_id)
    return jsonify(emails), 200


# ─── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=debug_mode, host=host, port=port, threaded=True)
