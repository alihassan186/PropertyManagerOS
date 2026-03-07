"""
comms_engine.py — AI functions for Comms Intelligence module
Model: llama-3.3-70b-versatile via Groq (FREE)
Processes 100 emails: sender ID, thread context, urgency scoring, actions.
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# ─── Prompts ─────────────────────────────────────────────────────────────────────

COMMS_ANALYSIS_PROMPT = """You are an AI assistant for a property management company.
Analyse this email and return ONLY valid JSON with no preamble, no explanation, no markdown fences.

Return exactly this JSON structure:
{
  "urgency": "critical" | "high" | "medium" | "low" | "info",
  "urgency_score": <integer 0-100>,
  "category": "<category>",
  "ai_summary": "<2-3 sentence summary of what this email is about and what action is needed>",
  "recommended_action": "<Specific, actionable instruction for the property manager>",
  "action_deadline": "<e.g. Immediate, Within 2 hours, Within 24 hours, Within 3 days, Within 1 week, No deadline>",
  "action_owner": "<e.g. Property Manager, Maintenance Team, Landlord, Accounts, Legal Team, Concierge>",
  "sentiment": "<positive | neutral | concerned | frustrated | angry | urgent>",
  "requires_response": <true | false>,
  "flags": [<array of applicable flag strings from list below>]
}

Urgency scoring:
  critical (80-100): active safety, welfare emergencies, fire/flood/gas, building failure, someone missing
  high (60-79):     RTB/HSE/legal notices, no heat with vulnerable persons, water damage, security breach
  medium (30-59):   maintenance requests, arrears, complaints, lease queries, contractor invoices
  low (10-29):      general enquiries, minor requests, routine reports, viewing requests
  info (0-9):       system messages, newsletters, automated alerts with no action needed

Available flags (include only applicable ones):
  welfare_check_needed   - person not seen 7+ days, strange smell, post piling up, concern for neighbour
  legal_exposure         - RTB filing, solicitor letter, HSE inspection, formal legal notice
  media_risk             - RTE, press enquiry, journalist, broadcast, social media threat
  vulnerable_tenant      - elderly, infant, disability, medical condition, mental health
  recurring_issue        - same problem reported multiple times, painted over, ongoing issue
  financial_risk         - overdue invoice, insurance claim, rent arrears, compensation demand
  deadline_imminent      - action needed within 7 days mentioned explicitly

Category options: Maintenance | Legal | Compliance | Tenant Welfare | Security | Finance | Leasing | Internal | Contractor | Media | System Alert | Other

CRITICAL: Return ONLY the JSON object. No other text."""

THREAD_ANALYSIS_PROMPT = """You are an AI assistant for a property management company.
Analyse this email THREAD (multiple emails in one conversation) and return ONLY valid JSON.

Return exactly this JSON structure:
{
  "thread_urgency": "critical" | "high" | "medium" | "low" | "info",
  "thread_urgency_score": <integer 0-100>,
  "thread_summary": "<3-4 sentences describing the full conversation, current status, and what the PM needs to know>",
  "thread_status": "Open" | "In Progress" | "Awaiting Response" | "Resolved" | "Escalating",
  "recommended_action": "<specific action for PM based on the full thread context>",
  "key_facts": [<array of 3-5 key fact strings extracted from the thread>],
  "participants": [<array of participant names/roles>],
  "escalation_risk": "low" | "medium" | "high",
  "escalation_reason": "<one sentence explaining why this could escalate, or null if low risk>"
}

CRITICAL: Return ONLY the JSON object. No other text."""

REPLY_DRAFT_PROMPT = """You are a professional and empathetic property manager.
Draft a concise, warm professional reply to this email.
Rules:
- Under 120 words
- Professional but warm tone
- Acknowledge the issue specifically
- State what action will be taken and when
- Do NOT use generic phrases like "Thank you for contacting us"
- Plain text, no subject line, no signature
- If this is an emergency or welfare concern, prioritise urgency in language"""

ACTION_ITEMS_PROMPT = """You are an AI property operations assistant.
Based on this email analysis, generate concrete action items.
Return ONLY a JSON array of action items:
[
  {
    "title": "<short action title, max 8 words>",
    "description": "<one sentence describing exactly what needs to be done>",
    "action_owner": "<Property Manager | Maintenance | Accounts | Legal | Concierge | Emergency Services>",
    "urgency_score": <0-100>,
    "urgency": "<critical | high | medium | low>",
    "deadline": "<Immediate | Within 2 hours | Within 24 hours | Within 3 days | Within 1 week>"
  }
]
Generate 1-3 action items. For critical/welfare emails generate 2-3. Return ONLY the JSON array."""


# ─── Core Functions ──────────────────────────────────────────────────────────────

def analyse_email(email: dict) -> dict:
    """
    Run AI analysis on a single email.
    Returns dict with urgency, urgency_score, ai_summary, flags, etc.
    """
    frm = email.get("from", {})
    email_content = f"""From: {frm.get('name')} <{frm.get('email')}> [{frm.get('type', 'unknown')}]
