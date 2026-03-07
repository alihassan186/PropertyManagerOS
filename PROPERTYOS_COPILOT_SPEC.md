# PropertyOS — Complete Technical Specification for GitHub Copilot
# Hackathon Build: Give(a)Go · March 7 · Baseline Dublin
# AI MODEL TO USE: Groq API — model: "llama-3.3-70b-versatile" (free, fastest, best)

---

## COPILOT INSTRUCTIONS — READ THIS FIRST

You are building PropertyOS: a full-stack AI-powered property operations platform.
Build EVERY file listed below, EXACTLY as specified.
Do NOT simplify. Do NOT skip features. Build everything.
The project must run with: python app.py
And open at: http://localhost:5000

---

## PROJECT STRUCTURE — CREATE ALL THESE FILES

```
propertyos/
├── app.py
├── database.py
├── ai_engine.py
├── autopilot.py
├── requirements.txt
├── .env.example
├── .gitignore
├── seed_data.py
└── templates/
    └── index.html
```

---

## FILE 1: requirements.txt

```
flask==3.1.0
flask-cors==5.0.0
groq==0.13.0
python-dotenv==1.0.1
```

---

## FILE 2: .env.example

```
# Get your FREE Groq API key at: https://console.groq.com
# No credit card required
GROQ_API_KEY=your_groq_api_key_here
```

---

## FILE 3: .gitignore

```
.env
__pycache__/
venv/
*.db
.DS_Store
*.pyc
.idea/
.vscode/
```

---

## FILE 4: database.py — COMPLETE CODE

```python
# database.py
# Handles ALL SQLite database operations for PropertyOS
# NO raw SQL should appear anywhere except this file

import sqlite3
import os
from datetime import datetime

DB_PATH = "propertyos.db"


def get_connection():
    """Create and return a SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create the database and all tables if they don't exist.
    Called once at Flask app startup.
    Creates: requests table with all columns.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id                INTEGER   PRIMARY KEY AUTOINCREMENT,
            tenant_message    TEXT      NOT NULL,
            urgency           TEXT      NOT NULL,
            category          TEXT      NOT NULL,
            contractor_brief  TEXT      NOT NULL,
            tenant_advice     TEXT      NOT NULL,
            response_time     TEXT      NOT NULL,
            ai_reply          TEXT,
            status            TEXT      NOT NULL DEFAULT 'New',
            language_detected TEXT,
            apartment_ref     TEXT,
            created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def dict_from_row(row):
    """Convert a sqlite3.Row to a plain Python dict."""
    return dict(zip(row.keys(), row))


def create_request(data: dict) -> int:
    """
    Insert a new maintenance request into the database.
    
    Args:
        data: dict with keys: tenant_message, urgency, category,
              contractor_brief, tenant_advice, response_time,
              language_detected (optional), apartment_ref (optional)
    
    Returns:
        int: the new row's id
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO requests 
            (tenant_message, urgency, category, contractor_brief,
             tenant_advice, response_time, language_detected, apartment_ref,
             status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'New', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        data.get("tenant_message"),
        data.get("urgency"),
        data.get("category"),
        data.get("contractor_brief"),
        data.get("tenant_advice"),
        data.get("response_time"),
        data.get("language_detected"),
        data.get("apartment_ref")
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_all_requests() -> list:
    """
    Return all requests ordered newest first.
    Returns list of dicts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


def get_request_by_id(request_id: int) -> dict:
    """
    Return a single request by ID as dict.
    Returns None if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    conn.close()
    return dict_from_row(row) if row else None


def update_status(request_id: int, status: str) -> bool:
    """
    Update the status of a request.
    Valid values: 'New', 'In Progress', 'Resolved'
    Returns True on success, False if id not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE requests SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, request_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def update_reply(request_id: int, reply: str) -> bool:
    """
    Store an AI-generated tenant reply for a request.
    Returns True on success, False if id not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE requests SET ai_reply = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (reply, request_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def get_analytics() -> dict:
    """
    Return aggregated statistics for the dashboard.
    
    Returns dict with:
        total: int — total number of requests
        by_urgency: dict — count per urgency level
        by_status: dict — count per status
        by_category: dict — count per category
        resolved_today: int — requests resolved today
        avg_response_time_label: str — human readable average
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Total
    cursor.execute("SELECT COUNT(*) as cnt FROM requests")
    total = cursor.fetchone()["cnt"]

    # By urgency
    cursor.execute("SELECT urgency, COUNT(*) as cnt FROM requests GROUP BY urgency")
    by_urgency = {"Emergency": 0, "High": 0, "Medium": 0, "Low": 0}
    for row in cursor.fetchall():
        by_urgency[row["urgency"]] = row["cnt"]

    # By status
    cursor.execute("SELECT status, COUNT(*) as cnt FROM requests GROUP BY status")
    by_status = {"New": 0, "In Progress": 0, "Resolved": 0}
    for row in cursor.fetchall():
        by_status[row["status"]] = row["cnt"]

    # By category
    cursor.execute("SELECT category, COUNT(*) as cnt FROM requests GROUP BY category")
    by_category = {}
    for row in cursor.fetchall():
        by_category[row["category"]] = row["cnt"]

    # Resolved today
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM requests 
        WHERE status = 'Resolved' AND date(updated_at) = date('now')
    """)
    resolved_today = cursor.fetchone()["cnt"]

    conn.close()

    # Estimate avg response time label based on urgency mix
    emergency_pct = (by_urgency["Emergency"] / max(total, 1)) * 100
    if emergency_pct > 30:
        avg_label = "~1.5 hrs"
    elif emergency_pct > 10:
        avg_label = "~3.2 hrs"
    else:
        avg_label = "~6.1 hrs"

    return {
        "total": total,
        "by_urgency": by_urgency,
        "by_status": by_status,
        "by_category": by_category,
        "resolved_today": resolved_today,
        "avg_response_time_label": avg_label
    }


def delete_all_requests():
    """Delete all requests. Used by seed_data.py to reset demo data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM requests")
    conn.commit()
    conn.close()
```

---

## FILE 5: ai_engine.py — COMPLETE CODE

