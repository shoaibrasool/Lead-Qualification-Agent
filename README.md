# Lead Qualification Agent

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.9-purple)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI-powered chat widget that qualifies inbound website leads against a configurable ICP rubric, books demos via Cal.com when the fit is strong, and posts summary cards to Slack.

Built with **LangGraph** state machine, **Gemini** for conversational field extraction, and **FastAPI** for the web server.

---

## Features

- **Conversational Lead Capture** — Gemini-powered chat that extracts 8 qualification fields naturally (name, email, company, role, need, budget, timeline, company size)
- **Deterministic Scoring** — Zero LLM calls in scoring. Pure Python heuristics driven by a configurable JSON rubric (6 dimensions, weighted)
- **Auto-Booking** — High-scoring leads (≥70) automatically get demo slots offered and booked via Cal.com v2 API
- **Slack Notifications** — Every lead gets a Block Kit card posted to Slack with outcome emoji (✅ qualified / 👀 maybe / ❌ declined)
- **Turn Limit** — Conversations auto-resolve after 8 turns (configurable) with partial field scoring
- **State Persistence** — LangGraph checkpointer backed by MongoDB for resume-capable conversations
- **Vanilla JS Widget** — Drop-in embed via `<script>` tag, no framework required, Shadow DOM isolation
- **Seed Script** — 16 synthetic conversations to populate data before going live

---

## Architecture

```
+---------+     +--------------+     +-----------+     +----------+     +--------------+     +-----+
|  greet  | --> | collect_info | <-> | score_lead| --> | book_demo| --> | notify_slack | --> | end |
| (static)|     | (Gemini LLM) |     | (rubric)  |     |(Cal.com) |     | (Slack BH)   |     |     |
+---------+     +--------------+     +-----------+     +----------+     +--------------+     +-----+
                                                |
                                                v
                                           notify_slack -> end
                                           (maybe/declined)
```

### LangGraph State Machine

| Node | Runtime | Description |
|---|---|---|
| `greet` | 10s | Static welcome message, no LLM |
| `collect_info` | 30s | Gemini conversation loop, one question at a time |
| `score_lead` | 10s | Deterministic scoring from `scoring_rubric.json` |
| `book_demo` | 30s | Cal.com slot lookup + booking creation |
| `notify_slack` | 30s | Fire-and-forget Slack webhook POST |
| `end` | 5s | Persist lead to MongoDB, return closing message |

### Scoring Dimensions

| Dimension | Weight | Type | Input |
|---|---|---|---|
| Budget | 25% | Bucketed threshold | `budget` field |
| Authority | 20% | Weighted lookup | `job_title` x `company_size` multiplier |
| Need | 20% | Keyword score | `need` field (urgency/pain match) |
| Timeline | 15% | Bucketed threshold | `timeline` field |
| Company Fit | 10% | Bucketed threshold | `company_size` field |
| Engagement | 10% | Bucketed threshold | `turn_count` (conversation depth) |

**Formula:** `weighted = raw_score x (weight / 100)`, final = `sum(weighted) x 10`

### Outcomes

| Score Range | Outcome | Action |
|---|---|---|
| >= 70 | `qualified` | Auto-book Cal.com demo |
| 40-69 | `maybe` | Flag for human follow-up |
| < 40 | `declined` | Polite decline message |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Web Server** | FastAPI + Uvicorn |
| **State Machine** | LangGraph 1.2.9 |
| **LLM** | Gemini 2.5 Flash Lite (via langchain-google-genai 4.x) |
| **Database** | MongoDB (PyMongo sync driver) |
| **Checkpointer** | langgraph-checkpoint-mongodb 0.4.0 (`MongoDBSaver`) |
| **Calendar** | Cal.com v2 API (httpx async) |
| **Notifications** | Slack Incoming Webhook (Block Kit JSON) |
| **External HTTP** | httpx |
| **Retry Logic** | tenacity |
| **Widget** | Vanilla JavaScript + CSS (Shadow DOM) |
| **Config** | Pydantic Settings (`.env`) |

