"""Persistence and attribution tests for continuing character behavior."""

import copy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "humanlike_life", Path(__file__).parents[1] / "life/core/narrative.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def rig(tmp_path):
    now = [1793000000.0]
    scope = {
        "platform": "qq",
        "umo": "qq:GroupMessage:a",
        "persona_id": "anan",
        "instance_id": "anan",
    }
    response = {}
    requests = []

    async def model(request):
        requests.append(request)
        if not request["scope"]["umo"]:
            return {
                "state": {
                    "activity_code": "reading",
                    "availability": "available",
                    "valid_until": now[0] + 86400,
                },
                "next_check": now[0] + 86400,
            }
        return copy.deepcopy(response)

    engine = MODULE.NarrativeEngine(
        tmp_path / "life.db",
        {"mode": "narrative", "persona_id": "anan", "narrative_all_groups": True},
        model,
        lambda: now[0],
    )

    def event(eid, actor="u1", text="你好", kind="chat.message", recipient=""):
        return {
            "event_id": eid,
            "scope": scope,
            "actor_id": actor,
            "text": text,
            "type": kind,
            "occurred_at": now[0],
            "received_at": now[0],
            "data": {"recipient_user_id": recipient},
        }

    return engine, now, scope, response, requests, event


@pytest.mark.asyncio
async def test_persist_scope_decay_and_no_change(rig):
    engine, now, scope, response, requests, event = rig
    response.update(
        humanlike={
            "preferences": [
                {"id": "games", "text": "喜欢讨论解谜游戏", "source_ids": ["a"]}
            ],
            "goals": [
                {
                    "id": "puzzle",
                    "text": "下次接着聊这道谜题",
                    "source_ids": ["a"],
                    "expires_at": now[0] + 1800,
                }
            ],
            "moods": [
                {
                    "subject_id": "u1",
                    "text": "被这个笑话逗得轻松",
                    "source_ids": ["a"],
                    "expires_at": now[0] + 1800,
                }
            ],
            "nicknames": [
                {
                    "subject_id": "u1",
                    "nickname": "小鱼",
                    "evidence_quote": "叫我小鱼",
                    "source_ids": ["a"],
                }
            ],
        }
    )
    result = await engine.advance([event("a", text="以后叫我小鱼")])
    assert result["status"] == "advanced"
    first = result["snapshot"]["humanlike"]
    assert first["moods"][0]["strength"] == 1
    await engine.close()
    engine = MODULE.NarrativeEngine(
        engine.path, engine.config, engine.model, engine.clock
    )
    assert (await engine.get_snapshot(scope))["humanlike"] == first
    assert not any(
        (await engine.get_snapshot(dict(scope, umo="qq:GroupMessage:b")))[
            "humanlike"
        ].values()
    )
    now[0] += 600
    response.clear()
    response["no_change"] = True
    assert (await engine.advance([event("b")]))["status"] == "no_change"
    snapshot = (await engine.get_snapshot(scope))["humanlike"]
    assert snapshot["moods"][0]["strength"] == 0.5
    assert snapshot["moods"][0]["updated_at"] == first["moods"][0]["updated_at"]
    now[0] += 1300
    snapshot = (await engine.get_snapshot(scope))["humanlike"]
    assert not snapshot["moods"] and not snapshot["goals"]
    assert snapshot["preferences"] and snapshot["nicknames"]
    await engine.close()