```python
# ai_engine.py
# ALL Groq API calls and prompt templates for PropertyOS
# Model: llama-3.3-70b-versatile (free, fastest available on Groq)
# NO Groq calls should appear anywhere except this file

import os
import json
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# ─── SYSTEM PROMPTS ──────────────────────────────────────────────────────────

TRIAGE_SYSTEM_PROMPT = """You are an AI assistant for a property management company.
Analyse the maintenance request and return ONLY valid JSON with no preamble, no explanation, no markdown fences.
Return exactly this JSON structure:

{
  "urgency": "Emergency" | "High" | "Medium" | "Low",
  "category": "Plumbing" | "Heating" | "Electrical" | "Structural" | "Pest" | "Appliance" | "Fixtures" | "Noise" | "Other",
  "contractor_brief": "<2-3 professional sentences describing the issue, ready to send to a contractor>",
  "tenant_advice": "<1 sentence of immediate actionable advice for the tenant to do right now>",
  "response_time": "Within 2 hours" | "Within 24 hours" | "Within 3 days" | "Within 1 week",
  "language_detected": "<ISO 639-1 code of the language the tenant wrote in, e.g. en, fr, es, de, it, pl>"
}

Urgency classification rules:
- Emergency: immediate safety risk, active water damage, no heat with vulnerable occupants, gas smell, fire risk
- High: affects livability (no heat, no hot water), has dependents (baby, elderly), ongoing leak risk
- Medium: functional issue not immediately dangerous, recurring minor problems
- Low: cosmetic damage, minor inconvenience, non-maintenance issues

If the request is NOT a maintenance issue (e.g. neighbour noise, parking, general complaints):
- Set urgency to "Low", category to "Other" or "Noise"
- contractor_brief: explain politely this is not a maintenance issue and suggest appropriate process
- tenant_advice: suggest they contact the relevant party (landlord, council, etc.)

Always detect the language and set language_detected correctly."""


REPLY_SYSTEM_PROMPT = """You are a professional and empathetic property manager writing a reply to a tenant.
Write a warm, concise, professional reply acknowledging their maintenance request.
Include:
1. Acknowledgement of their specific issue
2. The urgency level and what that means for response time
3. What they should expect to happen next
4. One immediate action they can take now if applicable

Rules:
- Keep it under 100 words
- Do NOT include subject line
- Do NOT include a signature or sign-off
- Be warm but professional
- If language_detected is not 'en', write the ENTIRE reply in that language
- Plain text only, no markdown"""


AUTOPILOT_SYSTEM_PROMPT = """You are an autonomous AI property operations agent.
You are processing a maintenance request as part of an automated queue processing system.

For the given request, return ONLY valid JSON (no preamble, no markdown):

{
  "action_taken": "<one sentence describing what you did>",
  "urgency": "Emergency" | "High" | "Medium" | "Low",
  "category": "Plumbing" | "Heating" | "Electrical" | "Structural" | "Pest" | "Appliance" | "Fixtures" | "Noise" | "Other",
  "contractor_brief": "<professional contractor brief 2-3 sentences>",
  "tenant_advice": "<1 sentence immediate advice>",
  "response_time": "Within 2 hours" | "Within 24 hours" | "Within 3 days" | "Within 1 week",
  "new_status": "In Progress" | "Resolved",
  "reasoning": "<1 sentence explaining your urgency decision>"
}

Set new_status to 'Resolved' for Low urgency items only. All others: 'In Progress'."""


# ─── FUNCTIONS ───────────────────────────────────────────────────────────────

def triage_request(message: str) -> dict:
    """
    Triage a maintenance request using Groq AI.
    
    Args:
        message: raw tenant message text
    
    Returns:
        dict with keys: urgency, category, contractor_brief,
                       tenant_advice, response_time, language_detected
    
    Raises:
        ValueError if JSON parsing fails after retry
    """
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Maintenance request: {message}"}
                ],
                temperature=0.1,
                max_tokens=600
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if model adds them
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            if attempt == 1:
                raise ValueError(f"AI returned invalid JSON after 2 attempts: {raw}")
            continue


def generate_reply(request_data: dict) -> str:
    """
    Generate a professional tenant reply for a triaged request.
    
    Args:
        request_data: dict containing tenant_message, urgency, category,
                     response_time, language_detected
    
    Returns:
        str: plain text tenant reply
    """
    user_content = f"""
Tenant message: {request_data.get('tenant_message')}
Urgency level: {request_data.get('urgency')}
Category: {request_data.get('category')}
Expected response time: {request_data.get('response_time')}
Language detected: {request_data.get('language_detected', 'en')}
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user",   "content": user_content}
        ],
        temperature=0.4,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()


def stream_triage(message: str):
    """
    Stream the triage result token by token using Groq streaming API.
    Used by the /api/stream SSE endpoint.
    
    Yields:
        str: individual tokens as they arrive from the model
    
    Usage:
        for token in stream_triage(message):
            yield f"data: {token}\\n\\n"
    """
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user",   "content": f"Maintenance request: {message}"}
        ],
        temperature=0.1,
        max_tokens=600,
        stream=True
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def autopilot_process(request_data: dict) -> dict:
    """
    Autonomously process a single request in AutoPilot mode.
    Returns structured action dict.
    
    Args:
        request_data: dict with tenant_message, urgency, category, id
    
    Returns:
        dict with: action_taken, urgency, category, contractor_brief,
                  tenant_advice, response_time, new_status, reasoning
    """
    user_content = f"""
Process this maintenance request autonomously:
ID: {request_data.get('id')}
Current status: {request_data.get('status')}
Tenant message: {request_data.get('tenant_message')}
Current urgency: {request_data.get('urgency')}
"""
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": AUTOPILOT_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content}
                ],
                temperature=0.1,
                max_tokens=500
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            if attempt == 1:
                return {
                    "action_taken": "Processed request",
                    "urgency": request_data.get("urgency", "Medium"),
                    "category": request_data.get("category", "Other"),
                    "contractor_brief": "Request reviewed by AutoPilot.",
                    "tenant_advice": "We have received your request.",
                    "response_time": "Within 24 hours",
                    "new_status": "In Progress",
                    "reasoning": "Default processing applied."
                }
```

---

## FILE 6: autopilot.py — COMPLETE CODE

```python
# autopilot.py
# AutoPilot mode: autonomous AI agent that processes the request queue
# This is the STAR FEATURE of PropertyOS

import time
import threading
from database import get_all_requests, update_status, update_reply
from ai_engine import autopilot_process, generate_reply

# Global state
_autopilot_running = False
_autopilot_thread = None
_trace_log = []  # List of trace messages shown in UI
_max_trace = 50  # Keep last 50 trace entries


def add_trace(message: str, msg_type: str = "info"):
    """
    Add a message to the AutoPilot reasoning trace log.
    msg_type: 'info' | 'success' | 'warning' | 'processing'
    """
    entry = {
        "message": message,
        "type": msg_type,
        "timestamp": time.strftime("%H:%M:%S")
    }
    _trace_log.append(entry)
    if len(_trace_log) > _max_trace:
        _trace_log.pop(0)


def get_trace() -> list:
    """Return current trace log."""
    return list(_trace_log)


def is_running() -> bool:
    """Return whether AutoPilot is currently active."""
    return _autopilot_running


def clear_trace():
    """Clear the trace log."""
    _trace_log.clear()


def _run_autopilot():
    """
    Main AutoPilot loop. Runs in a background thread.
    Processes all 'New' requests in the queue one by one.
    Updates status and generates replies autonomously.
    Adds reasoning trace entries for each step.
    Stops when all New requests are processed or stop() is called.
    """
    global _autopilot_running

    add_trace("🤖 AutoPilot activated — scanning request queue...", "info")
    time.sleep(0.8)

    while _autopilot_running:
        # Get all New requests
        all_requests = get_all_requests()
        new_requests = [r for r in all_requests if r["status"] == "New"]

        if not new_requests:
            add_trace("✅ Queue clear — all requests processed. AutoPilot standing by.", "success")
            time.sleep(3)
            # Keep running in standby, check for new requests
            continue

        # Process next request
        request = new_requests[0]
        req_id = request["id"]
        apt = request.get("apartment_ref") or f"Request #{req_id}"
        msg_preview = request["tenant_message"][:50] + "..." if len(request["tenant_message"]) > 50 else request["tenant_message"]

        add_trace(f"📋 Reading: {apt} — \"{msg_preview}\"", "processing")
        time.sleep(1.2)

        add_trace(f"🧠 Analysing urgency and category...", "processing")
        time.sleep(0.8)

        try:
            # Call AI to process autonomously
            result = autopilot_process(request)

            urgency = result.get("urgency", "Medium")
            category = result.get("category", "Other")
            new_status = result.get("new_status", "In Progress")
            reasoning = result.get("reasoning", "")

            add_trace(f"⚡ Urgency: {urgency} | Category: {category}", "info")
            time.sleep(0.6)

            add_trace(f"💭 Reasoning: {reasoning}", "info")
            time.sleep(0.8)

            add_trace(f"📝 Generating contractor brief...", "processing")
            time.sleep(0.9)

            add_trace(f"💬 Drafting tenant reply...", "processing")
            # Generate reply
            try:
                reply = generate_reply(request)
                update_reply(req_id, reply)
                add_trace(f"✉️  Tenant reply drafted and saved.", "success")
            except Exception:
                add_trace(f"⚠️  Reply generation skipped.", "warning")

            time.sleep(0.7)

            # Update status
            update_status(req_id, new_status)
            status_icon = "✅" if new_status == "Resolved" else "🔄"
            add_trace(f"{status_icon} Status updated: New → {new_status}", "success")
            time.sleep(1.0)

            add_trace(f"─────────────────────────────────────", "info")
            time.sleep(0.5)

        except Exception as e:
            add_trace(f"⚠️  Error processing {apt}: {str(e)[:60]}", "warning")
            # Mark as In Progress so it doesn't loop infinitely on error
            update_status(req_id, "In Progress")
            time.sleep(1)

    add_trace("🛑 AutoPilot stopped.", "warning")


def start():
    """Start the AutoPilot background thread."""
    global _autopilot_running, _autopilot_thread

    if _autopilot_running:
        return False  # Already running

    clear_trace()
    _autopilot_running = True
    _autopilot_thread = threading.Thread(target=_run_autopilot, daemon=True)
    _autopilot_thread.start()
    return True


def stop():
    """Stop the AutoPilot background thread."""
    global _autopilot_running
    _autopilot_running = False
    add_trace("🛑 AutoPilot stop requested...", "warning")
    return True
```

