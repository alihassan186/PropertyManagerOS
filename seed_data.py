"""
seed_data.py — Load 8 demo requests into the database.
Run once: python seed_data.py
"""

import sys
import os

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import database
from ai_engine import triage_request

SEED_REQUESTS = [
    {
        "message": "Water is pouring from my bedroom ceiling right now. It started 10 minutes ago and is getting worse.",
        "apt": "Apt 4B",
        "status": "New",
    },
    {
        "message": "No heating or hot water since this morning. I have a 4-month-old baby and it is very cold.",
        "apt": "Apt 2A",
        "status": "In Progress",
    },
    {
        "message": "Boiler making loud banging noise for 2 days. Heating still works but I am worried something is wrong.",
        "apt": "Apt 7C",
        "status": "New",
    },
    {
        "message": "The kitchen tap has been dripping constantly since last week. It keeps me awake at night.",
        "apt": "Apt 1D",
        "status": "New",
    },
    {
        "message": "Kitchen cupboard door hinge is broken. The door just hangs off now.",
        "apt": "Apt 9A",
        "status": "Resolved",
    },
    {
        "message": "Il y a une fuite d'eau sous mon évier depuis hier. L'eau s'accumule dans le placard en dessous.",
        "apt": "Apt 3F",
        "status": "New",
    },
    {
        "message": "My neighbour plays loud music every night after midnight. I cannot sleep and I have work early.",
        "apt": "Apt 6B",
        "status": "New",
    },
    {
        "message": "I found mouse droppings behind the fridge and under the sink. There may be more.",
        "apt": "Apt 5C",
        "status": "In Progress",
    },
]


def run():
    print("🗑  Clearing existing requests...")
    database.init_db()
    database.delete_all_requests()
    print("✅  Database cleared.\n")

    for i, item in enumerate(SEED_REQUESTS, 1):
        msg = item["message"]
        apt = item["apt"]
        status = item["status"]
        print(f"[{i}/8] Triaging: {apt} — {msg[:55]}...")

        try:
            result = triage_request(msg, apt)
        except Exception as e:
            print(f"  ❌ AI error: {e}")
            continue

        record = database.create_request(
            tenant_message=msg,
            urgency=result["urgency"],
            category=result["category"],
            contractor_brief=result["contractor_brief"],
            tenant_advice=result["tenant_advice"],
            response_time=result["response_time"],
            language_detected=result.get("language_detected"),
            apartment_ref=apt,
            status=status,
        )
        print(f"  ✅ #{record['id']} | {result['urgency']} | {result['category']} | {status}")

    print("\n🚀 Seed complete — 8 requests loaded.")
    print("   Run:  python app.py  →  http://localhost:5000")


if __name__ == "__main__":
    run()
