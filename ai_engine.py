"""
ai_engine.py — All Groq API calls and prompts for PropertyOS
Model: llama-3.3-70b-versatile (FREE via console.groq.com)
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# ─── System Prompts ────────────────────────────────────────────────────────────

TRIAGE_SYSTEM_PROMPT = """You are an AI assistant for a property management company.
Analyse the maintenance request and return ONLY valid JSON with no
preamble, no explanation, no markdown fences.
Return exactly this JSON structure:

{
  "urgency": "Emergency" | "High" | "Medium" | "Low",
  "category": "Plumbing"|"Heating"|"Electrical"|"Structural"|"Pest"|"Appliance"|"Fixtures"|"Noise"|"Other",
  "contractor_brief": "<2-3 sentences, professional, ready to send>",
  "tenant_advice": "<1 sentence immediate actionable advice>",
  "response_time": "Within 2 hours"|"Within 24 hours"|"Within 3 days"|"Within 1 week",
  "language_detected": "<ISO 639-1 code e.g. en, fr, es, de>"
}

Urgency rules:
  Emergency = immediate safety risk, active water damage, no heat with vulnerable persons, gas smell, fire risk
  High      = affects livability, has dependents, ongoing risk
  Medium    = functional issue, not immediately dangerous
  Low       = cosmetic, minor inconvenience

Non-maintenance requests: set Low + Other, handle gracefully."""

REPLY_SYSTEM_PROMPT = """You are a professional and empathetic property manager.
Write a warm, concise reply to a tenant maintenance request.
Include: acknowledgement, urgency level, expected timeframe,
and one immediate action they can take.
Rules:
- Under 100 words
- No subject line, no signature
- Warm but professional
- If language_detected is not "en", write ENTIRELY in that language
- Plain text only"""

AUTOPILOT_SYSTEM_PROMPT = """You are an autonomous AI property operations agent.
Process this maintenance request autonomously.
Return ONLY valid JSON (no preamble, no markdown):
{
  "action_taken": "<one sentence what you did>",
  "urgency": "Emergency"|"High"|"Medium"|"Low",
  "category": "<category>",
  "contractor_brief": "<2-3 sentence brief>",
  "tenant_advice": "<1 sentence advice>",
  "response_time": "<timeframe>",
  "new_status": "In Progress"|"Resolved",
  "reasoning": "<1 sentence urgency explanation>"
}
Set new_status to "Resolved" for Low urgency ONLY.
All others: "In Progress"."""


# ─── Core Functions ─────────────────────────────────────────────────────────────

def triage_request(tenant_message: str, apartment_ref: str = None) -> dict:
    """
    Call Groq to triage a maintenance request.
    Returns a dict with urgency, category, contractor_brief,
    tenant_advice, response_time, language_detected.
    """
    user_content = tenant_message
    if apartment_ref:
        user_content = f"[Unit: {apartment_ref}]\n{tenant_message}"

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=512,
    )

    raw = completion.choices[0].message.content.strip()
    # Strip markdown fences if model ignores instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def generate_reply(tenant_message: str, triage_data: dict) -> str:
    """
    Generate a warm professional tenant reply.
    Uses language_detected from triage_data to reply in correct language.
    """
    language = triage_data.get("language_detected", "en")
    context = (
        f"Tenant message: {tenant_message}\n"
        f"Urgency: {triage_data.get('urgency')}\n"
        f"Category: {triage_data.get('category')}\n"
        f"Response time: {triage_data.get('response_time')}\n"
        f"Tenant advice: {triage_data.get('tenant_advice')}\n"
        f"language_detected: {language}"
    )

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0.5,
        max_tokens=256,
    )

    return completion.choices[0].message.content.strip()


def stream_triage(tenant_message: str, apartment_ref: str = None):
    """
    Generator: yields raw token strings from Groq streaming.
    Used for SSE endpoint /api/stream.
    """
    user_content = tenant_message
    if apartment_ref:
        user_content = f"[Unit: {apartment_ref}]\n{tenant_message}"

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=512,
        stream=True,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


def autopilot_process(tenant_message: str, apartment_ref: str = None) -> dict:
    """
    Autonomous AI processing for AutoPilot mode.
    Returns full action dict including new_status and reasoning.
    """
    user_content = tenant_message
    if apartment_ref:
        user_content = f"[Unit: {apartment_ref}]\n{tenant_message}"

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": AUTOPILOT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=512,
    )

    raw = completion.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
