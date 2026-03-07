"""
database.py — All SQLite logic for PropertyOS
Zero SQL outside this file.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "propertyos.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_message    TEXT    NOT NULL,
            urgency           TEXT    NOT NULL,
            category          TEXT    NOT NULL,
            contractor_brief  TEXT    NOT NULL,
            tenant_advice     TEXT    NOT NULL,
            response_time     TEXT    NOT NULL,
            ai_reply          TEXT,
            status            TEXT    NOT NULL DEFAULT 'New',
            language_detected TEXT,
            apartment_ref     TEXT,
            created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def create_request(
    tenant_message,
    urgency,
    category,
    contractor_brief,
    tenant_advice,
    response_time,
    language_detected=None,
    apartment_ref=None,
    status="New",
):
    """Insert a new request and return the full record."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO requests
            (tenant_message, urgency, category, contractor_brief, tenant_advice,
             response_time, language_detected, apartment_ref, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_message,
            urgency,
            category,
            contractor_brief,
            tenant_advice,
            response_time,
            language_detected,
            apartment_ref,
            status,
            now,
            now,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return get_request_by_id(new_id)


def get_all_requests():
    """Return all requests, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_request_by_id(request_id):
    """Return a single request or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def update_status(request_id, status):
    """Update request status. Returns updated object or None."""
    valid = {"New", "In Progress", "Resolved"}
    if status not in valid:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE requests SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, request_id),
    )
    conn.commit()
    conn.close()
    return get_request_by_id(request_id)


def update_reply(request_id, ai_reply):
    """Store generated AI tenant reply."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE requests SET ai_reply = ?, updated_at = ? WHERE id = ?",
        (ai_reply, now, request_id),
    )
    conn.commit()
    conn.close()
    return get_request_by_id(request_id)


def update_request_full(request_id, urgency, category, contractor_brief,
                         tenant_advice, response_time, ai_reply, status,
                         language_detected=None):
    """Full update used by AutoPilot after processing."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        UPDATE requests SET
            urgency           = ?,
            category          = ?,
            contractor_brief  = ?,
            tenant_advice     = ?,
            response_time     = ?,
            ai_reply          = ?,
            status            = ?,
            language_detected = ?,
            updated_at        = ?
        WHERE id = ?
        """,
        (urgency, category, contractor_brief, tenant_advice, response_time,
         ai_reply, status, language_detected, now, request_id),
    )
    conn.commit()
    conn.close()
    return get_request_by_id(request_id)


def get_analytics():
    """Aggregated stats for dashboard charts."""
    conn = get_connection()
    cursor = conn.cursor()

    # Urgency breakdown
    cursor.execute(
        "SELECT urgency, COUNT(*) as count FROM requests GROUP BY urgency"
    )
    urgency_rows = cursor.fetchall()
    urgency_counts = {r["urgency"]: r["count"] for r in urgency_rows}

    # Category breakdown
    cursor.execute(
        "SELECT category, COUNT(*) as count FROM requests GROUP BY category ORDER BY count DESC"
    )
    category_rows = cursor.fetchall()

    # Status breakdown
    cursor.execute(
        "SELECT status, COUNT(*) as count FROM requests GROUP BY status"
    )
    status_rows = cursor.fetchall()
    status_counts = {r["status"]: r["count"] for r in status_rows}

    # Resolved today
    cursor.execute(
        """SELECT COUNT(*) as count FROM requests
           WHERE status = 'Resolved'
           AND DATE(updated_at) = DATE('now')"""
    )
    resolved_today = cursor.fetchone()["count"]

    # Total requests
    cursor.execute("SELECT COUNT(*) as count FROM requests")
    total = cursor.fetchone()["count"]

    # Emergency count
    cursor.execute(
        "SELECT COUNT(*) as count FROM requests WHERE urgency = 'Emergency' AND status != 'Resolved'"
    )
    active_emergency = cursor.fetchone()["count"]

    # High count
    cursor.execute(
        "SELECT COUNT(*) as count FROM requests WHERE urgency = 'High' AND status != 'Resolved'"
    )
    active_high = cursor.fetchone()["count"]

    conn.close()

    return {
        "total": total,
        "urgency_counts": urgency_counts,
        "category_counts": [
            {"category": r["category"], "count": r["count"]} for r in category_rows
        ],
        "status_counts": status_counts,
        "resolved_today": resolved_today,
        "active_emergency": active_emergency,
        "active_high": active_high,
    }


def delete_all_requests():
    """Wipe all requests. Used by seed_data.py."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM requests")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='requests'")
    conn.commit()
    conn.close()


