from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage

from app.config import get_settings
from app.graph.state import LeadState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a lead qualification assistant for a B2B SaaS company. Your job is to collect information from a website visitor to assess if they're a good fit.

You need to collect these 8 pieces of information:
1. name — their full name
2. email — their email address
3. company_name — what company they work for
4. company_size — number of employees
5. job_title — their role or position
6. need — what they're looking for or what problem they want to solve
7. budget — their approximate budget range
8. timeline — when they're looking to make a decision

RULES:
- Ask ONE question at a time. Never ask multiple questions in one message.
- Be conversational, friendly, and natural. Acknowledge answers before moving on.
- When you have collected ALL 8 fields, output a JSON object as the VERY LAST LINE of your response:
{"complete": true, "fields": {"name": "...", "email": "...", "company_name": "...", "company_size": "...", "job_title": "...", "need": "...", "budget": "...", "timeline": "..."}}
- Do NOT output the JSON line until you truly have all 8 fields.
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
        "pending_slots": None,
        "pending_selected_slot": None,
        "booking_link": None,
        "booking_error": None,
    }


def _get_last_user_message(state: LeadState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _pick_slot_from_response(user_text: str, slots: list[dict]) -> dict | None:
    text_lower = user_text.lower().strip()
    import re

    if not slots:
        return None

    for slot in slots:
        time_str = slot.get("start", slot.get("time", ""))
        if time_str and time_str in user_text:
            return slot

    formatted_texts = [
        _format_slot_option(i + 1, s).split(". ", 1)[-1].lower()
        for i, s in enumerate(slots)
    ]
    for idx, fmt in enumerate(formatted_texts):
        if fmt in text_lower:
            return slots[idx]

    if re.search(r'\b(last|final)\b', text_lower):
        return slots[-1]

    match = re.search(r"\b([1-3])\b", text_lower)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(slots):
            return slots[idx]

    words = ["first", "1st", "second", "2nd", "third", "3rd"]
    for i, word in enumerate(words[:3]):
        if re.search(rf'\b{re.escape(word)}\b', text_lower):
            return slots[i] if i < len(slots) else slots[-1]
    for i, word in enumerate(words[3:]):
        if re.search(rf'\b{re.escape(word)}\b', text_lower):
            return slots[i + 3] if i + 3 < len(slots) else slots[-1]

    return None


def _format_slot_option(idx: int, slot: dict) -> str:
    start = slot.get("start", slot.get("time", ""))
    date = slot.get("date", "")
    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        return f"{idx}. {dt.strftime('%A, %b %d at %I:%M %p %Z')}"
    except (ValueError, AttributeError):
        return f"{idx}. {date} {start}"


def _guess_attendee_name(state: LeadState) -> str:
    fields = state.get("collected_fields", {})
    name = fields.get("name")
    if name and str(name).strip() and str(name) != "not provided":
        return str(name)
    if fields.get("company_name"):
        return f"Lead from {fields['company_name']}"
    return "Lead"


def _guess_attendee_email(state: LeadState) -> str:
    fields = state.get("collected_fields", {})
    email = fields.get("email")
    if email and str(email).strip() and str(email) != "not provided":
        return str(email)
    return ""


def _extract_email(text: str) -> str | None:
    import re
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    return match.group(0) if match else None


async def book_demo_node(state: LeadState) -> dict:
    from app.services.cal_service import create_booking, get_slots

    settings = get_settings()
    event_type_id = settings.calcom_event_type_id
    existing_pending = state.get("pending_slots")
    pending_selected = state.get("pending_selected_slot")

    if pending_selected:
        user_message = _get_last_user_message(state)
        email = _extract_email(user_message) or _guess_attendee_email(state)
        if not email:
            return {
                "messages": [
                    AIMessage(
                        content="I need your email address to book the demo. Please share it."
                    )
                ],
                "pending_slots": None,
                "pending_selected_slot": pending_selected,
            }

        start = pending_selected.get("start", pending_selected.get("time", ""))
        attendee_name = _guess_attendee_name(state)

        try:
            uid, url = await create_booking(
                event_type_id=event_type_id,
                start=start,
                attendee_name=attendee_name,
                attendee_email=email,
            )
            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"Great! I've booked a demo for you. "
                            f"Here's the link: {url}\n\n"
                            "You'll receive a confirmation email with details. "
                            "Let me know if you need to reschedule!"
                        )
                    )
                ],
                "booking_link": url,
                "booking_error": None,
                "pending_slots": None,
                "pending_selected_slot": None,
            }
        except Exception as e:
            logger.error("Booking creation failed: %s", e)
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I'm sorry, I couldn't complete the booking "
                            "due to a system error. Our team has been notified "
                            "and will follow up with you shortly."
                        )
                    )
                ],
                "booking_link": None,
                "booking_error": str(e),
                "pending_slots": None,
                "pending_selected_slot": None,
            }

    if existing_pending:
        user_message = _get_last_user_message(state)
        selected = _pick_slot_from_response(user_message, existing_pending)
        if selected is None:
            slots_text = "\n".join(
                _format_slot_option(i + 1, s) for i, s in enumerate(existing_pending)
            )
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I didn't quite catch which slot you prefer. "
                            f"Please pick one:\n{slots_text}"
                        )
                    )
                ],
                "pending_slots": existing_pending,
            }

        attendee_email = _guess_attendee_email(state)
        if not attendee_email:
            return {
                "messages": [
                    AIMessage(
                        content="I need your email address to book the demo. Could you please share it?"
                    )
                ],
                "pending_slots": None,
                "pending_selected_slot": selected,
            }

        start = selected.get("start", selected.get("time", ""))
        attendee_name = _guess_attendee_name(state)

        try:
            uid, url = await create_booking(
                event_type_id=event_type_id,
                start=start,
                attendee_name=attendee_name,
                attendee_email=attendee_email,
            )
            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"Great! I've booked a demo for you. "
                            f"Here's the link: {url}\n\n"
                            "You'll receive a confirmation email with details. "
                            "Let me know if you need to reschedule!"
                        )
                    )
                ],
                "booking_link": url,
                "booking_error": None,
                "pending_slots": None,
                "pending_selected_slot": None,
            }
        except Exception as e:
            logger.error("Booking creation failed: %s", e)
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I'm sorry, I couldn't complete the booking "
                            "due to a system error. Our team has been notified "
                            "and will follow up with you shortly."
                        )
                    )
                ],
                "booking_link": None,
                "booking_error": str(e),
                "pending_slots": None,
                "pending_selected_slot": None,
            }

    try:
        slots = await get_slots(event_type_id=event_type_id)
    except Exception as e:
        logger.error("Slot fetch failed: %s", e)
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I wasn't able to check available demo slots "
                        "right now. Our team will reach out to you "
                        "shortly to schedule a meeting."
                    )
                )
            ],
            "booking_link": None,
            "booking_error": str(e),
            "pending_slots": None,
            "pending_selected_slot": None,
        }

    if not slots:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I don't see any available demo slots in the "
                        "coming week. Our team will reach out to you "
                        "shortly to find a time that works."
                    )
                )
            ],
            "booking_link": None,
            "booking_error": "No available demo slots found",
            "pending_slots": None,
            "pending_selected_slot": None,
        }

    display_slots = slots[:3]
    slots_text = "\n".join(
        _format_slot_option(i + 1, s) for i, s in enumerate(display_slots)
    )
    return {
        "messages": [
            AIMessage(
                content=(
                    "You're a great fit! Let's get a demo booked.\n\n"
                    f"Here are available times:\n{slots_text}\n\n"
                    "Which one works best for you?"
                )
            )
        ],
        "pending_slots": display_slots,
        "pending_selected_slot": None,
    }


async def notify_slack_node(state: LeadState) -> dict:
    from app.services.slack_service import send_slack

    settings = get_settings()
    webhook_url = settings.slack_webhook_url.get_secret_value()
    send_slack(webhook_url, dict(state))
    return {}


def end_node(state: LeadState) -> dict:
    from app.database import get_leads_collection

    outcome = state.get("outcome", "declined")
    if outcome == "qualified":
        text = (
            "Thanks for your time! We've noted your interest and "
            "our team will be in touch soon."
        )
    elif outcome == "maybe":
        text = (
            "Thanks for chatting! A member of our team will review "
            "your information and reach out if there's a good fit."
        )
    else:
        text = (
            "Thanks for your interest! Unfortunately, it doesn't "
            "seem like we're the right fit at this time. "
            "Best of luck!"
        )

    try:
        get_leads_collection().update_one(
            {"session_id": state["session_id"]},
            {"$set": {
                "fields": state.get("collected_fields", {}),
                "score": state.get("score"),
                "outcome": state.get("outcome"),
                "booking_link": state.get("booking_link"),
                "timestamp": datetime.now(UTC),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning("Failed to save lead to MongoDB: %s", e)

    return {"messages": [AIMessage(content=text)]}
