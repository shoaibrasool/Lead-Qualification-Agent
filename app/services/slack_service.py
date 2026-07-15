from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

OUTCOME_EMOJI = {
    "qualified": "✅",
    "maybe": "👀",
    "declined": "❌",
}

_background_tasks: set[asyncio.Task] = set()


async def _send_slack_post(webhook_url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()


def _format_breakdown(breakdown: list[dict] | None) -> str:
    if not breakdown:
        return "N/A"
    lines = []
    for dim in breakdown:
        name = dim.get("name", dim.get("dimension", "Unknown"))
        score = dim.get("score", dim.get("raw_score", 0))
        weight = dim.get("weight", 0)
        weighted = dim.get("weighted_score", 0)
        lines.append(f"  \u2022 {name}: {score}/{weight} \u2192 {weighted}")
    return "\n".join(lines)


def build_slack_payload(state: dict) -> dict:
    outcome = state.get("outcome", "unknown")
    score = state.get("score", 0)
    fields = state.get("collected_fields", {})
    emoji = OUTCOME_EMOJI.get(outcome, "❔")

    company = fields.get("company_name") or fields.get("company") or "Unknown Company"
    job_title = fields.get("job_title") or fields.get("role") or "N/A"
    need = fields.get("need") or fields.get("pain_point") or "N/A"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {outcome.upper()}: {company}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Score:*\n{score}/100"},
                {"type": "mrkdwn", "text": f"*Need:*\n{need}"},
            ],
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company}"},
                {"type": "mrkdwn", "text": f"*Role:*\n{job_title}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Score Breakdown:*\n{_format_breakdown(state.get('score_breakdown'))}",
            },
        },
    ]

    booking_link = state.get("booking_link")
    booking_error = state.get("booking_error")

    if booking_link:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Booking"},
                        "url": booking_link,
                        "style": "primary",
                    }
                ],
            }
        )
    elif booking_error:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Booking Error:*\n{booking_error}",
                },
            }
        )

    return {"text": f"New lead: {company} \u2014 {score}/100 \u2014 {outcome}", "blocks": blocks}


def send_slack(webhook_url: str, state: dict) -> None:
    payload = build_slack_payload(state)
    task = asyncio.create_task(_send_slack_post(webhook_url, payload))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
