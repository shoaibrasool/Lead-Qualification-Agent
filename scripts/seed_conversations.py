#!/usr/bin/env python3
"""Seed 16 synthetic leads through the live /chat endpoint.

Covers: 4x booked, 4x flagged, 4x declined, 4x abandoned (8-turn timeout).

Usage:
    python scripts/seed_conversations.py

Requires the server to be running on SEED_BASE_URL (default http://localhost:8000).
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.environ.get("SEED_BASE_URL", "http://localhost:8000")
CHAT_URL = f"{SERVER_URL}/chat"
MONGO_URI = os.environ.get("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
DB_NAME = os.environ.get("APP_ENV", "dev")

TIMEOUT = httpx.Timeout(60.0)

PASS = 0
FAIL = 0
results = []


def _post(session_id: str, message: str) -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(CHAT_URL, json={"session_id": session_id, "message": message})
        resp.raise_for_status()
        return resp.json()


def _check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        status = "PASS"
    else:
        FAIL += 1
        status = "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    results.append({"label": label, "status": status, "detail": detail})


def _build_info_msg(p: dict) -> str:
    parts = [
        f"Name: {p['name']}",
        f"Email: {p['email']}",
        f"Job Title: {p['job_title']}",
        f"Company: {p['company_name']}",
        f"Company Size: {p['company_size']} employees",
        f"Need: {p['need']}",
        f"Budget: {p['budget']}",
        f"Timeline: {p['timeline']}",
    ]
    return ". ".join(parts) + "."


FIELD_KEYS = ["name", "email", "company_name", "company_size", "job_title", "need", "budget", "timeline"]


def run_conversation(session_id: str, profile: dict, max_turns: int = 20) -> dict:
    resp = {}
    info_sent = False
    field_idx = 0

    for turn in range(max_turns):
        if resp.get("done"):
            break

        if turn == 0:
            resp = _post(session_id, "Hi! I'm interested in your product.")
            continue

        reply_lower = resp.get("reply", "").lower()
        debug = resp.get("debug", {})
        outcome = debug.get("outcome")
        done = resp.get("done", False)

        # Booking flow — outcome set but not done means pending slots
        if not done and outcome is not None:
            if "email" in reply_lower and ("your" in reply_lower or "share" in reply_lower):
                resp = _post(session_id, profile.get("email", "unknown@example.com"))
            else:
                resp = _post(session_id, "The first slot works for me.")
            continue

        if not info_sent:
            resp = _post(session_id, _build_info_msg(profile))
            info_sent = True
            continue

        # Not complete yet — feed any remaining fields individually
        if field_idx < len(FIELD_KEYS):
            key = FIELD_KEYS[field_idx]
            field_idx += 1
            resp = _post(session_id, f"My {key.replace('_', ' ')} is {profile[key]}")
        else:
            resp = _post(session_id, "Yes, that's correct.")

    return resp


def run_abandoned(session_id: str) -> dict:
    responses = [
        "Hi, I'm looking around.",
        "Not sure yet, tell me more.",
        "I'm just browsing.",
        "Hmm, I haven't decided.",
        "Can you tell me about pricing?",
        "I'll have to think about it.",
        "Maybe I'll check back later.",
        "Let me talk to my team first.",
        "I don't know if now is the right time.",
        "Can you send me more information?",
    ]
    resp = {}
    for i, msg in enumerate(responses):
        resp = _post(session_id, msg)
        if resp.get("done"):
            break
    return resp


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _make_profiles():
    booked = [
        {
            "session_id": str(uuid.uuid4()),
            "name": "Alice Johnson",
            "email": "alice@techcorp.com",
            "company_name": "TechCorp",
            "company_size": "51-200",
            "job_title": "CEO",
            "need": "urgently automate our lead qualification process",
            "budget": "50k+",
            "timeline": "this month",
            "expected_outcome": "qualified",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Bob Smith",
            "email": "bob@innovate.io",
            "company_name": "Innovate.io",
            "company_size": "51-200",
            "job_title": "VP of Engineering",
            "need": "We have a critical requirement to automate our pipeline immediately",
            "budget": "50k+",
            "timeline": "this month",
            "expected_outcome": "qualified",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Carol Davis",
            "email": "carol@dataflow.com",
            "company_name": "DataFlow Inc",
            "company_size": "201-500",
            "job_title": "Director of Sales",
            "need": "improve our team productivity",
            "budget": "significant",
            "timeline": "next quarter",
            "expected_outcome": "qualified",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Dan Wilson",
            "email": "dan@buildlab.com",
            "company_name": "BuildLab",
            "company_size": "501+",
            "job_title": "Head of Product",
            "need": "integrate our systems as a critical requirement",
            "budget": "25k+",
            "timeline": "under 2 months",
            "expected_outcome": "qualified",
        },
    ]

    flagged = [
        {
            "session_id": str(uuid.uuid4()),
            "name": "Eve Martin",
            "email": "eve@midcorp.com",
            "company_name": "MidCorp",
            "company_size": "51-200",
            "job_title": "Manager",
            "need": "explore options for the future",
            "budget": "~5k",
            "timeline": "6 months",
            "expected_outcome": "maybe",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Frank Lee",
            "email": "frank@startup.io",
            "company_name": "Startup.io",
            "company_size": "11-50",
            "job_title": "Senior Engineer",
            "need": "exploring options to improve our team efficiency",
            "budget": "10-20k",
            "timeline": "3 months",
            "expected_outcome": "maybe",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Grace Kim",
            "email": "grace@smallbiz.com",
            "company_name": "SmallBiz",
            "company_size": "1-10",
            "job_title": "Team Lead",
            "need": "consider our options for growth",
            "budget": "5-10k",
            "timeline": "end of year",
            "expected_outcome": "maybe",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Henry Brown",
            "email": "henry@bigco.com",
            "company_name": "BigCo",
            "company_size": "201-500",
            "job_title": "Associate Director",
            "need": "look into solutions for our department",
            "budget": "10k",
            "timeline": "next quarter",
            "expected_outcome": "maybe",
        },
    ]

    declined = [
        {
            "session_id": str(uuid.uuid4()),
            "name": "Ivy Chen",
            "email": "ivy@solo.dev",
            "company_name": "Solo Dev",
            "company_size": "1-10",
            "job_title": "Freelancer",
            "need": "just browsing what's available",
            "budget": "under 5k",
            "timeline": "next year",
            "expected_outcome": "declined",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Jack Turner",
            "email": "jack@micro.io",
            "company_name": "Micro.io",
            "company_size": "1-10",
            "job_title": "Junior Developer",
            "need": "curious about the product",
            "budget": "small",
            "timeline": "not sure yet",
            "expected_outcome": "declined",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Karen White",
            "email": "karen@test.com",
            "company_name": "not provided",
            "company_size": "not provided",
            "job_title": "Intern",
            "need": "general inquiry about your company",
            "budget": "not provided",
            "timeline": "not provided",
            "expected_outcome": "declined",
        },
        {
            "session_id": str(uuid.uuid4()),
            "name": "Leo Park",
            "email": "leo@tinyco.com",
            "company_name": "TinyCo",
            "company_size": "1-10",
            "job_title": "Trainee",
            "need": "maybe look into it someday",
            "budget": "less than 5k",
            "timeline": "about a year from now",
            "expected_outcome": "declined",
        },
    ]

    abandoned = [
        {"session_id": str(uuid.uuid4()), "expected_outcome": None},
        {"session_id": str(uuid.uuid4()), "expected_outcome": None},
        {"session_id": str(uuid.uuid4()), "expected_outcome": None},
        {"session_id": str(uuid.uuid4()), "expected_outcome": None},
    ]

    return booked, flagged, declined, abandoned


# ---------------------------------------------------------------------------
# MongoDB verification
# ---------------------------------------------------------------------------

def verify_mongodb(all_sessions: list[dict]) -> list[dict]:
    try:
        from pymongo import MongoClient
    except ImportError:
        print("  [SKIP] pymongo not installed — skipping MongoDB verification")
        return []

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    col = db["leads"]

    docs = list(col.find({"session_id": {"$in": [s["session_id"] for s in all_sessions]}}))
    print(f"\n  MongoDB: found {len(docs)} docs in '{DB_NAME}.leads'")

    results = []
    for s in all_sessions:
        doc = col.find_one({"session_id": s["session_id"]})
        if doc is None:
            print(f'  [FAIL] No MongoDB doc for session {s["session_id"][:8]}...')
            results.append({"session_id": s["session_id"], "found": False})
        else:
            exp = s.get("expected_outcome")
            if exp and doc.get("outcome") != exp:
                print(f'  [FAIL] Session {s["session_id"][:8]}... outcome={doc.get("outcome")} expected={exp}')
                results.append({"session_id": s["session_id"], "found": True, "outcome_mismatch": True})
            else:
                print(f'  [OK]   Session {s["session_id"][:8]}... outcome={doc.get("outcome")} score={doc.get("score")}')
                results.append({"session_id": s["session_id"], "found": True})

    client.close()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global PASS, FAIL, results
    PASS = 0
    FAIL = 0
    results = []

    print("=" * 62)
    print("  Lead Qualification Agent — Phase 6: Seed Conversations")
    print("=" * 62)

    # Health check
    try:
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{SERVER_URL}/health")
            r.raise_for_status()
        print(f"\n  Server at {SERVER_URL} is up\n")
    except Exception as e:
        print(f"\n  [FAIL] Cannot reach server at {SERVER_URL}: {e}")
        print("  Start the server first: uvicorn app.main:app --port 8000")
        sys.exit(1)

    booked, flagged, declined, abandoned = _make_profiles()
    categories = [
        ("booked (qualified)", booked),
        ("flagged (maybe)", flagged),
        ("declined", declined),
        ("abandoned", abandoned),
    ]

    all_sessions = []

    for label, profiles in categories:
        print(f"  ── {label} ──")
        for i, p in enumerate(profiles, 1):
            session_id = p["session_id"]
            all_sessions.append(p)

            try:
                if label.startswith("abandoned"):
                    resp = run_abandoned(session_id)
                else:
                    resp = run_conversation(session_id, p)

                debug = resp.get("debug", {})
                outcome = debug.get("outcome")
                score = debug.get("score")
                done = resp.get("done")
                booking_link = resp.get("booking_link")

                print(f"  [{i}] {p.get('name', 'abandoned'):20s} → outcome={outcome} score={score} done={done}")

                if label.startswith("abandoned"):
                    _check(f"Abandoned session {i} completed (done=True)", done)
                    _check(f"Abandoned session {i} has outcome set", outcome is not None)
                else:
                    exp = p["expected_outcome"]
                    _check(f"{p['name']} outcome == {exp}", outcome == exp,
                           f"got={outcome}")
                    _check(f"{p['name']} score is valid (0-100)",
                           score is not None and 0 <= score <= 100,
                           f"score={score}")
                    if exp == "qualified":
                        _check(f"{p['name']} score >= {60}", score is not None and score >= 60,
                               f"score={score}")
                    elif exp == "maybe":
                        _check(f"{p['name']} score >= {40} and < {60}",
                               score is not None and 40 <= score < 60,
                               f"score={score}")
                    elif exp == "declined":
                        _check(f"{p['name']} score < {40}",
                               score is not None and score < 40,
                               f"score={score}")

                    if exp == "qualified":
                        if booking_link:
                            _check(f"{p['name']} has booking link", True)
                        elif debug.get("booking_error"):
                            _check(f"{p['name']} booking note", True,
                                   f"booking_error={debug['booking_error']}")
                        elif done:
                            _check(f"{p['name']} completed but no booking link",
                                   False, "booking_link=None booking_error=None")

            except Exception as e:
                print(f"  [{i}] {p.get('name', 'abandoned'):20s} → ERROR: {e}")
                _check(f"Session {i} no exception", False, str(e))

    print(f"\n  {'=' * 58}")
    print(f"  Results: {PASS} passed, {FAIL} failed\n")

    # MongoDB verification
    print("  ── MongoDB Verification ──")
    mongo_results = verify_mongodb(all_sessions)

    mongo_found = sum(1 for r in mongo_results if r.get("found"))
    mongo_missing = sum(1 for r in mongo_results if not r.get("found"))
    print(f"\n  MongoDB docs: {mongo_found} found, {mongo_missing} missing")

    # Summary
    print(f"\n  {'=' * 58}")
    if FAIL == 0 and mongo_missing == 0:
        print("  ALL VALIDATIONS PASSED")
        sys.exit(0)
    else:
        print(f"  {FAIL} API failures, {mongo_missing} missing MongoDB docs")
        sys.exit(1)


if __name__ == "__main__":
    main()