def get_new_requests():
    """Return all requests with status = 'New' (for AutoPilot)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM requests WHERE status = 'New' ORDER BY created_at ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


# ─── Comms Intelligence Tables ──────────────────────────────────────────────────

def init_comms_tables():
    """Create comms tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS communications (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id            TEXT UNIQUE NOT NULL,
            thread_id           TEXT,
            thread_position     INTEGER DEFAULT 1,
            timestamp           TEXT,
            from_name           TEXT,
            from_email          TEXT,
            from_type           TEXT,
            from_unit           TEXT,
            from_property_id    TEXT,
            to_address          TEXT,
            subject             TEXT,
            body                TEXT,
            attachments         TEXT DEFAULT '[]',
            read                INTEGER DEFAULT 0,
            urgency             TEXT,
            urgency_score       INTEGER DEFAULT 0,
            category            TEXT,
            ai_summary          TEXT,
            recommended_action  TEXT,
            action_deadline     TEXT,
            action_owner        TEXT,
            sentiment           TEXT,
            requires_response   INTEGER DEFAULT 1,
            flags               TEXT DEFAULT '[]',
            welfare_check_needed INTEGER DEFAULT 0,
            auto_resolved       INTEGER DEFAULT 0,
            auto_resolution_note TEXT,
            auto_resolution_category TEXT,
            auto_resolved_at    TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comms_threads (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id           TEXT UNIQUE NOT NULL,
            subject             TEXT,
            property_id         TEXT,
            email_count         INTEGER DEFAULT 1,
            participants        TEXT DEFAULT '[]',
            thread_urgency      TEXT,
            thread_urgency_score INTEGER DEFAULT 0,
            thread_summary      TEXT,
            thread_status       TEXT DEFAULT 'Open',
            recommended_action  TEXT,
            key_facts           TEXT DEFAULT '[]',
            escalation_risk     TEXT DEFAULT 'low',
            escalation_reason   TEXT,
            last_email_at       TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id            TEXT,
            thread_id           TEXT,
            title               TEXT NOT NULL,
            description         TEXT,
            action_owner        TEXT,
            urgency_score       INTEGER DEFAULT 50,
            urgency             TEXT DEFAULT 'medium',
            deadline            TEXT,
            status              TEXT DEFAULT 'open',
            property_id         TEXT,
            from_unit           TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Backfill columns for existing installs (SQLite ignores duplicate add column)
    safety_alters = [
        "ALTER TABLE communications ADD COLUMN auto_resolved INTEGER DEFAULT 0",
        "ALTER TABLE communications ADD COLUMN auto_resolution_note TEXT",
        "ALTER TABLE communications ADD COLUMN auto_resolution_category TEXT",
        "ALTER TABLE communications ADD COLUMN auto_resolved_at TEXT",
    ]
    for statement in safety_alters:
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise

    conn.commit()
    conn.close()


def save_communication(email_data: dict) -> dict:
    """Insert a communication record. Skips if email_id already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    frm = email_data.get("from", {})
    attachments = email_data.get("attachments", [])
    cursor.execute("""
        INSERT OR IGNORE INTO communications
            (email_id, thread_id, thread_position, timestamp,
             from_name, from_email, from_type, from_unit, from_property_id,
             to_address, subject, body, attachments, read)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        email_data.get("id"),
        email_data.get("thread_id"),
        email_data.get("thread_position", 1),
        email_data.get("timestamp"),
        frm.get("name"),
        frm.get("email"),
        frm.get("type"),
        frm.get("unit"),
        frm.get("property_id"),
        email_data.get("to"),
        email_data.get("subject"),
        email_data.get("body"),
        json.dumps(attachments),
        1 if email_data.get("read") else 0,
    ))
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return get_communication_by_email_id(email_data.get("id"))