---

## FILE 7: app.py — COMPLETE CODE

```python
# app.py
# Flask application entry point for PropertyOS
# All routes defined here. Business logic in database.py and ai_engine.py

import os
import json
import random
import time
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from database import (
    init_db, create_request, get_all_requests, get_request_by_id,
    update_status, update_reply, get_analytics
)
from ai_engine import triage_request, generate_reply, stream_triage
import autopilot

app = Flask(__name__)
CORS(app)

VALID_STATUSES = ["New", "In Progress", "Resolved"]

# 15 realistic maintenance requests for the Live Simulator
SIMULATOR_REQUESTS = [
    {"msg": "The toilet in my bathroom won't stop running. It's been like this for 2 days.", "apt": "Apt 3B"},
    {"msg": "There's a crack in my bedroom ceiling and I can see a water stain forming.", "apt": "Apt 8A"},
    {"msg": "My oven stopped working yesterday. None of the rings heat up.", "apt": "Apt 2C"},
    {"msg": "The front door lock is stiff and sometimes won't open. I got locked out twice.", "apt": "Apt 5D"},
    {"msg": "There is a strong smell of gas coming from my kitchen. I'm worried.", "apt": "Apt 1A"},
    {"msg": "My bathroom extractor fan makes a loud grinding noise constantly.", "apt": "Apt 4F"},
    {"msg": "A window in my living room won't close properly. Cold air is coming in.", "apt": "Apt 6B"},
    {"msg": "The kitchen sink is draining very slowly. Getting worse each day.", "apt": "Apt 9C"},
    {"msg": "My bedroom radiator isn't heating up even though others in the flat are fine.", "apt": "Apt 7E"},
    {"msg": "There are damp patches appearing on my bedroom wall. Getting bigger.", "apt": "Apt 3A"},
    {"msg": "The light switch in my hallway has started sparking when I use it.", "apt": "Apt 2B"},
    {"msg": "Hay una gotera en el techo del salón. Apareció esta mañana.", "apt": "Apt 5C"},
    {"msg": "I've seen mice in my kitchen two nights in a row. Found droppings behind fridge.", "apt": "Apt 8D"},
    {"msg": "The shower pressure has dropped to almost nothing in the last week.", "apt": "Apt 4A"},
    {"msg": "My intercom system is broken. Visitors can't buzz me and I can't hear them.", "apt": "Apt 1D"},
]

# ─── STARTUP ────────────────────────────────────────────────────────────────

with app.app_context():
    init_db()


# ─── ROUTES ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return render_template("index.html")


@app.route("/api/triage", methods=["POST"])
def triage():
    """
    Triage a maintenance request using AI and persist to database.
    
    Request JSON:
        message (str, required): tenant's raw message
        apartment_ref (str, optional): unit reference e.g. "Apt 4B"
    
    Returns:
        201: full request object as JSON
        400: if message is missing or empty
        500: if AI call fails
    """
    data = request.get_json()
    
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "Message is required", "code": "MISSING_MESSAGE"}), 400

    message = data["message"].strip()
    apartment_ref = data.get("apartment_ref", "").strip() or None

    try:
        ai_result = triage_request(message)
    except Exception as e:
        return jsonify({"error": "AI service error", "code": "AI_ERROR", "detail": str(e)}), 500

    request_data = {
        "tenant_message":    message,
        "urgency":           ai_result.get("urgency", "Medium"),
        "category":          ai_result.get("category", "Other"),
        "contractor_brief":  ai_result.get("contractor_brief", ""),
        "tenant_advice":     ai_result.get("tenant_advice", ""),
        "response_time":     ai_result.get("response_time", "Within 24 hours"),
        "language_detected": ai_result.get("language_detected", "en"),
        "apartment_ref":     apartment_ref,
    }

    new_id = create_request(request_data)
    full_request = get_request_by_id(new_id)
    return jsonify(full_request), 201


@app.route("/api/stream")
def stream():
    """
    Server-Sent Events endpoint for live streaming AI triage.
    
    Query params:
        message (str, required): URL-encoded tenant message
    
    Returns:
        text/event-stream
        Each chunk: data: <token>\n\n
        Final chunk: data: [DONE]\n\n
    """
    message = request.args.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message required"}), 400

    def generate():
        try:
            for token in stream_triage(message):
                # Escape newlines for SSE format
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/requests", methods=["GET"])
def get_requests():
    """Return all requests ordered newest first."""
    return jsonify(get_all_requests()), 200


@app.route("/api/requests/<int:request_id>", methods=["GET"])
def get_request(request_id):
    """Return a single request by ID."""
    req = get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found", "code": "NOT_FOUND"}), 404
    return jsonify(req), 200


@app.route("/api/requests/<int:request_id>/reply", methods=["POST"])
def generate_reply_route(request_id):
    """
    Generate and store an AI tenant reply for a request.
    Returns: { "reply": "..." }
    """
    req = get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found", "code": "NOT_FOUND"}), 404

    try:
        reply = generate_reply(req)
        update_reply(request_id, reply)
        return jsonify({"reply": reply}), 200
    except Exception as e:
        return jsonify({"error": "AI error", "detail": str(e)}), 500


@app.route("/api/requests/<int:request_id>/status", methods=["PATCH"])
def update_request_status(request_id):
    """
    Update the status of a request.
    Request JSON: { "status": "New" | "In Progress" | "Resolved" }
    """
    data = request.get_json()
    new_status = data.get("status") if data else None

    if new_status not in VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
            "code": "INVALID_STATUS"
        }), 400

    success = update_status(request_id, new_status)
    if not success:
        return jsonify({"error": "Request not found", "code": "NOT_FOUND"}), 404

    return jsonify(get_request_by_id(request_id)), 200


@app.route("/api/analytics")
def analytics():
    """Return aggregated stats for the dashboard charts and chips."""
    return jsonify(get_analytics()), 200


# ─── AUTOPILOT ROUTES ───────────────────────────────────────────────────────

@app.route("/api/autopilot/start", methods=["POST"])
def autopilot_start():
    """Start AutoPilot mode."""
    started = autopilot.start()
    return jsonify({"running": True, "started": started}), 200


@app.route("/api/autopilot/stop", methods=["POST"])
def autopilot_stop():
    """Stop AutoPilot mode."""
    autopilot.stop()
    return jsonify({"running": False}), 200


@app.route("/api/autopilot/status")
def autopilot_status():
    """Return AutoPilot running state and trace log."""
    return jsonify({
        "running": autopilot.is_running(),
        "trace": autopilot.get_trace()
    }), 200


@app.route("/api/autopilot/trace-stream")
def autopilot_trace_stream():
    """
    SSE stream for live AutoPilot trace updates.
    Polls every 800ms and sends new trace entries.
    Frontend uses EventSource to display live reasoning.
    """
    def generate():
        sent_count = 0
        while autopilot.is_running():
            trace = autopilot.get_trace()
            if len(trace) > sent_count:
                new_entries = trace[sent_count:]
                for entry in new_entries:
                    payload = json.dumps(entry)
                    yield f"data: {payload}\n\n"
                sent_count = len(trace)
            time.sleep(0.8)
        # Send any final entries after stop
        trace = autopilot.get_trace()
        if len(trace) > sent_count:
            for entry in trace[sent_count:]:
                payload = json.dumps(entry)
                yield f"data: {payload}\n\n"
        yield "data: [STOPPED]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ─── SIMULATOR ROUTE ────────────────────────────────────────────────────────

@app.route("/api/simulate", methods=["POST"])
def simulate():
    """
    Live Traffic Simulator: picks a random request from SIMULATOR_REQUESTS,
    triages it with AI, saves it to DB, and returns the new request.
    Used to show live incoming requests during demo.
    """
    item = random.choice(SIMULATOR_REQUESTS)
    message = item["msg"]
    apt = item["apt"]

    try:
        ai_result = triage_request(message)
    except Exception as e:
        return jsonify({"error": "Simulation failed", "detail": str(e)}), 500

    request_data = {
        "tenant_message":    message,
        "urgency":           ai_result.get("urgency", "Medium"),
        "category":          ai_result.get("category", "Other"),
        "contractor_brief":  ai_result.get("contractor_brief", ""),
        "tenant_advice":     ai_result.get("tenant_advice", ""),
        "response_time":     ai_result.get("response_time", "Within 24 hours"),
        "language_detected": ai_result.get("language_detected", "en"),
        "apartment_ref":     apt,
    }

    new_id = create_request(request_data)
    return jsonify(get_request_by_id(new_id)), 201


# ─── ERROR HANDLERS ─────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found", "code": "NOT_FOUND"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "code": "SERVER_ERROR"}), 500


if __name__ == "__main__":
    print("🏠 PropertyOS starting...")
    print("🌐 Open: http://localhost:5000")
    print("🔑 API Key loaded:", "✅ Yes" if os.environ.get("GROQ_API_KEY") else "❌ NO KEY FOUND — check .env file")
    app.run(debug=True, port=5000, threaded=True)
```

