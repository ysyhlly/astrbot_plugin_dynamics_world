import pytest

from test_spatial import SCOPE, GLOBAL, state, act, document
from astrbot_plugin_dynamics_world.scenes import SceneService
from astrbot_plugin_dynamics_world.weather import EnvironmentService
from astrbot_plugin_dynamics_world.geography import configure_real, switch_mode


def setup(rig):
    engine, now, response = rig
    engine.environment = EnvironmentService(engine)
    engine.scenes = SceneService(engine)
    act(engine, "locate", "a")
    engine.scenes.bootstrap(SCOPE, {"expected_revision": 0, "place_id": "a"})
    return engine, now, response


def scene(engine):
    return state(engine)["scene"]


def item(engine, kind):
    return next(i for i in scene(engine)["items"] if i["kind"] == kind)


def start(engine, steps=None, preset=None, **extra):
    snap = scene(engine)
    return engine.scenes.administer(
        SCOPE,
        {
            "action": "preset" if preset else "start",
            "expected_revision": snap["revision"],
            "steps": steps or [],
            "preset": preset,
            **extra,
        },
    )


def step(engine, now):
    action = scene(engine)["action"]
    assert action
    now[0] = action["step_ends_at"] + 1
    return scene(engine)


def finish(engine, now):
    for _ in range(8):
        if not scene(engine)["action"]:
            return scene(engine)
        step(engine, now)
    raise AssertionError("flow did not finish")


def test_bootstrap_preserves_map_and_unknown_room_without_fabricated_history(rig):
    engine, now, _ = setup(rig)
    s = scene(engine)
    assert s["room_id"] is None and s["room_name"] == "房间待确认"
    assert len(s["rooms"]) == 2 and len(s["items"]) == 5 and not s["action"]
    assert all(not i["carried"] for i in s["items"])
    assert engine.spatial.public_map(SCOPE)["revision"] == 1
    with pytest.raises(ValueError):
        engine.scenes.bootstrap(
            SCOPE, {"expected_revision": s["revision"], "place_id": "a"}
        )
    with engine._db() as db:
        assert db.execute("SELECT COUNT(*) FROM diary").fetchone()[0] == 0
        assert not engine.scenes.snapshot(
            db, dict(SCOPE, persona_id="other", instance_id="other"), now[0]
        )["available"]


def test_read_flow_has_timed_steps_and_exactly_once_bookmark(rig):
    engine, now, _ = setup(rig)
    start(engine, preset="read")
    assert item(engine, "book")["page"] == 0 and not item(engine, "book")["carried"]
    after = step(engine, now)
    assert after["room_name"] == "房间" and after["action"]["index"] == 1
    assert item(engine, "book")["page"] == 0 and not item(engine, "book")["carried"]
    step(engine, now)
    assert item(engine, "book")["carried"] and item(engine, "book")["page"] == 0
    after = step(engine, now)
    assert after["action"] is None and item(engine, "book")["page"] == 10
    for _ in range(4):
        scene(engine)
    assert item(engine, "book")["page"] == 10
    with engine._db() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM world_scene_events WHERE kind='step.completed'"
            ).fetchone()[0]
            == 3
        )


def test_invalid_remote_take_and_closed_room_have_no_side_effect(rig):
    engine, now, _ = setup(rig)
    with pytest.raises(ValueError, match="物品不在"):
        start(engine, [{"kind": "take", "target_id": item(engine, "book")["id"]}])
    s = scene(engine)
    room = next(r for r in s["rooms"] if r["name"] == "房间")
    engine.scenes.configure(
        SCOPE,
        dict(
            action="room",
            expected_revision=s["revision"],
            place_id="a",
            room_id=room["id"],
            name="房间",
            sheltered=True,
            accessible=False,
            water=True,
        ),
    )
    with pytest.raises(ValueError, match="不允许进入"):
        start(engine, preset="read")
    assert not scene(engine)["action"] and not item(engine, "book")["carried"]


def test_finite_water_and_refill_only_at_source(rig):
    engine, now, _ = setup(rig)
    start(engine, preset="drink")
    finish(engine, now)
    water = item(engine, "water")
    assert water["servings"] == 2
    for _ in range(2):
        start(engine, [{"kind": "drink", "target_id": water["id"]}])
        finish(engine, now)
    assert item(engine, "water")["servings"] == 0
    with pytest.raises(ValueError, match="余量"):
        start(engine, [{"kind": "drink", "target_id": water["id"]}])
    start(engine, [{"kind": "refill", "target_id": water["id"]}])
    finish(engine, now)
    assert item(engine, "water")["servings"] == 3
    start(engine, [{"kind": "leave"}])
    finish(engine, now)
    with pytest.raises(ValueError, match="水源"):
        start(engine, [{"kind": "refill", "target_id": water["id"]}])


@pytest.mark.asyncio
async def test_pause_restart_and_map_mode_switch_freeze_action(rig):
    engine, now, _ = setup(rig)
    start(engine, preset="read")
    step(engine, now)
    step(engine, now)
    now[0] += 100
    before = scene(engine)["action"]["progress"]
    await engine.set_paused(True)
    now[0] += 600
    assert scene(engine)["action"]["progress"] == before
    await engine.set_paused(False)
    engine.scenes = SceneService(engine)
    assert scene(engine)["action"]["progress"] == before
    configure_real(
        engine.spatial,
        SCOPE,
        {"name": "test", "latitude": 22, "longitude": 114, "expected_revision": 1},
    )
    assert not scene(engine)["available"]
    now[0] += 1000
    switch_mode(engine.spatial, SCOPE, "virtual", 2)
    assert scene(engine)["action"]["progress"] == before
    finish(engine, now)
    assert item(engine, "book")["page"] == 10


