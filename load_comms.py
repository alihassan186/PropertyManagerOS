"""
load_comms.py — One-time script to load 100 emails from JSON, run AI analysis,
               and populate the comms database tables.

Run: python load_comms.py
Expected time: ~6 minutes for 100 emails (Groq rate limit aware)
"""

import json
import os
import sys
import time
from collections import defaultdict

# Ensure we're in the right directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

import database
import comms_engine

JSON_FILE = os.path.join(script_dir, "proptech-test-data.json")
FALLBACK_JSON = os.path.join(script_dir, "proptech-test-data_(1).json")


def load_json():
    """Load the email dataset."""
    path = JSON_FILE if os.path.exists(JSON_FILE) else FALLBACK_JSON
    if not os.path.exists(path):
        print(f"❌ JSON file not found: {path}")
        sys.exit(1)
    print(f"📂 Loading data from: {os.path.basename(path)}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("emails", []), data.get("metadata", {})


def process_emails(emails):
    """
    Step 1: Save all emails to DB.
    Step 2: Run AI analysis on each email.
    Step 3: Generate action items for high-priority emails.
    """
    database.init_comms_tables()
    print(f"✅ Database tables ready")
    print(f"📧 Processing {len(emails)} emails...\n")

    # ── Step 1: Save all emails ──────────────────────────────────────────
    print("=" * 60)
    print("STEP 1/3 — Saving emails to database")
    print("=" * 60)
    for i, email in enumerate(emails, 1):
        database.save_communication(email)
        if i % 10 == 0:
            print(f"  Saved {i}/{len(emails)} emails...")
    print(f"✅ All {len(emails)} emails saved to DB\n")

    # ── Step 2: AI analysis ──────────────────────────────────────────────
    print("=" * 60)
    print("STEP 2/3 — Running AI analysis on each email (~6 mins)")
    print("=" * 60)

    critical_emails = []
    errors = []

    for i, email in enumerate(emails, 1):
        email_id = email.get("id", f"email_{i:03d}")
        subject = email.get("subject", "")[:55]
        frm = email.get("from", {})
        sender_type = frm.get("type", "unknown")

        print(f"  [{i:3d}/{len(emails)}] {email_id} — {subject[:40]}...")

        try:
            analysis = comms_engine.analyse_email(email)
            database.update_communication_ai(email_id, analysis)

            urgency = analysis.get("urgency", "info")
            score = analysis.get("urgency_score", 0)
            flags = analysis.get("flags", [])

            flag_str = ""
            if "welfare_check_needed" in flags:
                flag_str += " 🚨 WELFARE"
            if "legal_exposure" in flags:
                flag_str += " ⚖️ LEGAL"
            if "media_risk" in flags:
                flag_str += " 📺 MEDIA"
            if "vulnerable_tenant" in flags:
                flag_str += " 👶 VULNERABLE"

            urgency_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}.get(urgency, "⚪")
            print(f"        → {urgency_icon} {urgency.upper()} ({score}) [{sender_type}]{flag_str}")

            if urgency in ("critical", "high"):
                critical_emails.append((email, analysis))

            # Rate limiting: 1 second delay between calls
            time.sleep(1.0)

        except Exception as e:
            print(f"        ❌ Error: {e}")
            errors.append((email_id, str(e)))
            time.sleep(2.0)  # Extra pause on error

    print(f"\n✅ AI analysis complete. {len(critical_emails)} critical/high emails. {len(errors)} errors.\n")

    # ── Step 3: Action items ─────────────────────────────────────────────
    print("=" * 60)
    print("STEP 3/3 — Generating action items for priority emails")
    print("=" * 60)

    action_count = 0
    for email, analysis in critical_emails:
        email_id = email.get("id")
        frm = email.get("from", {})
        print(f"  Generating actions for {email_id}...")
        try:
            items = comms_engine.generate_action_items(email, analysis)
            for item in items:
                item["email_id"] = email_id
                item["thread_id"] = email.get("thread_id")
                item["property_id"] = frm.get("property_id")
                item["from_unit"] = frm.get("unit")
                database.save_action_item(item)
                action_count += 1
            time.sleep(1.0)
        except Exception as e:
            print(f"  ❌ Action item error for {email_id}: {e}")
            time.sleep(2.0)

    print(f"✅ {action_count} action items generated\n")
    return critical_emails, errors