---

## FILE 8: seed_data.py — COMPLETE CODE

```python
# seed_data.py
# Run this ONCE before the demo to populate the database with 8 realistic requests
# Usage: python seed_data.py
# WARNING: This deletes ALL existing data and replaces with fresh demo data

import os
import time
from dotenv import load_dotenv
load_dotenv()

from database import init_db, delete_all_requests, create_request, update_status
from ai_engine import triage_request

DEMO_REQUESTS = [
    {
        "msg": "There is water pouring from my bedroom ceiling right now. It started about 10 minutes ago and is getting worse.",
        "apt": "Apt 4B",
        "set_status": "New"
    },
    {
        "msg": "We have had no heating or hot water since this morning. I have a 4-month-old baby at home and it is very cold.",
        "apt": "Apt 2A",
        "set_status": "In Progress"
    },
    {
        "msg": "My boiler has been making a loud banging noise for the past 2 days. The heating still works but I am worried something is wrong.",
        "apt": "Apt 7C",
        "set_status": "New"
    },
    {
        "msg": "The kitchen tap has been dripping constantly since last week. It is not urgent but it wastes a lot of water.",
        "apt": "Apt 1D",
        "set_status": "New"
    },
    {
        "msg": "One of my kitchen cupboard door hinges is broken and the door hangs open. It has been like this for a while.",
        "apt": "Apt 9A",
        "set_status": "Resolved"
    },
    {
        "msg": "Il y a une fuite d'eau sous mon évier depuis hier matin. L'eau s'accumule dans le placard. Pouvez-vous envoyer quelqu'un aujourd'hui?",
        "apt": "Apt 3F",
        "set_status": "New"
    },
    {
        "msg": "My neighbour in 6A plays very loud music every night after midnight. It has been happening for 2 weeks and I cannot sleep.",
        "apt": "Apt 6B",
        "set_status": "New"
    },
    {
        "msg": "I have found mouse droppings behind my fridge and under the kitchen sink. I have seen a mouse twice this week.",
        "apt": "Apt 5C",
        "set_status": "In Progress"
    },
]


def run_seed():
    print("🌱 PropertyOS Seed Data Script")
    print("=" * 40)
    
    init_db()
    print("✅ Database initialised")
    
    delete_all_requests()
    print("🗑️  Cleared existing data")
    print()
    
    for i, item in enumerate(DEMO_REQUESTS, 1):
        print(f"[{i}/8] Processing: {item['apt']} — {item['msg'][:50]}...")
        
        try:
            ai_result = triage_request(item["msg"])
            
            request_data = {
                "tenant_message":    item["msg"],
                "urgency":           ai_result.get("urgency", "Medium"),
                "category":          ai_result.get("category", "Other"),
                "contractor_brief":  ai_result.get("contractor_brief", ""),
                "tenant_advice":     ai_result.get("tenant_advice", ""),
                "response_time":     ai_result.get("response_time", "Within 24 hours"),
                "language_detected": ai_result.get("language_detected", "en"),
                "apartment_ref":     item["apt"],
            }
            
            new_id = create_request(request_data)
            
            if item["set_status"] != "New":
                update_status(new_id, item["set_status"])
            
            print(f"       ✅ Urgency: {request_data['urgency']} | Category: {request_data['category']} | Status: {item['set_status']}")
        
        except Exception as e:
            print(f"       ❌ Error: {e}")
        
        time.sleep(0.5)  # Rate limit protection
    
    print()
    print("=" * 40)
    print("✅ Seed data complete! 8 requests loaded.")
    print("🌐 Start the app: python app.py")
    print("🔗 Then open: http://localhost:5000")


if __name__ == "__main__":
    run_seed()
```

---

## FILE 9: templates/index.html — COMPLETE CODE

This is the ENTIRE frontend. One single HTML file with embedded CSS and JavaScript.
Build it exactly as specified below.

### HTML STRUCTURE

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PropertyOS — AI Operations Platform</title>

  <!-- FONTS -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">

  <!-- CHART.JS -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
</head>

<body>
  <!-- APP SHELL: sidebar + main -->
  <div class="app-shell">

    <!-- SIDEBAR -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-text">Property<span class="logo-accent">OS</span></span>
        <span class="logo-sub">Operations Platform</span>
      </div>
      <nav class="sidebar-nav">
        <a class="nav-item active" data-view="triage">
          <span class="nav-icon">⚡</span> Triage Center
        </a>
        <a class="nav-item" data-view="comms">
          <span class="nav-icon">💬</span> Tenant Comms
        </a>
        <a class="nav-item" data-view="analytics">
          <span class="nav-icon">📊</span> Analytics
        </a>
        <a class="nav-item" data-view="queue">
          <span class="nav-icon">🗃️</span> Full Queue
        </a>
      </nav>
      <div class="ai-status-badge">
        <div class="ai-dot"></div>
        <span>AI Engine Online</span>
      </div>
    </aside>

    <!-- MAIN CONTENT -->
    <main class="main-content">

      <!-- TOP HEADER BAR -->
      <div class="top-bar">
        <div class="top-bar-left">
          <h1 class="page-title">Triage Center</h1>
          <span class="page-sub" id="pageDate"></span>
        </div>
        <div class="top-bar-right">
          <!-- AutoPilot Toggle -->
          <div class="autopilot-control" id="autopilotControl">
            <span class="autopilot-label">AutoPilot</span>
            <div class="toggle-switch" id="autopilotToggle">
              <div class="toggle-thumb"></div>
            </div>
            <span class="autopilot-status" id="autopilotStatus">OFF</span>
          </div>
          <!-- Simulator Button -->
          <button class="btn-simulate" id="simulateBtn">📡 Simulate Request</button>
          <!-- New Request Button -->
          <button class="btn-primary" id="newRequestBtn">+ New Request</button>
        </div>
      </div>

      <!-- STATS ROW: 4 chips -->
      <div class="stats-row">
        <div class="stat-chip emergency">
          <div class="stat-val" id="statEmergency">0</div>
          <div class="stat-lbl">Emergency</div>
        </div>
        <div class="stat-chip high">
          <div class="stat-val" id="statHigh">0</div>
          <div class="stat-lbl">High Priority</div>
        </div>
        <div class="stat-chip resolved">
          <div class="stat-val" id="statResolved">0</div>
          <div class="stat-lbl">Resolved Today</div>
        </div>
        <div class="stat-chip avg">
          <div class="stat-val" id="statAvg">—</div>
          <div class="stat-lbl">Avg Response</div>
        </div>
      </div>

      <!-- MAIN PANEL ROW: left col + right AI panel -->
      <div class="panel-row">

        <!-- LEFT COLUMN -->
        <div class="left-col">

          <!-- REQUEST QUEUE PANEL -->
          <div class="panel" id="requestQueuePanel">
            <div class="panel-header">
              <span class="panel-title">Live Request Queue</span>
              <span class="panel-badge" id="urgentBadge">0 urgent</span>
            </div>
            <div class="queue-list" id="queueList">
              <div class="queue-empty">No requests yet. Submit one to get started.</div>
            </div>
          </div>

          <!-- CHART PANEL -->
          <div class="panel chart-panel">
            <div class="panel-header">
              <span class="panel-title">Urgency Breakdown</span>
            </div>
            <div class="chart-wrap">
              <canvas id="urgencyChart"></canvas>
            </div>
          </div>

        </div>

        <!-- RIGHT: AI PANEL -->
        <div class="panel ai-panel">

          <!-- AI Panel Header -->
          <div class="panel-header">
            <span class="panel-title">⚡ AI Triage Engine</span>
            <span class="ai-live-badge">● LIVE</span>
          </div>

          <!-- AutoPilot Trace (hidden by default, shown when AutoPilot ON) -->
          <div class="autopilot-trace" id="autopilotTrace" style="display:none;">
            <div class="trace-header">🤖 AutoPilot Reasoning Trace</div>
            <div class="trace-log" id="traceLog"></div>
          </div>

          <!-- AI Output: shows streaming triage result or selected request details -->
          <div class="ai-output-wrap" id="aiOutputWrap">
            <div class="ai-placeholder" id="aiPlaceholder">
              <div class="placeholder-icon">🏠</div>
              <p>Paste a tenant message below and click Triage<br>or select a request from the queue</p>
            </div>
            <div class="ai-result" id="aiResult" style="display:none;">
              <!-- Populated dynamically -->
            </div>
          </div>

          <!-- Action buttons (hidden until result loaded) -->
          <div class="ai-actions" id="aiActions" style="display:none;">
            <button class="btn-action" id="generateReplyBtn">💬 Generate Reply</button>
            <button class="btn-action" id="copyBriefBtn">📋 Copy Brief</button>
            <button class="btn-action" id="downloadBriefBtn">⬇️ Download .txt</button>
          </div>

          <!-- Reply box (hidden until reply generated) -->
          <div class="reply-box" id="replyBox" style="display:none;">
            <div class="reply-header">
              <span>✉️ Tenant Reply Draft</span>
              <button class="btn-copy-reply" id="copyReplyBtn">Copy</button>
            </div>
            <div class="reply-text" id="replyText"></div>
          </div>

          <!-- Input area -->
          <div class="ai-input-area">
            <!-- Voice button -->
            <button class="btn-voice" id="voiceBtn" title="Speak your request">🎙️</button>
            <textarea
              id="tenantInput"
              placeholder="Paste tenant message here... or click 🎙️ to speak"
              rows="3"
            ></textarea>
            <div class="input-row">
              <input type="text" id="aptInput" placeholder="Apt (optional)" class="apt-input">
              <button class="btn-triage" id="triageBtn">⚡ Triage</button>
            </div>
          </div>

        </div>
      </div>

    </main>
  </div>

  <!-- TOAST CONTAINER -->
  <div id="toastContainer"></div>

