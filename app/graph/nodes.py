from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.config import get_settings
from app.graph.state import LeadState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a lead qualification assistant for a B2B SaaS company. Your job is to collect information from a website visitor to assess if they're a good fit.

You need to collect these 6 pieces of information:
1. company_name — what company they work for
2. company_size — number of employees
3. job_title — their role or position
4. need — what they're looking for or what problem they want to solve
5. budget — their approximate budget range
6. timeline — when they're looking to make a decision

RULES:
- Ask ONE question at a time. Never ask multiple questions in one message.
- Be conversational, friendly, and natural. Acknowledge answers before moving on.
- When you have collected ALL 6 fields, output a JSON object as the VERY LAST LINE of your response:
{"complete": true, "fields": {"company_name": "...", "company_size": "...", "job_title": "...", "need": "...", "budget": "...", "timeline": "..."}}
- Do NOT output the JSON line until you truly have all 6 fields.
- If the user won't answer a question, politely note it and mark the field as "not provided"."""


def _has_ai_reply(messages: list) -> bool:
    return any(isinstance(m, AIMessage) for m in messages)


def _extract_completion_json(text: str) -> tuple[bool, dict]:
    start = text.find("{")
    if start == -1:
        return False, {}

    depth = 0
    for end in range(start, len(text)):
        c = text[end]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : end + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict) and isinstance(parsed.get("complete"), bool):
                        return parsed["complete"], parsed.get("fields", {})
                except (json.JSONDecodeError, ValueError):
                    continue
    return False, {}


def greet_node(state: LeadState) -> dict:
    if _has_ai_reply(state.get("messages", [])):
        return {}

    greeting = AIMessage(
        content=(
            "Hi there! Thanks for your interest. "
            "I'd love to learn a bit about you and your company to see how we can help. "
            "To start, what's your name and which company are you with?"
        )
    )
    return {
        "messages": [greeting],
        "turn_count": 0,
        "complete": False,
    }


def collect_info_node(state: LeadState) -> dict:
    if state.get("complete"):
        return {}

    from app.services.gemini_service import generate_response

    messages = state.get("messages", [])
    response = generate_response(messages, system_prompt=SYSTEM_PROMPT)

    if isinstance(response, list):
        response = " ".join(part.get("text", "") for part in response if isinstance(part, dict))

    turn_count = state.get("turn_count", 0) + 1

    if not response.strip():
        logger.warning("Gemini returned empty response")
        response = "I didn't quite catch that. Could you tell me more?"

    complete, fields = _extract_completion_json(response)

    ai_message = AIMessage(content=response)

    updates: dict = {
        "messages": [ai_message],
        "turn_count": turn_count,
    }

    if complete:
        existing = dict(state.get("collected_fields", {}))
        existing.update(fields)
        updates["collected_fields"] = existing
        updates["complete"] = True
    else:
        updates["complete"] = False

    return updates


def score_lead_node(state: LeadState) -> dict:
    from app.services.scoring import score_lead

    fields = state.get("collected_fields", {})
    turn_count = state.get("turn_count", 0)
    result = score_lead(fields, turn_count)
    score = result["total_score"]
    settings = get_settings()

    if score >= settings.auto_book_threshold:
        outcome = "qualified"
    elif score >= settings.flag_followup_threshold:
        outcome = "maybe"
    else:
        outcome = "declined"

    return {
        "score": score,
        "outcome": outcome,
        "score_breakdown": result["dimensions"],
    }