---

## Project Structure

```
lead-qualification-agent/
├── app/
│   ├── main.py                  # FastAPI app factory, lifespan, CORS
│   ├── config.py                # Pydantic BaseSettings
│   ├── database.py              # MongoDB client singleton + indexes
│   ├── models.py                # ChatRequest, ChatResponse, LeadInDB
│   ├── graph/
│   │   ├── state.py             # LeadState TypedDict
│   │   ├── nodes.py             # 6 graph node implementations
│   │   ├── edges.py             # Conditional routing functions
│   │   └── agent.py             # StateGraph assembly + compile
│   ├── routes/
│   │   └── chat.py              # POST /chat, GET /health
│   └── services/
│       ├── gemini_service.py    # ChatGoogleGenerativeAI + tenacity retry
│       ├── scoring.py           # Rubric-based scoring engine
│       ├── cal_service.py       # Cal.com v2 slot + booking API
│       └── slack_service.py     # Block Kit builder + webhook POST
├── frontend/widget/
│   ├── index.html               # Test page
│   ├── widget.js                # Floating bubble, sessions, slot buttons
│   └── widget.css               # Shadow DOM styles
├── scripts/
│   └── seed_conversations.py    # 16 synthetic lead conversations
├── scoring_rubric.json          # ICP scoring configuration
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
└── AGENTS.md                    # AI agent instructions
```

---

## Setup

### Prerequisites

- Python 3.11+
- MongoDB instance (local or Atlas M0 free tier)
- Gemini API key from [Google AI Studio](https://aistudio.google.com)
- Cal.com account with a "Demo Call" event type
- Slack workspace with [incoming webhook](https://slack.com/apps/A0F7XDUAZ-incoming-webhooks)

### Installation

```bash
git clone https://github.com/shoaibrasool/Lead-Qualification-Agent.git
cd Lead-Qualification-Agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

### Configuration

```env
# Required
GEMINI_API_KEY=             # Google AI Studio API key
GEMINI_MODEL=gemini-2.5-flash-lite
CALCOM_API_KEY=             # Cal.com API key
CALCOM_EVENT_TYPE_ID=       # Your Demo Call event type ID
SLACK_WEBHOOK_URL=          # Slack incoming webhook URL
MONGODB_CONNECTION_STRING=  # mongodb://localhost:27017

# Optional (defaults shown)
AUTO_BOOK_THRESHOLD=70
FLAG_FOLLOWUP_THRESHOLD=40
MAX_CONVERSATION_TURNS=8
APP_ENV=dev
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

```bash
python scripts/seed_conversations.py
```

### API

**`POST /chat`**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Hi, I'm interested in your product."
}
```

**`GET /health`** — Server health check

---

## Widget Embed

```html
<script
  src="https://your-domain.com/widget/widget.js"
  data-api-url="https://your-domain.com/chat"
></script>
```

Renders as a floating bubble (bottom-right), expands to a 380x520px panel with typing indicator, markdown rendering, and clickable time slot buttons.

---

## Deployment

### Railway

```bash
railway login
railway init
railway up
```

### AWS EC2

```bash
git clone <repo> && cd Lead-Qualification-Agent
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
# Configure Nginx (port 80 -> 8000) + systemd service
sudo systemctl start lead-agent
```

---

## Common Pitfalls

- **Messages field**: Must use `Annotated[list[BaseMessage], add_messages]` reducer
- **MongoDB driver**: Use sync `MongoClient`, not Motor
- **Checkpointer**: Use `MongoDBSaver`, not deprecated `AsyncMongoDBSaver`
- **Gemini package**: Use `langchain-google-genai` 4.x, not 2.x
- **Cal.com header**: `cal-api-version` changes periodically - verify at build time
- **Timeout**: Set `serverSelectionTimeoutMS=3000` on `MongoClient`

---

## License

MIT