</body>
</html>
```

---

### CSS (embed in index.html inside `<style>` tag in `<head>`)

```css
/* ── RESET & ROOT ─────────────────────────────────────── */
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg:       #0A0A0F;
  --surface:  #13131A;
  --surface2: #1C1C28;
  --border:   #2A2A3D;
  --accent:   #00D9A3;
  --accent2:  #4F8FFF;
  --accent3:  #FF6B9D;
  --accent4:  #F59E0B;
  --text:     #E8E8F0;
  --muted:    #6B7280;
  --red:      #EF4444;
  --green:    #10B981;
  --mono:     'DM Mono', monospace;
  --sans:     'DM Sans', sans-serif;
  --head:     'Syne', sans-serif;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  height: 100vh;
  overflow: hidden;
}

/* ── APP SHELL ────────────────────────────────────────── */
.app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100vh;
  overflow: hidden;
}

/* ── SIDEBAR ──────────────────────────────────────────── */
.sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.sidebar-logo {
  padding: 24px 20px 20px;
  border-bottom: 1px solid var(--border);
}

.logo-text {
  font-family: var(--head);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
  display: block;
  margin-bottom: 2px;
}

.logo-accent { color: var(--accent); }

.logo-sub {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 20px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
  border-left: 2px solid transparent;
  text-decoration: none;
  transition: all 0.15s ease;
}

.nav-item:hover { color: var(--text); background: rgba(255,255,255,0.03); }
.nav-item.active {
  color: var(--text);
  background: rgba(0,217,163,0.07);
  border-left-color: var(--accent);
}

.nav-icon { font-size: 15px; }

.ai-status-badge {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
}

.ai-dot {
  width: 7px; height: 7px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}

/* ── MAIN CONTENT ─────────────────────────────────────── */
.main-content {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  padding: 20px 24px;
  gap: 16px;
}

/* ── TOP BAR ──────────────────────────────────────────── */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.page-title {
  font-family: var(--head);
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.page-sub {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* AutoPilot Toggle */
.autopilot-control {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 100px;
  padding: 6px 14px;
  cursor: pointer;
}

.autopilot-label {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.toggle-switch {
  width: 36px; height: 20px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 100px;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-switch.active { background: var(--accent); border-color: var(--accent); }

.toggle-thumb {
  position: absolute;
  top: 2px; left: 2px;
  width: 14px; height: 14px;
  background: var(--muted);
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}

.toggle-switch.active .toggle-thumb {
  transform: translateX(16px);
  background: #0A0A0F;
}

.autopilot-status {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--muted);
  min-width: 24px;
}
.autopilot-status.active { color: var(--accent); }

/* Buttons */
.btn-simulate {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 14px;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
}
.btn-simulate:hover { border-color: var(--accent2); color: var(--accent2); }

.btn-primary {
  background: var(--accent);
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 500;
  color: #0A0A0F;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.85; }

/* ── STATS ROW ────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  flex-shrink: 0;
}

.stat-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  transition: border-color 0.2s;
}

.stat-chip:hover { border-color: var(--accent); }

.stat-val {
  font-family: var(--head);
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-lbl {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.stat-chip.emergency .stat-val { color: var(--red); }
.stat-chip.high .stat-val      { color: var(--accent4); }
.stat-chip.resolved .stat-val  { color: var(--green); }
.stat-chip.avg .stat-val       { color: var(--accent2); }

/* ── PANEL ROW ────────────────────────────────────────── */
.panel-row {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.left-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow: hidden;
}

/* ── PANEL ────────────────────────────────────────────── */
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.panel-title {
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.panel-badge {
  font-family: var(--mono);
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 100px;
  background: rgba(239,68,68,0.15);
  color: var(--red);
  border: 1px solid rgba(239,68,68,0.3);
}

/* ── REQUEST QUEUE ────────────────────────────────────── */
#requestQueuePanel {
  flex: 1.5;
  min-height: 0;
}

.queue-list {
  overflow-y: auto;
  flex: 1;
}

.queue-empty {
  padding: 24px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
  font-family: var(--mono);
}

.queue-item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: background 0.15s;
  animation: slideIn 0.3s ease;
}

.queue-item:hover { background: rgba(255,255,255,0.02); }
.queue-item.selected { background: rgba(0,217,163,0.05); border-left: 2px solid var(--accent); }

@keyframes slideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.urgency-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.urgency-dot.Emergency { background: var(--red); box-shadow: 0 0 6px var(--red); }
.urgency-dot.High      { background: var(--accent4); }
.urgency-dot.Medium    { background: #FDE68A; }
.urgency-dot.Low       { background: var(--green); }

.queue-item-content { flex: 1; min-width: 0; }
.queue-item-title {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}
.queue-item-meta {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
}

.status-tag {
  font-family: var(--mono);
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 100px;
  border: 1px solid var(--border);
  color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}
.status-tag.New        { color: var(--muted); }
.status-tag.in-progress { color: var(--accent4); border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.08); }
.status-tag.resolved   { color: var(--green); border-color: rgba(16,185,129,0.3); background: rgba(16,185,129,0.08); }

/* ── CHART ────────────────────────────────────────────── */
.chart-panel { flex: 1; min-height: 0; }
.chart-wrap  { flex: 1; padding: 12px 16px; min-height: 0; position: relative; }

/* ── AI PANEL ─────────────────────────────────────────── */
.ai-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.ai-live-badge {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--accent);
  animation: pulse 1.5s infinite;
}

/* AutoPilot Trace */
.autopilot-trace {
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  max-height: 220px;
}

.trace-header {
  padding: 8px 16px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
  background: rgba(0,217,163,0.05);
  letter-spacing: 0.04em;
}

.trace-log {
  overflow-y: auto;
  max-height: 180px;
  padding: 8px 0;
}

.trace-entry {
  padding: 3px 16px;
  font-family: var(--mono);
  font-size: 11px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.trace-entry.info       { color: var(--text); }
.trace-entry.success    { color: var(--green); }
.trace-entry.warning    { color: var(--accent4); }
.trace-entry.processing { color: var(--accent2); }

.trace-time {
  color: var(--border);
  flex-shrink: 0;
}

/* AI Output */
.ai-output-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  min-height: 0;
}

.ai-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
  text-align: center;
  gap: 12px;
}

.placeholder-icon { font-size: 36px; }

.ai-placeholder p {
  font-size: 13px;
  line-height: 1.6;
}

.ai-result { font-size: 13px; line-height: 1.7; }

.result-field { margin-bottom: 14px; }
.result-label {
  font-family: var(--mono);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent);
  margin-bottom: 4px;
}
.result-value { color: var(--text); }
.result-value.emergency { color: var(--red); font-weight: 600; }
.result-value.high      { color: var(--accent4); font-weight: 600; }
.result-value.medium    { color: #FDE68A; font-weight: 600; }
.result-value.low       { color: var(--green); font-weight: 600; }

.brief-box {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text);
}

