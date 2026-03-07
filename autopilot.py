"""
autopilot.py — AutoPilot autonomous agent for PropertyOS
Background threading loop that processes the entire New request queue
without human input.
"""

import threading
import time
from datetime import datetime


# ─── Module-level state ─────────────────────────────────────────────────────────

_running = False
_thread = None
_trace = []          # list of trace-entry dicts
_lock = threading.Lock()
_trace_listeners = []  # SSE queue objects


# ─── Public API ─────────────────────────────────────────────────────────────────

def start():
    """Start the AutoPilot background thread."""
    global _running, _thread, _trace
    with _lock:
        if _running:
            return
        _running = True
        _trace = []
        _thread = threading.Thread(target=_run_loop, daemon=True)
        _thread.start()


def stop():
    """Signal AutoPilot to stop after its current request."""
    global _running
    with _lock:
        _running = False


def is_running() -> bool:
    return _running


def get_trace() -> list:
    """Return a copy of all trace entries so far."""
    with _lock:
        return list(_trace)


def add_trace(message: str, icon: str = "🤖"):
    """Add a timestamped entry to the trace log and notify listeners."""
    ts = datetime.now().strftime("%H:%M:%S")
    entry = {"ts": ts, "icon": icon, "message": message}
    with _lock:
        _trace.append(entry)
        for q in _trace_listeners:
            q.put(entry)


def register_listener(queue):
    """Register an SSE queue to receive live trace entries."""
    with _lock:
        _trace_listeners.append(queue)


def unregister_listener(queue):
    """Remove an SSE queue."""
    with _lock:
        if queue in _trace_listeners:
            _trace_listeners.remove(queue)


# ─── Internal loop ──────────────────────────────────────────────────────────────

def _run_loop():
    """
    Main AutoPilot loop.
    Imports inside function to avoid circular imports at module load time.
    """
    global _running

    from database import get_new_requests, update_request_full
    from ai_engine import autopilot_process, generate_reply

    add_trace("AutoPilot activated — scanning request queue...", "🤖")
    time.sleep(0.6)

    new_requests = get_new_requests()

    if not new_requests:
        add_trace("No New requests in queue — nothing to do.", "✅")
        with _lock:
            _running = False
        return

    add_trace(f"Found {len(new_requests)} New request(s). Starting processing...", "📋")
    time.sleep(0.4)

    for req in new_requests:
        if not _running:
            add_trace("AutoPilot stopped by user.", "🛑")
            break

        apt = req.get("apartment_ref") or "Unknown unit"
        preview = req["tenant_message"][:60] + ("..." if len(req["tenant_message"]) > 60 else "")
        add_trace(f"Reading: {apt} — \"{preview}\"", "📋")
        time.sleep(0.5)

        add_trace("Analysing urgency and category...", "🧠")
        time.sleep(0.3)

        try:
            result = autopilot_process(req["tenant_message"], req.get("apartment_ref"))
        except Exception as e:
            add_trace(f"AI error on request #{req['id']}: {str(e)}", "❌")
            continue

        urgency = result.get("urgency", "Medium")
        category = result.get("category", "Other")
        add_trace(f"Urgency: {urgency} | Category: {category}", "⚡")
        time.sleep(0.3)

        reasoning = result.get("reasoning", "See contractor brief.")
        add_trace(f"Reasoning: {reasoning}", "💭")
        time.sleep(0.3)

        add_trace("Generating contractor brief...", "📝")
        time.sleep(0.5)

        add_trace("Drafting tenant reply...", "💬")
        time.sleep(0.3)

        try:
            triage_data = {
                "urgency": urgency,
                "category": category,
                "response_time": result.get("response_time", "Within 24 hours"),
                "tenant_advice": result.get("tenant_advice", ""),
                "language_detected": req.get("language_detected", "en"),
            }
            ai_reply = generate_reply(req["tenant_message"], triage_data)
        except Exception:
            ai_reply = "Thank you for your message. We have received your request and will follow up shortly."

        add_trace("Tenant reply drafted and saved.", "✉️")
        time.sleep(0.3)

        new_status = result.get("new_status", "In Progress")
        update_request_full(
            request_id=req["id"],
            urgency=urgency,
            category=category,
            contractor_brief=result.get("contractor_brief", ""),
            tenant_advice=result.get("tenant_advice", ""),
            response_time=result.get("response_time", "Within 24 hours"),
            ai_reply=ai_reply,
            status=new_status,
            language_detected=req.get("language_detected"),
        )

        add_trace(f"Status updated: New → {new_status}", "✅")
        time.sleep(0.4)
        add_trace("─" * 40, "")
        time.sleep(0.3)

    if _running:
        add_trace("Queue clear — all requests processed.", "✅")

    with _lock:
        _running = False
