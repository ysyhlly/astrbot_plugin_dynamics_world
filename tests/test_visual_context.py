import json

from test_spatial import SCOPE, GLOBAL, state, act
from test_scenes import setup, scene, start, finish
from astrbot_plugin_dynamics_world.visual_context import WorldVisualContext
from astrbot_plugin_dynamics_world.geography import configure_real
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    build_narrative_prompt,
)


def attach(rig):
    engine, now, _ = setup(rig)
    engine.visuals = WorldVisualContext(engine)
    return engine, now


def test_current_room_and_visible_props_ground_scene_without_private_notes_or_city_location(
    rig,
):
    engine, now = attach(rig)
    start(engine, preset="read")
    finish(engine, now)
    engine.environment.snapshot = lambda *args: {
        "available": True,
        "status": "ready",
        "fact_kind": "external_weather",
        "location": "深圳（参考城市）",
        "source": "test-weather",
        "current": {
            "temperature": 20,
            "label": "雨",
            "is_day": False,
            "effect": "rain",
        },
    }
    with engine._db() as db:
        key, rev, s = engine.scenes.load(db, SCOPE)
        notebook = next(i for i in s["items"].values() if i["kind"] == "notebook")
        notebook["notes"] = [
            {"text": "PRIVATE_NOTE_SENTINEL", "title": "PRIVATE_TITLE_SENTINEL"}
        ]
        engine.scenes.save(db, key, rev, s)
    visual = state(engine)["visual_sharing"]
    assert (
        visual["current_scene"]["place"] == "住所"
        and visual["current_scene"]["room"] == "房间"
    )
    assert visual["current_scene"]["visual_weather"]["condition"] == "雨"
    assert any("有遮蔽" in text for text in visual["limitations"])
    raw = json.dumps(visual, ensure_ascii=False)
    assert "PRIVATE_" not in raw and "latitude" not in raw and "longitude" not in raw
    assert "深圳" not in json.dumps(visual["current_scene"], ensure_ascii=False)
    assert visual["references_default"] == []


def test_in_progress_journey_does_not_turn_destination_into_a_sighting(rig):
    engine, now = attach(rig)
    act(engine, "depart", "b")
    visual = state(engine)["visual_sharing"]
    assert visual["current_scene"]["phase"] == "travelling"
    assert visual["current_scene"]["destination"] == "书店"
    assert not any(row.get("place") == "书店" for row in visual["recent_experiences"])
    journey = state(engine)["spatial"]["journey"]
    now[0] = journey["arrives_at"] + 1
    assert state(engine)["visual_sharing"]["current_scene"]["place"] == "书店"


def test_only_confirmed_same_world_receipts_are_shareable_not_admin_or_plans(rig):
    engine, now = attach(rig)
    start(engine, [{"kind": "enter", "target_id": scene(engine)["rooms"][0]["id"]}])
    finish(engine, now)
    visual = state(engine)["visual_sharing"]
    assert any(r["kind"] == "confirmed_room" for r in visual["recent_experiences"])
    assert all(
        r["basis"] == "completed_fictional_action" for r in visual["recent_experiences"]
    )
    configure_real(
        engine.spatial,
        SCOPE,
        {"name": "测试城市", "latitude": 22, "longitude": 114, "expected_revision": 1},
    )
    real = state(engine)["visual_sharing"]
    assert (
        real["current_scene"]["phase"] == "unknown" and not real["recent_experiences"]
    )


def test_unknown_location_and_stale_weather_do_not_fabricate_visual_conditions(rig):
    engine, now = attach(rig)
    engine.environment.snapshot = lambda *args: {
        "available": True,
        "status": "stale",
        "stale": True,
        "current": {"label": "雨", "is_day": False},
    }
    visual = state(engine)["visual_sharing"]
    assert "visual_weather" not in visual["current_scene"]
    other = dict(SCOPE, persona_id="other", instance_id="other")
    unknown = state(engine, other)["visual_sharing"]
    assert not unknown["available"] and not unknown["recent_experiences"]


def test_visual_rules_do_not_enter_background_life_provider_or_create_intents(rig):
    engine, now = attach(rig)
    request = {"scope": GLOBAL, "now": now[0], "events": [], "snapshot": state(engine)}
    prompt = build_narrative_prompt(request, {})
    payload = json.loads(prompt.split("有类型与来源的状态和事件：\n")[1])
    assert "visual_sharing" not in payload["snapshot"]
    assert request["snapshot"]["visual_sharing"]["context_only"]
    with engine._db() as db:
        assert db.execute("SELECT COUNT(*) FROM intents").fetchone()[0] == 0