def test_cancel_retains_completed_take_and_map_edit_guard(rig):
    engine, now, _ = setup(rig)
    start(engine, preset="read")
    step(engine, now)
    step(engine, now)
    with pytest.raises(ValueError):
        engine.spatial.install(SCOPE, document(), 1)
    engine.scenes.administer(
        SCOPE, {"action": "cancel", "expected_revision": scene(engine)["revision"]}
    )
    assert item(engine, "book")["carried"] and item(engine, "book")["page"] == 0
    assert scene(engine)["last_action"]["status"] == "cancelled"
    broken = document()
    broken["places"] = broken["places"][1:]
    with pytest.raises(ValueError, match="移除"):
        engine.spatial.install(SCOPE, broken, 1)


def test_rain_walk_uses_real_journey_and_rain_consequences(rig):
    engine, now, _ = setup(rig)
    engine.environment.snapshot = lambda *args: {
        "available": True,
        "status": "ready",
        "source": "test",
        "location": "world",
        "timezone": "Asia/Shanghai",
        "current": {"effect": "rain", "label": "雨", "temperature": 20, "is_day": True},
    }
    start(engine, preset="rain_walk", target_id="b")
    for _ in range(5):
        if (
            scene(engine)["action"]["steps"][scene(engine)["action"]["index"]]["kind"]
            == "travel"
        ):
            break
        step(engine, now)
    assert (
        state(engine)["spatial"]["phase"] == "travelling"
        and item(engine, "umbrella")["open"]
    )
    now[0] += 60
    scene(engine)
    now[0] += 60
    scene(engine)
    assert item(engine, "umbrella")["wet"] and scene(engine)["wetness"] < 5
    finish(engine, now)
    assert (
        state(engine)["spatial"]["place_id"] == "b"
        and scene(engine)["last_action"]["status"] == "completed"
    )


def test_model_action_is_global_version_guarded_and_receipts_are_not_early(rig):
    engine, now, _ = setup(rig)
    request = {"scope": GLOBAL, "snapshot": state(engine)}
    command = engine.scenes.validate(
        {"operation": "start", "steps": [{"kind": "rest"}]}, request
    )
    with pytest.raises(ValueError):
        engine.scenes.validate(
            {"operation": "start", "steps": [{"kind": "rest"}]},
            dict(request, scope=SCOPE),
        )
    start(engine, [{"kind": "rest"}])
    with pytest.raises(ValueError):
        with engine._db() as db:
            engine.scenes.commit(db, GLOBAL, command, now[0])
    assert not any(r["kind"] == "action.completed" for r in scene(engine)["receipts"])


@pytest.mark.asyncio
async def test_completed_flow_reaches_life_model_once(rig):
    engine, now, _ = setup(rig)
    calls = []

    async def model(request):
        calls.append(request)
        return {"no_change": True}

    engine.model = model
    start(engine, [{"kind": "rest"}])
    finish(engine, now)
    await engine.tick()
    assert any(
        e.get("data", {}).get("trigger") == "world_action_completed"
        for req in calls
        for e in req["events"]
    )
    count = len(calls)
    await engine.tick()
    assert len(calls) == count


@pytest.mark.asyncio
async def test_proposed_diary_is_deferred_until_action_receipts(rig):
    engine, now, response = setup(rig)
    request = {
        "scope": GLOBAL,
        "now": now[0],
        "needs_daily_plan": False,
        "snapshot": state(engine, GLOBAL),
        "events": [{"event_id": "t", "type": "life.tick", "fact_kind": "fiction"}],
    }
    with pytest.raises(ValueError, match="reading"):
        engine._validate_change({"state": {"activity_code": "reading"}}, request)
    change = engine._validate_change(
        {
            "world_action": {"operation": "start", "steps": [{"kind": "rest"}]},
            "diary": [
                {
                    "text": "我已经休息好了",
                    "occurred_at": now[0],
                    "fact_kind": "fiction",
                    "source_ids": ["t"],
                }
            ],
        },
        request,
    )
    assert change["diary"] == [] and change["world_action"]["deferred_diary_count"] == 1


def test_unprotected_rain_wets_book_and_blocks_reading(rig):
    engine, now, _ = setup(rig)
    start(engine, preset="read")
    finish(engine, now)
    start(engine, [{"kind": "leave"}, {"kind": "travel", "target_id": "b"}])
    step(engine, now)
    engine.environment.snapshot = lambda *args: {
        "available": True,
        "status": "ready",
        "source": "test",
        "location": "world",
        "timezone": "Asia/Shanghai",
        "current": {"effect": "rain", "label": "雨", "temperature": 20, "is_day": True},
    }
    now[0] += 31
    scene(engine)
    now[0] += 60
    scene(engine)
    assert item(engine, "book")["wet"] and scene(engine)["wetness"] > 5
    finish(engine, now)
    with pytest.raises(ValueError, match="干燥"):
        start(engine, [{"kind": "read", "target_id": item(engine, "book")["id"]}])


def test_cancelling_flow_does_not_teleport_an_active_journey(rig):
    engine, now, _ = setup(rig)
    start(engine, [{"kind": "travel", "target_id": "b"}])
    journey = state(engine)["spatial"]["journey"]
    engine.scenes.administer(
        SCOPE, {"action": "cancel", "expected_revision": scene(engine)["revision"]}
    )
    assert state(engine)["spatial"]["journey"]["id"] == journey["id"]
    assert not scene(engine)["action"]
    now[0] = journey["arrives_at"] + 1
    assert state(engine)["spatial"]["place_id"] == "b"
