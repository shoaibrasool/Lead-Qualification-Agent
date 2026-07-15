from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.cal.com/v2"

SLOTS_API_VERSION = "2024-09-04"
BOOKINGS_API_VERSION = "2024-08-13"


def _headers(api_version: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.calcom_api_key.get_secret_value()}",
        "Content-Type": "application/json",
        "cal-api-version": api_version,
    }


async def get_slots(
    event_type_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    time_zone: str = "UTC",
) -> list[dict]:
    if start_date is None:
        start_date = datetime.now(UTC).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = (datetime.now(UTC) + timedelta(days=7)).strftime("%Y-%m-%d")

    params = {
        "eventTypeId": event_type_id,
        "start": start_date,
        "end": end_date,
        "timeZone": time_zone,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/slots",
            headers=_headers(SLOTS_API_VERSION),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    slots_by_date: dict[str, list[dict | str]] = data.get("data", {})
    all_slots: list[dict] = []
    for date_str, slots in slots_by_date.items():
        for slot_time in slots:
            if isinstance(slot_time, str):
                all_slots.append({"date": date_str, "time": slot_time, "start": slot_time})
            elif isinstance(slot_time, dict):
                all_slots.append({"date": date_str, **slot_time})

    all_slots.sort(key=lambda s: s.get("start", s.get("time", "")))
    return all_slots


async def create_booking(
    event_type_id: int,
    start: str,
    attendee_name: str,
    attendee_email: str,
    time_zone: str = "UTC",
) -> tuple[str, str]:
    body = {
        "start": start,
        "eventTypeId": event_type_id,
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": time_zone,
            "language": "en",
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/bookings",
            headers=_headers(BOOKINGS_API_VERSION),
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    booking = data.get("data", {})
    uid = booking.get("uid", "")
    url = booking.get("meetingUrl", "") or booking.get("location", "")
    return uid, url