@pytest.mark.asyncio
async def test_bot_can_name_only_after_delivery_and_rejection_is_sticky(rig):
    engine, now, scope, response, requests, event = rig
    nickname = {
        "subject_id": "u1",
        "nickname": "存档侠",
        "evidence_quote": "存档侠",
        "source_ids": ["a"],
    }
    response["humanlike"] = {"nicknames": [nickname]}
    assert (
        await engine.advance(
            [
                event(
                    "a",
                    actor="bot",
                    text="存档侠，你又试了？",
                    kind="delivery.success",
                    recipient="u1",
                )
            ]
        )
    )["status"] == "advanced"
    response["humanlike"] = {
        "nicknames": [
            dict(
                nickname,
                status="rejected",
                evidence_quote="别这么叫我",
                source_ids=["b"],
            )
        ]
    }
    assert (await engine.advance([event("b", text="别这么叫我")]))[
        "status"
    ] == "advanced"
    snapshot = await engine.get_snapshot(scope)
    assert snapshot["humanlike"]["nicknames"][0]["status"] == "rejected"
    bad = dict(nickname, source_ids=["c"])
    request = {"scope": scope, "now": now[0], "snapshot": snapshot}
    with pytest.raises(ValueError, match="new member request"):
        engine._humanlike_change(
            {"nicknames": [bad]},
            request,
            {
                "c": event(
                    "c",
                    actor="bot",
                    text="存档侠",
                    kind="delivery.success",
                    recipient="u1",
                )
            },
        )
    response["humanlike"] = {
        "nicknames": [
            dict(
                nickname,
                nickname="小鱼",
                evidence_quote="以后叫我小鱼",
                source_ids=["d"],
            )
        ]
    }
    assert (await engine.advance([event("d", text="以后叫我小鱼")]))[
        "status"
    ] == "advanced"
    assert (await engine.get_snapshot(scope))["humanlike"]["nicknames"][0][
        "nickname"
    ] == "小鱼"


@pytest.mark.parametrize(
    "kind,actor,recipient,text,subject",
    [
        ("delivery.failure", "bot", "u1", "小鱼", "u1"),
        ("delivery.uncertain", "bot", "u1", "小鱼", "u1"),
        ("delivery.success", "bot", "u2", "小鱼", "u1"),
        ("chat.message", "u2", "", "叫他小鱼", "u1"),
        ("delivery.success", "u1", "u1", "小鱼", "u1"),
        ("chat.message", "u1", "", "你好", "u1"),
    ],
)
def test_bad_nickname_evidence_rejected(rig, kind, actor, recipient, text, subject):
    engine, now, scope, response, requests, event = rig
    source = event("a", actor, text, kind, recipient)
    with pytest.raises(ValueError):
        engine._humanlike_change(
            {
                "nicknames": [
                    {
                        "subject_id": subject,
                        "nickname": "小鱼",
                        "evidence_quote": "小鱼",
                        "source_ids": ["a"],
                    }
                ]
            },
            {"scope": scope, "now": now[0], "snapshot": {}},
            {"a": source},
        )


@pytest.mark.asyncio
async def test_no_change_effects_and_unverified_goal_completion_are_atomic(rig):
    engine, now, scope, response, requests, event = rig
    response.update(
        no_change=True,
        humanlike={
            "preferences": [{"id": "x", "text": "喜欢解谜", "source_ids": ["a"]}]
        },
    )
    assert (await engine.advance([event("a")]))["status"] == "invalid"
    assert not (await engine.get_snapshot(scope))["humanlike"]["preferences"]
    with pytest.raises(ValueError, match="execution receipt"):
        engine._humanlike_change(
            {
                "goals": [
                    {
                        "id": "x",
                        "text": "已经处理完",
                        "status": "done",
                        "source_ids": ["b"],
                    }
                ]
            },
            {"scope": scope, "now": now[0], "snapshot": {}},
            {"b": event("b")},
        )


@pytest.mark.asyncio
async def test_global_preferences_survive_activity_expiry(rig):
    engine, now, scope, response, requests, event = rig

    async def global_model(request):
        return {
            "humanlike": {
                "preferences": [
                    {
                        "id": "reading",
                        "text": "喜欢短篇小说",
                        "source_ids": [request["events"][0]["event_id"]],
                    }
                ]
            }
        }

    engine.model = global_model
    tick = dict(
        event("t", actor="system", kind="life.tick"),
        scope=dict(scope, umo="", platform=""),
    )
    assert (await engine.advance([tick]))["status"] == "advanced"
    now[0] += 7200
    snapshot = await engine.get_snapshot(scope)
    assert snapshot["stale"]
    assert snapshot["humanlike"]["preferences"][0]["text"] == "喜欢短篇小说"


