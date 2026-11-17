"""Shared constants, validation exception and pure helpers for narrative persistence."""
from __future__ import annotations

import json
import math
from typing import Any
from zoneinfo import ZoneInfo

CHINA = ZoneInfo("Asia/Shanghai")
FACT_KINDS = {"observation", "user_claim", "fiction", "subjective", "plan", "receipt"}
AVAILABILITIES = {"available", "busy", "asleep", "unknown"}
ACTIVITIES = {
    "writing": "独自写作", "gaming": "独自玩游戏", "resting": "休息",
    "sleeping": "睡觉", "eating": "用餐", "reading": "独自阅读",
    "walking": "散步", "chores": "处理日常事务", "unknown": "未知",
}
COMMITMENT_STATUSES = {"proposed", "committed", "conditional", "completed", "cancelled", "expired"}
INTENT_STATUSES = {"pending", "claimed", "sent", "cancelled", "expired", "uncertain", "failed"}
TERMINAL_INTENTS = {"sent", "cancelled", "expired", "uncertain"}


class NarrativeValidationError(ValueError):
    """Carry a fixed body-free code, never interpolated model/user content."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value: Any, maximum: int, field: str = "text") -> str:
    if not isinstance(value, str):
        raise NarrativeValidationError("text_type", f"{field} must be a string")
    value = value.strip()
    if len(value) > maximum:
        raise NarrativeValidationError("text_length", f"{field} exceeds its length limit")
    return value


def _timestamp(value: Any, field: str = "timestamp") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise NarrativeValidationError("timestamp_type", f"{field} must be a finite epoch timestamp")
    if value < 0:
        raise NarrativeValidationError("timestamp_negative", f"{field} cannot be negative")
    return float(value)


def normalize_scope(scope: dict) -> dict:
    """Validate scope identifiers without reducing full UMO to a group number."""
    if not isinstance(scope, dict) or scope.get("schema_version", 1) != 1:
        raise NarrativeValidationError("unsupported_scope_schema", "Unsupported scope schema")
    result = {name: _text(scope.get(name, ""), 300, name) for name in ("platform", "umo", "persona_id")}
    result["instance_id"] = _text(scope.get("instance_id") or result["persona_id"], 300, "instance_id")
    if not result["persona_id"] or not result["instance_id"]:
        raise NarrativeValidationError("a_concrete_persona_is_required", "A concrete persona is required")
    result["schema_version"] = 1
    return result


def _identity(scope: dict) -> str:
    return _json([scope["persona_id"], scope["instance_id"]])