def update_communication_ai(email_id: str, ai_data: dict):
    """Store AI analysis results on a communication record."""
    conn = get_connection()
    cursor = conn.cursor()
    flags = ai_data.get("flags", [])
    welfare = 1 if "welfare_check_needed" in flags else 0
    cursor.execute("""
        UPDATE communications SET
            urgency             = ?,
            urgency_score       = ?,
            category            = ?,
            ai_summary          = ?,
            recommended_action  = ?,
            action_deadline     = ?,
            action_owner        = ?,
            sentiment           = ?,
            requires_response   = ?,
            flags               = ?,
            welfare_check_needed = ?
        WHERE email_id = ?
    """, (
        ai_data.get("urgency"),
        ai_data.get("urgency_score", 0),
        ai_data.get("category"),
        ai_data.get("ai_summary"),
        ai_data.get("recommended_action"),
        ai_data.get("action_deadline"),
        ai_data.get("action_owner"),
        ai_data.get("sentiment"),
        1 if ai_data.get("requires_response") else 0,
        json.dumps(flags),
        welfare,
        email_id,
    ))
    conn.commit()
    conn.close()


def mark_communication_auto_resolved(email_id: str, note: str, category: str = None) -> dict:
    """Flag a communication as auto-resolved with a professional note."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE communications SET
            auto_resolved = 1,
            auto_resolution_note = ?,
            auto_resolution_category = ?,
            auto_resolved_at = COALESCE(auto_resolved_at, CURRENT_TIMESTAMP),
            requires_response = 0
        WHERE email_id = ?
    """, (note, category, email_id))
    conn.commit()
    conn.close()
    return get_communication_by_email_id(email_id)


def save_thread(thread_data: dict):
    """Insert or update a thread record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comms_threads
            (thread_id, subject, property_id, email_count, participants,
             thread_urgency, thread_urgency_score, thread_summary, thread_status,
             recommended_action, key_facts, escalation_risk, escalation_reason, last_email_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(thread_id) DO UPDATE SET
            subject             = excluded.subject,
            property_id         = excluded.property_id,
            email_count         = excluded.email_count,
            participants        = excluded.participants,
            thread_urgency      = excluded.thread_urgency,
            thread_urgency_score = excluded.thread_urgency_score,
            thread_summary      = excluded.thread_summary,
            thread_status       = excluded.thread_status,
            recommended_action  = excluded.recommended_action,
            key_facts           = excluded.key_facts,
            escalation_risk     = excluded.escalation_risk,
            escalation_reason   = excluded.escalation_reason,
            last_email_at       = excluded.last_email_at
    """, (
        thread_data.get("thread_id"),
        thread_data.get("subject"),
        thread_data.get("property_id"),
        thread_data.get("email_count", 1),
        json.dumps(thread_data.get("participants", [])),
        thread_data.get("thread_urgency"),
        thread_data.get("thread_urgency_score", 0),
        thread_data.get("thread_summary"),
        thread_data.get("thread_status", "Open"),
        thread_data.get("recommended_action"),
        json.dumps(thread_data.get("key_facts", [])),
        thread_data.get("escalation_risk", "low"),
        thread_data.get("escalation_reason"),
        thread_data.get("last_email_at"),
    ))
    conn.commit()
    conn.close()


