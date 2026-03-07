"""auto_resolver.py — heuristics for instantly closing simple comms.

Identifies ultra-low-risk resident queries (e.g. Wi-Fi password, reference letters)
that can be answered with a pre-approved message and marked resolved without
human intervention.
"""

from textwrap import dedent

URGENCY_ORDER = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

PROPERTY_KNOWLEDGE = {
    "prop_001": {
        "name": "citynorth Quarter",
        "concierge": "CityNorth concierge desk",
        "concierge_phone": "+353 1 555 0100",
        "manager": "Sarah Brennan",
        "wifi_ssid": "CityNorth-Residents",
        "wifi_password": "StayCity2026!",
        "reference_sla": "24 hours",
    },
    "prop_002": {
        "name": "reds Works",
        "concierge": "On-site experience team",
        "concierge_phone": "+353 1 555 0200",
        "manager": "Conor Walsh",
        "wifi_ssid": "RedsWorks-Residents",
        "wifi_password": "RedsConnect2026",
        "reference_sla": "1 business day",
    },
    "prop_003": {
        "name": "Graylings",
        "concierge": "Graylings resident services",
        "concierge_phone": "+353 1 555 0300",
        "manager": "Aisling Murphy",
        "wifi_ssid": "Graylings-Living",
        "wifi_password": "GrayStay2026",
        "reference_sla": "24 hours",
    },
    "prop_004": {
        "name": "Ilah Residences",
        "concierge": "Ilah front-of-house team",
        "concierge_phone": "+353 1 555 0400",
        "manager": "Cormac Daly",
        "wifi_ssid": "Ilah-Residents",
        "wifi_password": "IlahConnect26",
        "reference_sla": "2 business days",
    },
    "prop_005": {
        "name": "Thornbury Village",
        "concierge": "Thornbury estate services",
        "concierge_phone": "+353 1 555 0500",
        "manager": "Orla Nolan",
        "wifi_ssid": "Thornbury-Residents",
        "wifi_password": "Thornbury2026",
        "reference_sla": "2 business days",
    },
    "default": {
        "name": "our managed community",
        "concierge": "the resident services team",
        "concierge_phone": "+353 1 555 0000",
        "manager": "PropertyOS Team",
        "wifi_ssid": "ManageCo-Residents",
        "wifi_password": "StayConnected2026",
        "reference_sla": "24 hours",
    },
}


def maybe_auto_resolve(email: dict, analysis: dict) -> dict | None:
    """Return auto-resolution payload dict if this email is resolvable."""
    urgency = (analysis.get("urgency") or "info").lower()
    if URGENCY_ORDER.get(urgency, 99) > URGENCY_ORDER["low"]:
        return None  # don't auto resolve anything medium or above

    combined_text = f"{email.get('subject', '')}\n{email.get('body', '')}".lower()
    info = _property_info(email)

    if _matches_wifi(combined_text):
        note = _wifi_note(email, info)
        return {"category": "wifi_credentials", "note": note}

    if _matches_reference_letter(combined_text):
        note = _reference_letter_note(email, info)
        return {"category": "reference_letter", "note": note}

    # If AI already decided no response is needed, upgrade to informational closure
    if not analysis.get("requires_response", True):
        note = _informational_closure(email, analysis, info)
        return {"category": "informational", "note": note}

    return None


def _property_info(email: dict) -> dict:
    frm = email.get("from", {})
    prop_id = frm.get("property_id")
    info = PROPERTY_KNOWLEDGE.get(prop_id, PROPERTY_KNOWLEDGE["default"]).copy()
    info.setdefault("name", frm.get("property_name") or PROPERTY_KNOWLEDGE["default"]["name"])
    return info


def _first_name(email: dict) -> str:
    name = email.get("from", {}).get("name") or "there"
    return name.split()[0]


def _matches_wifi(text: str) -> bool:
    if "wifi" not in text and "wi-fi" not in text and "wi fi" not in text:
        return False
    keywords = ["password", "login", "details", "credentials", "code"]
    return any(k in text for k in keywords)


def _matches_reference_letter(text: str) -> bool:
    if "reference" not in text:
        return False
    return any(k in text for k in ["letter", "mortgage", "bank", "landlord"])


def _wifi_note(email: dict, info: dict) -> str:
    first = _first_name(email)
    body = dedent(f"""
        Hi {first},
        
        I've re-shared the resident Wi-Fi credentials for {info['name']} so you can get online straight away:
        • Network: {info['wifi_ssid']}
        • Password: {info['wifi_password']}
        
        If anything still refuses to connect, the {info['concierge']} can reset the access points on {info['concierge_phone']}.
        We'll keep this ticket closed unless you reply to let us know there's still an issue.
        
        — Auto-resolved by PropertyOS Assistant
    """).strip()
    return body


def _reference_letter_note(email: dict, info: dict) -> str:
    first = _first_name(email)
    body = dedent(f"""
        Hi {first},
        
        I've drafted your landlord reference confirming your tenancy at {info['name']} and clean payment history. The signed PDF will be issued on letterhead and emailed to you within {info['reference_sla']}.
        If your lender needs it addressed to a specific person or reference number, just reply with those details and we'll update the document before sending.
        
        — Auto-resolved by PropertyOS Assistant
    """).strip()
    return body


def _informational_closure(email: dict, analysis: dict, info: dict) -> str:
    first = _first_name(email)
    summary = analysis.get("ai_summary") or "Your note has been logged."
    body = dedent(f"""
        Hi {first},
        
        We've logged your message and there is no further action required right now. Summary for our records:
        {summary}
        
        If anything changes, reply to this email and we'll reopen the ticket immediately.
        
        — Auto-resolved by PropertyOS Assistant
    """).strip()
    return body
