"""
database.py — All SQLite logic for PropertyOS
Zero SQL outside this file.
"""

import sqlite3
import os
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
