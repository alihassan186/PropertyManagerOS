# PropertyOS — AI Property Operations Dashboard
### Give(a)Go Hackathon · March 7, 2025 · Baseline Dublin

> AI-powered maintenance triage system with AutoPilot Mode, Voice Input, live streaming, and contractor brief export.

---

## Quick Start (5 minutes)

### 1. Get Your FREE Groq API Key
1. Go to **[console.groq.com](https://console.groq.com)**
2. Sign Up (use Google — fastest)
3. Click **API Keys** → **Create API Key** → name it `propertyos`
4. Copy the key (starts with `gsk_`)

### 2. Setup
```bash
cd propertyos
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Add API Key
```bash
cp .env.example .env
# Edit .env and paste your Groq key:
# GROQ_API_KEY=gsk_your_key_here
```

### 4. Load Demo Data
```bash
python seed_data.py
```

### 5. Run
```bash
python app.py
```
Open **http://localhost:5000** in Chrome.

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Live AI Triage** | Paste tenant message → AI streams response word-by-word via SSE |
| 2 | **AutoPilot Mode** | Toggle ON → AI autonomously processes entire request queue with live trace |
| 3 | **Voice Input** | Click mic → speak request → Chrome transcribes → auto-triages |
| 4 | **Tenant Reply Generator** | One click → AI drafts reply in tenant's language |
| 5 | **Live Simulator** | Adds random realistic requests for demo effect |
| 6 | **Contractor Brief Export** | Copy brief or download formatted .txt file |

## Stack

- **Backend**: Python Flask + SQLite
- **AI**: Groq API (`llama-3.3-70b-versatile`) — FREE
- **Frontend**: Vanilla HTML/CSS/JS — no framework
- **Charts**: Chart.js 4.x
- **Cost**: €0

## 90-Second Demo Script

| Time | Action |
|------|--------|
| 0–15s | "Property managers handle 40+ requests/week. Each takes 15 mins. I built something that does it in 3 seconds." |
| 15–40s | Paste Emergency water message → Click Triage → say nothing → let streaming text talk |
| 40–55s | "What if it just ran itself?" → Flip AutoPilot toggle → step back |
| 55–65s | Click mic → speak a request → watch live triage |
| 65–75s | Paste neighbour noise message → shows edge case handling |
| 75–90s | "In 6 hours: WhatsApp, auto-assign contractors, calendar invites." |

## Demo Messages

```
EMERGENCY:
Water is pouring from my bedroom ceiling right now. It started 10 minutes ago and is getting worse.

HIGH + VULNERABLE:
No heating or hot water since this morning. I have a 4-month-old baby and it is very cold.

FRENCH:
Il y a une fuite d'eau sous mon évier depuis hier. L'eau s'accumule dans le placard.

EDGE CASE:
My neighbour plays guitar every night at 2am. I cannot sleep.
```
