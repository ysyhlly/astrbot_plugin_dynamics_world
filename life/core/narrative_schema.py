"""Static output contract; semantic evidence, ID and timestamp checks remain authoritative in Python."""

from __future__ import annotations


def narrative_schema(request: dict) -> dict:
    """Return a static JSON schema free of live timestamps and per-call dynamic ID enums.

    Exact timestamp windows (> now, day bounds, narrated_until) and dynamic ID
    membership (events, rooms, items, places, furniture, projects, actors) are
    strictly enforced by Python post-parse validators.
    """
    if request.get("resident_isolated"):
        from ...resident_runtime import decision_schema
        return decision_schema(request)
    scoped = bool(request["scope"]["umo"])

    def text(maximum):
        return {"type": "string", "maxLength": maximum}

    def choice(values):
        return {"type": "string", "enum": values}

    def stamp():
        return {"type": "number", "minimum": 0}

    def obj(properties, required=()):
        return {"type": "object", "properties": properties, "required": list(required),
                "additionalProperties": False}

    def rows(properties, required, maximum):
        return {"type": "array", "items": obj(properties, required), "maxItems": maximum}

    # Source-ID membership is strictly enforced by NarrativeEngine._sources.
    sources = {"type": "array", "items": text(300), "minItems": 1, "maxItems": 50}
    basic = {"source_ids": sources}
    member = {**basic, "subject_id": text(100)}
    if request.get("manual_plan_regeneration") and not scoped:
        return obj(
            {
                "schema_version": {"type": "integer", "enum": [1]},
                "no_change": {"type": "boolean"},
                "source_ids": sources,
                "state": obj(
                    {
                        "activity": text(80),
                        "activity_code": choice(
                            [
                                "writing",
                                "gaming",
                                "resting",
                                "sleeping",
                                "eating",
                                "reading",
                                "walking",
                                "chores",
                                "unknown",
                            ]
                        ),
                        "availability": choice(
                            ["available", "busy", "asleep", "unknown"]
                        ),
                        "subjective_state": text(300),
                        "summary": text(300),
                        "valid_until": stamp(),
                    }
                ),
                "daily_plan": {
                    "type": "array",
                    "items": obj(
                        {"start": stamp(), "end": stamp(), "activity": text(120)},
                        ("start", "end", "activity"),
                    ),
                    "minItems": 1,
                    "maxItems": 12,
                },
                "next_check": stamp(),
            },
            ("schema_version", "no_change", "daily_plan"),
        )
    if request.get("outreach_only"):
        props = {"no_change": {"type": "boolean"}}
        common = {
            **member,
            "reason": text(300),
            "evidence_quote": text(600),
            "not_before": stamp(),
            "expires_at": stamp(),
        }
        required = ("subject_id", "reason", "evidence_quote", "source_ids", "not_before", "expires_at")
        if request.get("care_policy", {}).get("enabled"):
            props["care_waits"] = rows(
                {
                    **common,
                    "reason_kind": choice(["health_concern", "travel_checkin", "agreed_checkin"]),
                    "waiting_for": text(300),
                },
                (*required, "reason_kind", "waiting_for"),
                2,
            )
        if request.get("social_policy", {}).get("enabled"):
            props["chat_openers"] = rows(
                {
                    **common,
                    "topic": text(120),
                    "topic_candidate_id": text(100),
                },
                (*required, "topic"),
                2,
            )
        return obj(props, ("no_change",))

    world_updates_schema = rows(
        {
            "actor_id": text(100),
            "operation": choice(["rest", "observe", "travel", "invite", "respond", "speak"]),
            "target_id": text(160),
            "invitation_id": text(80),
            "response": choice(["accepted", "declined", "reschedule"]),
            "when": stamp(),
            "text": text(240),
            "source_ids": {"type": "array", "items": text(160), "minItems": 1, "maxItems": 8},
        },
        ("actor_id", "operation", "source_ids"),
        8,
    )
    if request.get("background_only"):
        return obj(
            {"no_change": {"type": "boolean"}, "world_updates": world_updates_schema},
            ("no_change",),
        )

    humanlike = {
        "preferences": rows({**basic, "id": text(100), "text": text(120),
                             "status": choice(["active", "removed"])},
                            ("id", "text", "source_ids"), 8),
        "goals": rows({**basic, "id": text(100), "text": text(120),
                       "status": choice(["planned", "done", "dropped"]), "expires_at": stamp()},
                      ("id", "text", "source_ids"), 4),
    }
    humanlike["interests"] = rows(
        {
            **basic,
            "id": text(100),
            "topic": text(80),
            "text": text(160),
            "status": choice(["active", "paused", "done"]),
            "next_step": text(120),
            "progress_kind": choice(
                ["discussion", "execution"] if scoped else ["fiction"]
            ),
            "evidence_quote": text(300),
        },
        ("id", "topic", "text", "source_ids", "progress_kind", "evidence_quote"),
        4,
    )
    if scoped:
        humanlike.update(
            {
                "corrections": rows(
                    {
                        **member,
                        "category": choice(
                            [
                                "interpretation",
                                "length",
                                "advice",
                                "humor",
                                "addressing",
                            ]
                        ),
                        "topic": text(80),
                        "text": text(160),
                        "evidence_quote": text(300),
                        "status": choice(["active", "retracted"]),
                    },
                    (
                        "subject_id",
                        "category",
                        "topic",
                        "text",
                        "evidence_quote",
                        "source_ids",
                    ),
                    8,
                ),
                "moods": rows(
                    {
                        **member,
                        "text": text(120),
                        "expires_at": stamp(),
                        "topic": text(80),
                        "cause_quote": text(300),
                        "status": choice(["active", "settled"]),
                    },
                    ("subject_id", "text", "source_ids"),
                    8,
                ),
                "nicknames": rows(
                    {
                        **member,
                        "nickname": text(24),
                        "status": choice(["active", "rejected"]),
                        "evidence_quote": text(300),
                    },
                    (
                        "subject_id",
                        "nickname",
                        "status",
                        "source_ids",
                        "evidence_quote",
                    ),
                    8,
                ),
            }
        )
    properties = {
        "schema_version": {"type": "integer", "enum": [1]},
        "no_change": {"type": "boolean"},
        "event_impact": choice(["none", "activity", "commitment", "relationship"]),
        "state": obj({"activity_code": choice(["writing", "gaming", "resting", "sleeping", "eating",
                                                  "reading", "walking", "chores", "unknown"]),
                      "availability": choice(["available", "busy", "asleep", "unknown"]),
                      "subjective_state": text(300), "summary": text(300), "valid_until": stamp()}),
        "diary": rows({**basic, "text": text(300),
                       "occurred_at": stamp(),
                       "fact_kind": choice(["subjective", "user_claim", "observation", "receipt"] if scoped else ["fiction"])},
                      ("text", "source_ids", "fact_kind"), 4),
        "commitments": rows({**basic, "commitment_id": text(300), "description": text(300),
                             "status": choice(["proposed", "committed", "conditional", "completed", "cancelled", "expired"]),
                             "evidence_quote": text(300), "due_at": stamp(), "reminder_id": text(300)},
                            ("commitment_id", "description", "status", "source_ids"), 10),
        "contact_intents": rows({**basic, "intent_id": text(300), "reason": text(300),
                                 "not_before": stamp(), "expires_at": stamp(),
                                 "commitment_id": text(300), "reminder_id": text(300)},
                                ("reason", "source_ids", "not_before", "expires_at"), 4),
        "humanlike": obj(humanlike),
        "next_check": stamp(),
    }
    if not scoped:
        properties["state"]["properties"]["activity"] = text(80)
        kinds = [
            "enter", "leave", "take", "put", "read", "drink", "refill",
            "open_umbrella", "fold_umbrella", "rest", "dry", "travel",
            "write_note", "read_notes", "power_on", "power_off", "computer_work",
        ]
        from ...room_design import CURTAINS, KINDS, LIGHTS, POSITIONS
        kinds += sorted(KINDS)
        from ...creative_projects import KINDS as PROJECT_KINDS
        kinds += sorted(PROJECT_KINDS)
        from ...garden_ecology import ECOLOGY_KINDS
        kinds += sorted(ECOLOGY_KINDS) + ["open_mailbox"]
        from ...cabin_life import ACTIVITIES as CABIN_ACTIVITIES
        kinds += sorted(CABIN_ACTIVITIES)
        properties["world_action"] = obj(
            {
                "operation": choice(["start", "cancel", "interrupt", "resume"]),
                "steps": rows(
                    {
                        "kind": choice(kinds),
                        "target_id": text(160),
                        "title": text(60),
                        "text": text(1000),
                        "mode": choice(["writing", "organize", "gaming"] + list(LIGHTS) + list(CURTAINS)),
                        "position": choice(list(POSITIONS)),
                        "record_id": text(160),
                        "project_id": text(100),
                        "parts": {"type": "integer", "minimum": 1, "maximum": 8},
                        "section": {"type": "integer", "minimum": 1, "maximum": 8},
                    },
                    ("kind",),
                    6,
                ),
            },
            ("operation",),
        )
        properties["movement"] = obj(
            {
                "kind": choice(["locate", "plan", "depart"]),
                "target_id": text(160),
                "not_before": stamp(),
            },
            ("kind", "target_id"),
        )
        properties["daily_plan"] = rows(
            {"start": stamp(), "end": stamp(), "activity": text(120)},
            ("start", "end", "activity"),
            12,
        )
        properties["plan_id"] = text(80)
        properties["agenda_changes"] = rows(
            {
                "id": text(80),
                "status": choice(["deferred", "cancelled"]),
                "start": stamp(),
                "end": stamp(),
                "reason": text(200),
            },
            ("id", "status", "reason"),
            12,
        )
        properties["world_updates"] = world_updates_schema
    if request.get("care_policy", {}).get("enabled") and scoped:
        properties["care_waits"] = rows(
            {
                **member,
                "reason_kind": choice(["health_concern", "travel_checkin", "agreed_checkin"]),
                "reason": text(300),
                "waiting_for": text(300),
                "evidence_quote": text(300),
                "not_before": stamp(),
                "expires_at": stamp(),
            },
            (
                "subject_id",
                "reason_kind",
                "reason",
                "waiting_for",
                "evidence_quote",
                "source_ids",
                "not_before",
                "expires_at",
            ),
            4,
        )
    return obj(properties, ("no_change",))