def process_threads(emails):
    """Group emails by thread_id, run thread analysis on multi-email threads."""
    print("=" * 60)
    print("STEP 4/4 — Thread analysis")
    print("=" * 60)

    # Group by thread
    thread_map = defaultdict(list)
    for email in emails:
        tid = email.get("thread_id", email.get("id"))
        thread_map[tid].append(email)

    thread_count = 0
    for thread_id, thread_emails in thread_map.items():
        # Determine subject & property from first email
        first = thread_emails[0]
        frm = first.get("from", {})
        subject = first.get("subject", "")
        property_id = frm.get("property_id")

        # Sort by thread position
        thread_emails_sorted = sorted(thread_emails, key=lambda x: x.get("thread_position", 1))

        # Build participant list
        participants = list({e.get("from", {}).get("name", "") for e in thread_emails if e.get("from", {}).get("name")})
        last_email_at = max((e.get("timestamp", "") for e in thread_emails), default="")

        if len(thread_emails_sorted) > 1:
            # Run thread-level AI analysis
            print(f"  🧵 Thread {thread_id} ({len(thread_emails_sorted)} emails): {subject[:40]}...")
            try:
                thread_analysis = comms_engine.analyse_thread(thread_emails_sorted)
                thread_data = {
                    "thread_id": thread_id,
                    "subject": subject,
                    "property_id": property_id,
                    "email_count": len(thread_emails_sorted),
                    "participants": participants,
                    "thread_urgency": thread_analysis.get("thread_urgency"),
                    "thread_urgency_score": thread_analysis.get("thread_urgency_score", 0),
                    "thread_summary": thread_analysis.get("thread_summary"),
                    "thread_status": thread_analysis.get("thread_status", "Open"),
                    "recommended_action": thread_analysis.get("recommended_action"),
                    "key_facts": thread_analysis.get("key_facts", []),
                    "escalation_risk": thread_analysis.get("escalation_risk", "low"),
                    "escalation_reason": thread_analysis.get("escalation_reason"),
                    "last_email_at": last_email_at,
                }
                database.save_thread(thread_data)
                risk = thread_analysis.get("escalation_risk", "low")
                status = thread_analysis.get("thread_status", "Open")
                score = thread_analysis.get("thread_urgency_score", 0)
                print(f"     → score: {score}, status: {status}, escalation: {risk}")
                time.sleep(1.0)
                thread_count += 1
            except Exception as e:
                print(f"  ❌ Thread analysis error for {thread_id}: {e}")
                # Save basic thread info anyway
                database.save_thread({
                    "thread_id": thread_id,
                    "subject": subject,
                    "property_id": property_id,
                    "email_count": len(thread_emails_sorted),
                    "participants": participants,
                    "last_email_at": last_email_at,
                })
                time.sleep(2.0)
        else:
            # Single-email thread — save basic info without separate AI call
            database.save_thread({
                "thread_id": thread_id,
                "subject": subject,
                "property_id": property_id,
                "email_count": 1,
                "participants": participants,
                "last_email_at": last_email_at,
            })

    print(f"✅ {thread_count} multi-email threads fully analysed\n")


def print_summary():
    """Print final summary stats."""
    analytics = database.get_comms_analytics()
    print("=" * 60)
    print("✅ COMMS INTELLIGENCE LOADED SUCCESSFULLY")
    print("=" * 60)
    print(f"  📧 Total emails:    {analytics['total']}")
    print(f"  📬 Unread:          {analytics['unread']}")
    print(f"  🔴 Critical:        {analytics['critical']}")
    print(f"  🟠 High:            {analytics['high']}")
    print(f"  🚨 Welfare checks:  {analytics['welfare_checks']}")
    print(f"  ✅ Open actions:    {analytics['open_actions']}")
    print(f"  ⚖️  Legal exposure:  {analytics['legal_exposure']}")
    print(f"  📺 Media risk:      {analytics['media_risk']}")
    print("")
    print("  By sender type:")
    for t, c in analytics.get("by_sender_type", {}).items():
        print(f"    {t}: {c}")
    print("")
    print("▶  Start the app:  python app.py")
    print("▶  Open browser:   http://localhost:5000")
    print("▶  Click:          Comms Intelligence in the sidebar")
    print("=" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🏠 PropertyOS — Comms Intelligence Loader")
    print("=" * 60 + "\n")

    emails, metadata = load_json()
    critical_emails, errors = process_emails(emails)
    process_threads(emails)
    print_summary()