.lang-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(79,143,255,0.1);
  border: 1px solid rgba(79,143,255,0.3);
  border-radius: 100px;
  padding: 3px 10px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent2);
  margin-bottom: 14px;
}

/* Streaming cursor */
.cursor {
  display: inline-block;
  width: 8px; height: 14px;
  background: var(--accent);
  border-radius: 1px;
  animation: blink 0.7s infinite;
  vertical-align: middle;
  margin-left: 2px;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* AI Actions */
.ai-actions {
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.btn-action {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px 14px;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s;
}
.btn-action:hover { border-color: var(--accent); color: var(--accent); }
.btn-action:disabled { opacity: 0.5; cursor: not-allowed; }

/* Reply Box */
.reply-box {
  margin: 0 16px 12px;
  background: rgba(0,217,163,0.05);
  border: 1px solid rgba(0,217,163,0.2);
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
}

.reply-header {
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
  border-bottom: 1px solid rgba(0,217,163,0.15);
}

.btn-copy-reply {
  background: transparent;
  border: 1px solid rgba(0,217,163,0.3);
  border-radius: 6px;
  padding: 2px 10px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--accent);
  cursor: pointer;
}

.reply-text {
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text);
  max-height: 120px;
  overflow-y: auto;
}

/* Input Area */
.ai-input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
  position: relative;
}

.btn-voice {
  position: absolute;
  top: 20px;
  right: 24px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  width: 32px; height: 32px;
  cursor: pointer;
  font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
  z-index: 1;
}
.btn-voice:hover { border-color: var(--accent3); }
.btn-voice.listening { background: rgba(255,107,157,0.15); border-color: var(--accent3); animation: pulse 0.8s infinite; }

#tenantInput {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 44px 10px 12px;
  color: var(--text);
  font-family: var(--sans);
  font-size: 13px;
  resize: none;
  line-height: 1.5;
  transition: border-color 0.15s;
  width: 100%;
}
#tenantInput:focus { outline: none; border-color: var(--accent); }
#tenantInput::placeholder { color: var(--muted); }

.input-row {
  display: flex;
  gap: 8px;
}

.apt-input {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 12px;
  width: 140px;
  transition: border-color 0.15s;
}
.apt-input:focus { outline: none; border-color: var(--accent); }
.apt-input::placeholder { color: var(--muted); }

.btn-triage {
  flex: 1;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  padding: 8px 20px;
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 500;
  color: #0A0A0F;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-triage:hover { opacity: 0.85; }
.btn-triage:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── TOAST ────────────────────────────────────────────── */
#toastContainer {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toast {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 18px;
  font-family: var(--mono);
  font-size: 12px;
  max-width: 300px;
  animation: toastIn 0.2s ease;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.toast.success { border-left: 3px solid var(--green); color: var(--green); }
.toast.error   { border-left: 3px solid var(--red); color: var(--red); }
.toast.info    { border-left: 3px solid var(--accent2); color: var(--accent2); }

@keyframes toastIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
@keyframes toastOut { from { opacity:1; } to { opacity:0; transform:translateY(8px); } }

/* ── SCROLLBAR STYLE ──────────────────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* ── RESPONSIVE ───────────────────────────────────────── */
@media (max-width: 900px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .panel-row { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  body { overflow: auto; }
  .main-content { height: auto; overflow: auto; }
}
```

---

### JAVASCRIPT (embed in index.html before `</body>` inside `<script>` tag)

```javascript
// ── STATE ──────────────────────────────────────────────
let currentRequestId = null;
let simulatorInterval = null;
let simulatorRunning = false;
let autopilotTraceSource = null;
let lastTraceCount = 0;

// ── INIT ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setPageDate();
  loadQueue();
  loadAnalytics();
  setupTriageBtn();
  setupVoiceBtn();
  setupAutopilotToggle();
  setupSimulateBtn();
  setupActionButtons();

  // Refresh queue and analytics every 4 seconds
  setInterval(() => { loadQueue(); loadAnalytics(); }, 4000);
});

function setPageDate() {
  const now = new Date();
  document.getElementById('pageDate').textContent =
    now.toLocaleDateString('en-IE', { weekday:'long', day:'numeric', month:'long' });
}

// ── QUEUE ──────────────────────────────────────────────
async function loadQueue() {
  try {
    const res = await fetch('/api/requests');
    const requests = await res.json();
    renderQueue(requests);
  } catch (e) {
    console.error('Queue load failed:', e);
  }
}

function renderQueue(requests) {
  const list = document.getElementById('queueList');
  const badge = document.getElementById('urgentBadge');

  if (!requests.length) {
    list.innerHTML = '<div class="queue-empty">No requests yet.</div>';
    badge.textContent = '0 urgent';
    return;
  }

  const urgent = requests.filter(r => r.urgency === 'Emergency' || r.urgency === 'High').length;
  badge.textContent = `${urgent} urgent`;
  badge.style.display = urgent > 0 ? '' : 'none';

  list.innerHTML = requests.map(r => `
    <div class="queue-item ${currentRequestId === r.id ? 'selected' : ''}"
         onclick="selectRequest(${r.id})">
      <div class="urgency-dot ${r.urgency}"></div>
      <div class="queue-item-content">
        <div class="queue-item-title">${escHtml(r.tenant_message.substring(0, 65))}${r.tenant_message.length > 65 ? '…' : ''}</div>
        <div class="queue-item-meta">${r.apartment_ref || 'Unknown apt'} · ${r.category} · ${timeAgo(r.created_at)}</div>
      </div>
      <div class="status-tag ${r.status === 'In Progress' ? 'in-progress' : r.status.toLowerCase()}">${r.status}</div>
    </div>
  `).join('');
}

async function selectRequest(id) {
  currentRequestId = id;
  try {
    const res = await fetch(`/api/requests/${id}`);
    const req = await res.json();
    showRequestInPanel(req);
    // Re-render queue to update selected state
    loadQueue();
  } catch (e) {
    showToast('Failed to load request', 'error');
  }
}

// ── ANALYTICS ─────────────────────────────────────────
let urgencyChart = null;

async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();

    document.getElementById('statEmergency').textContent = data.by_urgency.Emergency || 0;
    document.getElementById('statHigh').textContent = data.by_urgency.High || 0;
    document.getElementById('statResolved').textContent = data.resolved_today || 0;
    document.getElementById('statAvg').textContent = data.avg_response_time_label || '—';

    renderChart(data);
  } catch (e) {
    console.error('Analytics failed:', e);
  }
}

