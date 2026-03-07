from __future__ import annotations

import json
from pathlib import Path


FAQ_FALLBACK_PATTERNS = {
    "wifi": ["wifi", "wi-fi", "internet password", "broadband"],
    "bin_collection": ["bin", "recycling", "waste collection"],
    "parking": ["parking permit", "parking fob", "parking"],
    "direct_debit": ["direct debit", "mandate", "standing order"],
    "move_in_checklist": ["move in", "move-in", "key collection", "checklist"],
}

STRONG_URGENCY_TERMS = {
    "leak",
    "electrical hazard",
    "no heating",
    "no hot water",
    "fire alarm",
    "mould",
    "damp",
    "rtb",
    "legal",
    "dispute",
    "still not fixed",
}

_MODULE_DIR = Path(__file__).resolve().parent


class _SafeFormatDict(dict):
    def __missing__(self, key):
        # Keep unknown placeholders untouched instead of raising KeyError.
        return "{" + str(key) + "}"


def _candidate_template_paths(path: str | None) -> list[Path]:
    if path:
        direct = Path(path)
        if direct.is_absolute():
            return [direct]
        return [direct, _MODULE_DIR / direct]

    return [
        _MODULE_DIR / "data" / "templates.json",
        _MODULE_DIR / "templates.json",
    ]


def load_templates(path: str | None = None) -> dict:
    for template_path in _candidate_template_paths(path):
        if not template_path.exists():
            continue
        try:
            data = json.loads(template_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _content_text(subject: str, body: str) -> str:
    return f"{subject or ''}\n{body or ''}".lower()


def match_faq_template(subject: str, body: str, templates: dict) -> str | None:
    text = _content_text(subject, body)

    patterns_by_template: dict[str, list[str]] = {}
    for template_id, payload in templates.items():
        if not isinstance(payload, dict):
            continue
        patterns = payload.get("patterns")
        if not isinstance(patterns, list):
            continue
        normalized = [str(p).lower().strip() for p in patterns if str(p).strip()]
        if normalized:
            patterns_by_template[template_id] = normalized

    if not patterns_by_template:
        patterns_by_template = FAQ_FALLBACK_PATTERNS

    for template_id, patterns in patterns_by_template.items():
        if any(pattern in text for pattern in patterns):
            return template_id

    return None


def _first_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return "there"
    return cleaned.split()[0]


def render_template_reply(template_id: str, context: dict, templates: dict) -> str:
    payload = templates.get(template_id, {}) if isinstance(templates, dict) else {}

    default_reply = (
        "Hi {first_name},\n\n"
        "Thanks for your message. Here is the requested information: {info_hint}.\n\n"
        "Best,\n{manager_name}"
    )
    default_context = _SafeFormatDict(
        {
            "first_name": context.get("first_name", "there"),
            "manager_name": context.get("manager_name", "Property Manager"),
            "property_name": context.get("property_name", "your property"),
            "info_hint": template_id.replace("_", " "),
        }
    )

    if not isinstance(payload, dict) or "body_template" not in payload:
        return default_reply.format_map(default_context)

    body_template = str(payload.get("body_template", "")).strip()
    if not body_template:
        return ""

    try:
        return body_template.format_map(default_context)
    except ValueError:
        # Malformed braces in template; use a safe generic fallback.
        return default_reply.format_map(default_context)


def evaluate_auto_resolve(thread_bundle: dict, templates: dict) -> dict:
    subject = str(thread_bundle.get("subject", "") or "")
    body = str(thread_bundle.get("thread_text", "") or "")

    template_id = match_faq_template(subject, body, templates)
    if not template_id:
        return {
            "is_auto": False,
            "template_id": None,
            "draft_reply": "",
            "handling_reason": "",
            "strong_signal_present": False,
        }

    text = _content_text(subject, body)
    strong_signal_present = any(term in text for term in STRONG_URGENCY_TERMS)

    context = {
        "first_name": _first_name(str(thread_bundle.get("latest_sender_name", "") or "")),
        "manager_name": str(thread_bundle.get("property_manager", "") or "Property Manager"),
        "property_name": str(thread_bundle.get("property_name", "") or "your property"),
    }
    draft_reply = render_template_reply(template_id, context, templates)

    if strong_signal_present:
        return {
            "is_auto": False,
            "template_id": template_id,
            "draft_reply": "",
            "handling_reason": f"FAQ matched ({template_id}) but strong urgency terms detected",
            "strong_signal_present": True,
        }

    if not draft_reply:
        return {
            "is_auto": False,
            "template_id": template_id,
            "draft_reply": "",
            "handling_reason": f"FAQ matched ({template_id}) but no valid template body found",
            "strong_signal_present": False,
        }

    return {
        "is_auto": True,
        "template_id": template_id,
        "draft_reply": draft_reply,
        "handling_reason": f"Matched FAQ template: {template_id}",
        "strong_signal_present": False,
    }