@pytest.mark.asyncio
async def test_narrator_only_sees_current_members_names(rig):
    engine, now, scope, response, requests, event = rig
    response["humanlike"] = {
        "nicknames": [
            {
                "subject_id": "u1",
                "nickname": "小鱼",
                "evidence_quote": "小鱼",
                "source_ids": ["a"],
            }
        ]
    }
    assert (await engine.advance([event("a", text="叫我小鱼")]))["status"] == "advanced"
    response.clear()
    response["no_change"] = True
    assert (await engine.advance([event("b", actor="u2")]))["status"] == "no_change"
    assert requests[-1]["snapshot"]["humanlike"]["nicknames"] == []


@pytest.mark.asyncio
async def test_explicit_nickname_objection_persists_without_model_call(rig):
    engine, now, scope, response, requests, event = rig
    response["humanlike"] = {
        "nicknames": [
            {
                "subject_id": "u1",
                "nickname": "小鱼",
                "evidence_quote": "小鱼",
                "source_ids": ["a"],
            }
        ]
    }
    assert (await engine.advance([event("a", text="叫我小鱼")]))["status"] == "advanced"
    count = len(requests)
    objection = event("b", text="别叫我小鱼！")
    await engine.ingest_events([objection])
    snapshot = await engine.get_snapshot(scope)
    assert snapshot["humanlike"]["nicknames"][0]["status"] == "rejected"
    assert len(requests) == count
    with pytest.raises(ValueError, match="objection"):
        engine._humanlike_change(
            {
                "nicknames": [
                    {
                        "subject_id": "u1",
                        "nickname": "小鱼",
                        "evidence_quote": "别叫我小鱼",
                        "source_ids": ["b"],
                    }
                ]
            },
            {"scope": scope, "now": now[0], "snapshot": snapshot},
            {"b": objection},
        )
    await engine.ingest_events([objection])
    assert (await engine.get_snapshot(scope))["revision"] == snapshot["revision"]


@pytest.mark.asyncio
async def test_quoted_or_other_member_objection_does_not_revoke_name(rig):
    engine, now, scope, response, requests, event = rig
    response["humanlike"] = {
        "nicknames": [
            {
                "subject_id": "u1",
                "nickname": "小鱼",
                "evidence_quote": "小鱼",
                "source_ids": ["a"],
            }
        ]
    }
    await engine.advance([event("a", text="叫我小鱼")])
    await engine.ingest_events(
        [
            event("b", text="他刚说‘别叫我小鱼’"),
            event("c", actor="u2", text="别叫我小鱼"),
        ]
    )
    assert (await engine.get_snapshot(scope))["humanlike"]["nicknames"][0][
        "status"
    ] == "active"


def test_delayed_events_cannot_revive_old_mood_or_overwrite_new_objection(rig):
    engine, now, scope, response, requests, event = rig
    old = dict(event("a", text="叫我小鱼"), occurred_at=now[0] - 7200)
    request = {
        "scope": scope,
        "now": now[0],
        "snapshot": {
            "humanlike": {
                "nicknames": [
                    {
                        "subject_id": "u1",
                        "status": "rejected",
                        "updated_at": now[0] - 60,
                    }
                ]
            }
        },
    }
    result = engine._humanlike_change(
        {
            "moods": [{"subject_id": "u1", "text": "轻松", "source_ids": ["a"]}],
            "nicknames": [
                {
                    "subject_id": "u1",
                    "nickname": "小鱼",
                    "evidence_quote": "小鱼",
                    "source_ids": ["a"],
                }
            ],
        },
        request,
        {"a": old},
    )
    assert result == {"moods": [], "nicknames": []}