Unit: {frm.get('unit', 'N/A')} | Property: {frm.get('property_id', 'N/A')}
Subject: {email.get('subject', '')}
Date: {email.get('timestamp', '')}

{email.get('body', '')}"""

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": COMMS_ANALYSIS_PROMPT},
            {"role": "user", "content": email_content},
        ],
        temperature=0.2,
        max_tokens=600,
    )

    raw = completion.choices[0].message.content.strip()
    raw = _clean_json(raw)
    return json.loads(raw)


def analyse_thread(emails: list) -> dict:
    """
    Analyse a full email thread (list of email dicts).
    Returns thread-level summary dict.
    """
    thread_content = f"THREAD: {len(emails)} emails\n\n"
    for i, email in enumerate(emails, 1):
        frm = email.get("from", {})
        thread_content += f"--- Email {i} ---\n"
        thread_content += f"From: {frm.get('name')} [{frm.get('type')}]\n"
        thread_content += f"Subject: {email.get('subject', '')}\n"
        thread_content += f"Date: {email.get('timestamp', '')}\n"
        thread_content += f"{email.get('body', '')}\n\n"

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": THREAD_ANALYSIS_PROMPT},
            {"role": "user", "content": thread_content},
        ],
        temperature=0.2,
        max_tokens=700,
    )

    raw = completion.choices[0].message.content.strip()
    raw = _clean_json(raw)
    return json.loads(raw)


def draft_reply(email: dict, analysis: dict) -> str:
    """Draft a professional reply to an email using AI."""
    frm = email.get("from", {})
    context = f"""Email from: {frm.get('name')} ({frm.get('type')})
Subject: {email.get('subject')}
AI urgency: {analysis.get('urgency')} (score: {analysis.get('urgency_score')})
AI summary: {analysis.get('ai_summary')}
Flags: {', '.join(analysis.get('flags', []))}

Original email:
{email.get('body', '')}"""

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPLY_DRAFT_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.5,
        max_tokens=300,
    )
    return completion.choices[0].message.content.strip()


def generate_action_items(email: dict, analysis: dict) -> list:
    """
    Generate concrete action items for an email.
    Returns a list of action item dicts.
    """
    if analysis.get("urgency_score", 0) < 10:
        return []

    frm = email.get("from", {})
    context = f"""Email: {email.get('subject')}
From: {frm.get('name')} [{frm.get('type')}] in {frm.get('unit', 'N/A')}
Property: {frm.get('property_id', 'N/A')}
Urgency: {analysis.get('urgency')} (score {analysis.get('urgency_score')})
Summary: {analysis.get('ai_summary')}
Recommended action: {analysis.get('recommended_action')}
Flags: {', '.join(analysis.get('flags', []))}
Action deadline: {analysis.get('action_deadline')}"""

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ACTION_ITEMS_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.2,
        max_tokens=600,
    )

    raw = completion.choices[0].message.content.strip()
    raw = _clean_json(raw)
    items = json.loads(raw)
    if isinstance(items, dict):
        items = [items]
    return items


def stream_analysis(email: dict):
    """
    Generator: streams AI analysis of a single email token by token.
    Used for the 🧠 Live Analysis SSE endpoint.
    """
    frm = email.get("from", {})
    email_content = f"""Perform a detailed property management analysis of this email.
Explain your reasoning step by step: who sent it, what they need, how urgent it is and why, what flags apply, and what the PM should do right now.

From: {frm.get('name')} <{frm.get('email')}> [{frm.get('type', 'unknown')}]
Unit: {frm.get('unit', 'N/A')} | Property: {frm.get('property_id', 'N/A')}
Subject: {email.get('subject', '')}

{email.get('body', '')}"""

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are an expert property management AI. Analyse emails thoroughly, explaining your reasoning. Be specific and professional. For welfare/safety issues, be direct and urgent."},
            {"role": "user", "content": email_content},
        ],
        temperature=0.3,
        max_tokens=800,
        stream=True,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from model output."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                return p
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:].strip()
    return raw