def save_action_item(action_data: dict) -> dict:
    """Insert an action item and return the saved record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO action_items
            (email_id, thread_id, title, description, action_owner,
             urgency_score, urgency, deadline, status, property_id, from_unit)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        action_data.get("email_id"),
        action_data.get("thread_id"),
        action_data.get("title"),
        action_data.get("description"),
        action_data.get("action_owner"),
        action_data.get("urgency_score", 50),
        action_data.get("urgency", "medium"),
        action_data.get("deadline"),
        action_data.get("status", "open"),
        action_data.get("property_id"),
        action_data.get("from_unit"),
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return get_action_item_by_id(new_id)


def get_action_item_by_id(item_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM action_items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def update_action_item_status(item_id: int, status: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()
    return get_action_item_by_id(item_id)


def get_communication_by_email_id(email_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM communications WHERE email_id = ?", (email_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def get_communication_by_id(comm_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM communications WHERE id = ?", (comm_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def get_all_communications() -> list:
    """Return all communications ordered by urgency_score desc, then timestamp desc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM communications
        ORDER BY urgency_score DESC, timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_thread_emails(thread_id: str) -> list:
    """Return all emails in a thread, ordered by position."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM communications
        WHERE thread_id = ?
        ORDER BY thread_position ASC
    """, (thread_id,))
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_all_threads() -> list:
    """Return all threads on urgency score desc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM comms_threads
        ORDER BY thread_urgency_score DESC, last_email_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_all_action_items() -> list:
    """Return all action items ordered by urgency_score desc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM action_items
        ORDER BY urgency_score DESC, created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_comms_analytics() -> dict:
    """Aggregated stats for Comms Intelligence dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as c FROM communications")
    total = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE read = 0")
    unread = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE urgency = 'critical'")
    critical = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE urgency = 'high'")
    high = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE welfare_check_needed = 1")
    welfare = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM action_items WHERE status = 'open'")
    open_actions = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT from_type, COUNT(*) as c
        FROM communications
        GROUP BY from_type ORDER BY c DESC
    """)
    by_type = {(r["from_type"] or "unknown"): r["c"] for r in cursor.fetchall()}

    cursor.execute("""
        SELECT urgency, COUNT(*) as c
        FROM communications
        WHERE urgency IS NOT NULL
        GROUP BY urgency ORDER BY c DESC
    """)
    by_urgency = {r["urgency"]: r["c"] for r in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE urgency IS NULL")
    uncategorized = cursor.fetchone()["c"]

    by_priority = {
        "critical": by_urgency.get("critical", 0),
        "important": by_urgency.get("high", 0),
        "medium": by_urgency.get("medium", 0),
        "low": by_urgency.get("low", 0) + by_urgency.get("info", 0) + uncategorized,
    }

    cursor.execute("""
        SELECT from_property_id, COUNT(*) as c
        FROM communications
        GROUP BY from_property_id ORDER BY c DESC
    """)
    by_property = {(r["from_property_id"] or "unknown"): r["c"] for r in cursor.fetchall()}

    cursor.execute("""
        SELECT COUNT(*) as c FROM communications WHERE flags LIKE '%legal_exposure%'
    """)
    legal = cursor.fetchone()["c"]

    cursor.execute("""
        SELECT COUNT(*) as c FROM communications WHERE flags LIKE '%media_risk%'
    """)
    media = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) as c FROM communications WHERE auto_resolved = 1")
    auto_resolved = cursor.fetchone()["c"]

    conn.close()

    return {
        "total": total,
        "unread": unread,
        "critical": critical,
        "high": high,
        "welfare_checks": welfare,
        "open_actions": open_actions,
        "by_sender_type": by_type,
        "by_urgency": by_urgency,
        "by_priority": by_priority,
        "by_property": by_property,
        "legal_exposure": legal,
        "media_risk": media,
        "auto_resolved": auto_resolved,
    }