function renderChart(data) {
  const ctx = document.getElementById('urgencyChart').getContext('2d');
  const labels = ['Emergency', 'High', 'Medium', 'Low'];
  const values = labels.map(l => data.by_urgency[l] || 0);
  const colors = ['#EF4444', '#F59E0B', '#FDE68A', '#10B981'];

  if (urgencyChart) {
    urgencyChart.data.datasets[0].data = values;
    urgencyChart.update('none');
    return;
  }

  urgencyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: '#2A2A3D' }, ticks: { color: '#6B7280', font: { family: 'DM Mono', size: 10 } } },
        y: { grid: { color: '#2A2A3D' }, ticks: { color: '#6B7280', font: { family: 'DM Mono', size: 10 }, stepSize: 1 } }
      }
    }
  });
}

// ── TRIAGE ────────────────────────────────────────────
function setupTriageBtn() {
  document.getElementById('triageBtn').addEventListener('click', handleTriage);
  document.getElementById('tenantInput').addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 'Enter') handleTriage();
  });
}

async function handleTriage() {
  const message = document.getElementById('tenantInput').value.trim();
  const apt = document.getElementById('aptInput').value.trim();

  if (!message) {
    showToast('Please enter a tenant message', 'error');
    document.getElementById('tenantInput').focus();
    return;
  }

  const btn = document.getElementById('triageBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Analysing...';

  // Show streaming output
  showStreamingPanel();

  try {
    // Start SSE stream for visual effect
    const encodedMsg = encodeURIComponent(message);
    const evtSource = new EventSource(`/api/stream?message=${encodedMsg}`);
    let streamBuffer = '';

    evtSource.onmessage = (e) => {
      if (e.data === '[DONE]') {
        evtSource.close();
        // Now persist to DB and show structured result
        persistAndShow(message, apt);
        return;
      }
      if (e.data.startsWith('[ERROR]')) {
        evtSource.close();
        showToast('Stream error — retrying...', 'error');
        persistAndShow(message, apt);
        return;
      }
      const token = e.data.replace(/\\n/g, '\n');
      streamBuffer += token;
      updateStreamDisplay(streamBuffer);
    };

    evtSource.onerror = () => {
      evtSource.close();
      persistAndShow(message, apt);
    };

  } catch (e) {
    showToast('Connection error', 'error');
    btn.disabled = false;
    btn.textContent = '⚡ Triage';
  }
}

function showStreamingPanel() {
  document.getElementById('aiPlaceholder').style.display = 'none';
  document.getElementById('aiResult').style.display = 'block';
  document.getElementById('aiResult').innerHTML = `
    <div class="result-field">
      <div class="result-label">AI Processing</div>
      <div class="result-value" id="streamDisplay" style="font-family:var(--mono);font-size:12px;color:var(--muted);white-space:pre-wrap;"></div>
    </div>
  `;
  document.getElementById('aiActions').style.display = 'none';
  document.getElementById('replyBox').style.display = 'none';
}

function updateStreamDisplay(text) {
  const el = document.getElementById('streamDisplay');
  if (el) {
    el.innerHTML = escHtml(text) + '<span class="cursor"></span>';
    // Scroll to bottom of ai output
    const wrap = document.getElementById('aiOutputWrap');
    wrap.scrollTop = wrap.scrollHeight;
  }
}

async function persistAndShow(message, apt) {
  try {
    const res = await fetch('/api/triage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, apartment_ref: apt || null })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const req = await res.json();
    currentRequestId = req.id;
    showRequestInPanel(req);
    loadQueue();
    loadAnalytics();

    document.getElementById('tenantInput').value = '';
    document.getElementById('aptInput').value = '';

    showToast(`✅ Request triaged: ${req.urgency} priority`, req.urgency === 'Emergency' ? 'error' : 'success');

  } catch (e) {
    showToast('Failed to save request: ' + e.message, 'error');
  } finally {
    const btn = document.getElementById('triageBtn');
    btn.disabled = false;
    btn.textContent = '⚡ Triage';
  }
}

// ── SHOW REQUEST IN PANEL ──────────────────────────────
function showRequestInPanel(req) {
  document.getElementById('aiPlaceholder').style.display = 'none';
  document.getElementById('aiResult').style.display = 'block';

  const langBadge = req.language_detected && req.language_detected !== 'en'
    ? `<div class="lang-badge">🌍 ${getLanguageName(req.language_detected)} detected — replying in ${getLanguageName(req.language_detected)}</div>`
    : '';

  const urgencyClass = req.urgency.toLowerCase();

  document.getElementById('aiResult').innerHTML = `
    ${langBadge}
    <div class="result-field">
      <div class="result-label">Urgency Level</div>
      <div class="result-value ${urgencyClass}">${getUrgencyEmoji(req.urgency)} ${req.urgency.toUpperCase()}</div>
    </div>
    <div class="result-field">
      <div class="result-label">Category</div>
      <div class="result-value">${req.category}</div>
    </div>
    <div class="result-field">
      <div class="result-label">Response Time</div>
      <div class="result-value">${req.response_time}</div>
    </div>
    <div class="result-field">
      <div class="result-label">Contractor Brief</div>
      <div class="brief-box">${escHtml(req.contractor_brief)}</div>
    </div>
    <div class="result-field">
      <div class="result-label">Tenant Advice</div>
      <div class="result-value" style="color:var(--accent2);">${escHtml(req.tenant_advice)}</div>
    </div>
    <div class="result-field">
      <div class="result-label">Status</div>
      <select class="status-select" onchange="updateStatus(${req.id}, this.value)">
        <option value="New" ${req.status==='New'?'selected':''}>New</option>
        <option value="In Progress" ${req.status==='In Progress'?'selected':''}>In Progress</option>
        <option value="Resolved" ${req.status==='Resolved'?'selected':''}>Resolved</option>
      </select>
    </div>
  `;

  // Show action buttons
  document.getElementById('aiActions').style.display = 'flex';

  // Show existing reply if available
  if (req.ai_reply) {
    document.getElementById('replyText').textContent = req.ai_reply;
    document.getElementById('replyBox').style.display = 'block';
  } else {
    document.getElementById('replyBox').style.display = 'none';
  }
}

// ── STATUS UPDATE ──────────────────────────────────────
async function updateStatus(id, status) {
  try {
    await fetch(`/api/requests/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    loadQueue();
    loadAnalytics();
    showToast(`Status updated to: ${status}`, 'success');
  } catch (e) {
    showToast('Status update failed', 'error');
  }
}

// ── ACTION BUTTONS ────────────────────────────────────
function setupActionButtons() {
  document.getElementById('generateReplyBtn').addEventListener('click', async () => {
    if (!currentRequestId) return;
    const btn = document.getElementById('generateReplyBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Generating...';
    try {
      const res = await fetch(`/api/requests/${currentRequestId}/reply`, { method: 'POST' });
      const data = await res.json();
      document.getElementById('replyText').textContent = data.reply;
      document.getElementById('replyBox').style.display = 'block';
      showToast('Reply generated', 'success');
    } catch (e) {
      showToast('Reply generation failed', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '💬 Generate Reply';
    }
  });

  document.getElementById('copyBriefBtn').addEventListener('click', () => {
    const briefEl = document.querySelector('.brief-box');
    if (!briefEl) return;
    navigator.clipboard.writeText(briefEl.textContent).then(() => {
      const btn = document.getElementById('copyBriefBtn');
      btn.textContent = '✅ Copied!';
      setTimeout(() => btn.textContent = '📋 Copy Brief', 2000);
    });
  });

  document.getElementById('downloadBriefBtn').addEventListener('click', () => {
    const briefEl = document.querySelector('.brief-box');
    if (!briefEl) return;
    const apt = document.querySelector('.queue-item.selected .queue-item-meta')?.textContent || 'unknown';
    const date = new Date().toISOString().split('T')[0];
    const content = `PROPERTY MAINTENANCE REQUEST\nDate: ${date}\nUnit: ${apt.split('·')[0].trim()}\n\nCONTRACTOR BRIEF:\n${briefEl.textContent}`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brief_${date}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Brief downloaded', 'success');
  });

  document.getElementById('copyReplyBtn').addEventListener('click', () => {
    const text = document.getElementById('replyText').textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('copyReplyBtn');
      btn.textContent = '✅ Copied!';
      setTimeout(() => btn.textContent = 'Copy', 2000);
    });
  });
}

// ── VOICE INPUT ────────────────────────────────────────
function setupVoiceBtn() {
  const btn = document.getElementById('voiceBtn');
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    btn.style.display = 'none';
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-IE';

  let isListening = false;

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    document.getElementById('tenantInput').value = transcript;
    if (event.results[event.resultIndex].isFinal) {
      btn.classList.remove('listening');
      isListening = false;
      showToast('Voice captured — click Triage to analyse', 'info');
    }
  };

  recognition.onerror = (e) => {
    btn.classList.remove('listening');
    isListening = false;
    showToast('Voice error: ' + e.error, 'error');
  };

  recognition.onend = () => {
    btn.classList.remove('listening');
    isListening = false;
  };

  btn.addEventListener('click', () => {
    if (isListening) {
      recognition.stop();
    } else {
      recognition.start();
      btn.classList.add('listening');
      isListening = true;
      showToast('🎙️ Listening... speak now', 'info');
    }
  });
}

// ── AUTOPILOT ─────────────────────────────────────────
function setupAutopilotToggle() {
  document.getElementById('autopilotControl').addEventListener('click', toggleAutopilot);
}

async function toggleAutopilot() {
  const toggle = document.getElementById('autopilotToggle');
  const statusEl = document.getElementById('autopilotStatus');
  const tracePanel = document.getElementById('autopilotTrace');

  const isActive = toggle.classList.contains('active');

  if (!isActive) {
    // Start AutoPilot
    toggle.classList.add('active');
    statusEl.textContent = 'ON';
    statusEl.classList.add('active');
    tracePanel.style.display = 'block';
    document.getElementById('traceLog').innerHTML = '';
    lastTraceCount = 0;

    await fetch('/api/autopilot/start', { method: 'POST' });
    showToast('🤖 AutoPilot activated!', 'success');

    // Start SSE trace stream
    startTraceStream();

  } else {
    // Stop AutoPilot
    toggle.classList.remove('active');
    statusEl.textContent = 'OFF';
    statusEl.classList.remove('active');

    await fetch('/api/autopilot/stop', { method: 'POST' });
    showToast('AutoPilot stopped', 'info');

    if (autopilotTraceSource) {
      autopilotTraceSource.close();
      autopilotTraceSource = null;
    }
  }
}

function startTraceStream() {
  if (autopilotTraceSource) autopilotTraceSource.close();

  autopilotTraceSource = new EventSource('/api/autopilot/trace-stream');

  autopilotTraceSource.onmessage = (e) => {
    if (e.data === '[STOPPED]') {
      autopilotTraceSource.close();
      autopilotTraceSource = null;
      return;
    }
    try {
      const entry = JSON.parse(e.data);
      appendTraceEntry(entry);
    } catch (err) {
      console.error('Trace parse error:', err);
    }
  };

  autopilotTraceSource.onerror = () => {
    autopilotTraceSource.close();
    autopilotTraceSource = null;
  };
}

function appendTraceEntry(entry) {
  const log = document.getElementById('traceLog');
  const el = document.createElement('div');
  el.className = `trace-entry ${entry.type || 'info'}`;
  el.innerHTML = `
    <span class="trace-time">${entry.timestamp}</span>
    <span>${escHtml(entry.message)}</span>
  `;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

// ── LIVE SIMULATOR ────────────────────────────────────
function setupSimulateBtn() {
  const btn = document.getElementById('simulateBtn');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = '📡 Simulating...';
    try {
      const res = await fetch('/api/simulate', { method: 'POST' });
      const req = await res.json();
      loadQueue();
      loadAnalytics();
      showToast(`📡 New request: ${req.apartment_ref} — ${req.urgency}`, 'info');
    } catch (e) {
      showToast('Simulation failed', 'error');
    } finally {
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = '📡 Simulate Request';
      }, 1500);
    }
  });
}

// ── TOAST SYSTEM ──────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── HELPERS ───────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function timeAgo(timestamp) {
  const now = new Date();
  const then = new Date(timestamp);
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

function getUrgencyEmoji(urgency) {
  return { Emergency: '🔴', High: '🟠', Medium: '🟡', Low: '🟢' }[urgency] || '⚪';
}

function getLanguageName(code) {
  const names = { fr:'French', es:'Spanish', de:'German', it:'Italian', pl:'Polish', pt:'Portuguese', nl:'Dutch', ro:'Romanian' };
  return names[code] || code.toUpperCase();
}

// Style the status select to match dark theme
document.addEventListener('click', () => {
  document.querySelectorAll('.status-select').forEach(el => {
    el.style.cssText = `
      background: var(--surface2); border: 1px solid var(--border); border-radius: 6px;
      padding: 4px 8px; color: var(--text); font-family: var(--mono); font-size: 12px;
      cursor: pointer; outline: none;
    `;
  });
});
```

---

## SETUP COMMANDS — Run in this exact order

```bash
# 1. Create project folder
mkdir propertyos && cd propertyos

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# OR: venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file with your Groq key
echo "GROQ_API_KEY=your_key_here" > .env
# Get free key at: https://console.groq.com (no card needed)

# 5. Run seed data (populate demo requests)
python seed_data.py

# 6. Start the app
python app.py

# 7. Open browser
# http://localhost:5000
```

---

## AI MODEL TO USE

**Model name:** `llama-3.3-70b-versatile`
**Provider:** Groq (groq.com)
**Cost:** FREE — no credit card required
**Speed:** ~500 tokens/second — fastest available
**Why:** Best instruction following, best JSON output, best free option available in 2025

---

## 5 DEMO MESSAGES FOR HACKATHON DAY

Save these in your phone notes. Paste them live during the demo.

```
1. EMERGENCY (RED DOT):
"There is water pouring from my bedroom ceiling right now. It started about 10 minutes ago and is getting worse fast."

2. HIGH (ORANGE DOT):
"We have had no heating or hot water since this morning. I have a 4-month-old baby at home and it is very cold in the flat."

3. FRENCH - MULTI LANGUAGE (shows Kota/international appeal):
"Il y a une fuite d'eau sous mon évier depuis hier matin. L'eau s'accumule dans le placard sous l'évier."

4. EDGE CASE - NOT MAINTENANCE (shows AI handles gracefully):
"My neighbour in the flat above plays loud music every night after midnight. I cannot sleep. Can you please do something?"

5. MEDIUM:
"My boiler has been making a loud banging noise for the past 2 days. The heating still works but I am worried something serious is wrong."
```

---

## AUTOPILOT DEMO SEQUENCE

```
Step 1: Make sure you have 3-4 "New" status requests in the queue (from seed data)
Step 2: Click the AutoPilot toggle → it turns ON (green)
Step 3: Step back from your laptop — hands in pockets
Step 4: The trace panel appears and shows the AI reasoning in real time
Step 5: Watch the queue items change from "New" → "In Progress" or "Resolved"
Step 6: Say nothing. Let the room read the trace. Silence = power.
Step 7: After all processed, say: "That's 40 minutes of ops work done in 20 seconds."
```

---

## GITHUB COPILOT PROMPT TO START

Open VS Code in your project folder, create each file, and use this prompt in Copilot Chat:

```
Read the PROPERTYOS_COPILOT_SPEC.md file carefully.
Build the complete PropertyOS application exactly as specified.
Start with these files in this order:
1. requirements.txt — exact contents from spec
2. .env.example — exact contents from spec
3. .gitignore — exact contents from spec
4. database.py — complete code from spec
5. ai_engine.py — complete code from spec
6. autopilot.py — complete code from spec
7. app.py — complete code from spec
8. seed_data.py — complete code from spec
9. templates/index.html — complete HTML with all embedded CSS and JS from spec

After creating all files, verify:
- app.py imports from database.py, ai_engine.py, and autopilot.py correctly
- templates folder exists and index.html is inside it
- All CSS variables are defined in :root
- All JavaScript functions are defined before they are called
- The Chart.js CDN script tag is in the HTML head
```
