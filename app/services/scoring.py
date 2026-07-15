from __future__ import annotations

import json
import os

_RUBRIC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "scoring_rubric.json",
)

_EMPTY_VALUES = frozenset({"", "not provided", "unknown", "n/a", "none"})


def _load_rubric() -> dict:
    with open(_RUBRIC_PATH) as f:
        return json.load(f)


def _normalize(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_empty(value) -> bool:
    return _normalize(value) in _EMPTY_VALUES


def _best_match_length(text: str, patterns: list[str]) -> int:
    text_lower = _normalize(text)
    best = 0
    for pattern in patterns:
        p = pattern.lower()
        if p in text_lower:
            best = max(best, len(p))
    return best


def _evaluate_bucketed_threshold(config: dict, inputs: dict) -> int:
    input_key = config["input"]
    value = inputs.get(input_key)

    if _is_empty(value):
        return config["default_score"]

    if input_key == "turn_count":
        turn_count = value if isinstance(value, (int, float)) else 0
        best_score = config["default_score"]
        for bucket in config["buckets"]:
            min_turns = bucket.get("min", 0)
            if turn_count >= min_turns:
                best_score = max(best_score, bucket["score"])
        return best_score

    value_str = _normalize(value)
    best_score = config["default_score"]
    best_len = 0

    for bucket in config["buckets"]:
        patterns = bucket.get("match", [])
        match_len = _best_match_length(value_str, patterns)
        if match_len > best_len:
            best_len = match_len
            best_score = bucket["score"]

    return best_score


def _evaluate_weighted_lookup(config: dict, inputs: dict) -> int:
    field_config = config["inputs"]
    primary_value = inputs.get(field_config["primary"])

    if _is_empty(primary_value):
        return config["default_score"]

    primary_str = _normalize(primary_value)
    base_score = config["default_score"]
    best_len = 0

    for entry in config["primary_keywords"]:
        match_len = _best_match_length(primary_str, entry["match"])
        if match_len > best_len:
            best_len = match_len
            base_score = entry["score"]

    multiplier = 1.0
    multiplier_field = field_config.get("multiplier")
    if multiplier_field:
        multiplier_value = inputs.get(multiplier_field)
        if not _is_empty(multiplier_value):
            mult_str = _normalize(multiplier_value)
            best_mult_len = 0
            for key, val in config.get("multiplier_map", {}).items():
                key_lower = key.lower()
                if key_lower in mult_str or mult_str in key_lower:
                    match_len = max(len(key_lower), len(mult_str))
                    if match_len > best_mult_len:
                        best_mult_len = match_len
                        multiplier = val

    combine = config.get("combine", "passthrough")
    if combine == "multiply":
        return min(10, round(base_score * multiplier))

    return min(10, base_score)


def _evaluate_keyword_score(config: dict, inputs: dict) -> int:
    input_key = config["input"]
    value = inputs.get(input_key)

    if _is_empty(value):
        return config["default_score"]

    value_str = _normalize(value)
    best_score = config["default_score"]
    best_len = 0

    for level in config["levels"]:
        match_len = _best_match_length(value_str, level["match"])
        if match_len > best_len:
            best_len = match_len
            best_score = level["score"]

    return best_score


_EVALUATORS = {
    "bucketed_threshold": _evaluate_bucketed_threshold,
    "weighted_lookup": _evaluate_weighted_lookup,
    "keyword_score": _evaluate_keyword_score,
}


def score_lead(fields: dict, turn_count: int = 0) -> dict:
    rubric = _load_rubric()
    dimensions = rubric["dimensions"]

    inputs: dict = {**fields, "turn_count": turn_count}

    total = 0
    breakdown = []

    for name, config in dimensions.items():
        evaluator_fn = _EVALUATORS[config["type"]]
        raw = evaluator_fn(config, inputs)
        weighted = raw * (config["weight"] / 100)
        total += weighted
        breakdown.append({
            "dimension": name,
            "raw": raw,
            "weight": config["weight"],
            "weighted_score": round(weighted, 2),
        })

    return {
        "total_score": round(total * 10),
        "dimensions": breakdown,
    }
