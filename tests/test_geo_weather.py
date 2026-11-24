import asyncio
import json

import pytest

from test_spatial import SCOPE, GLOBAL, state, act
from astrbot_plugin_dynamics_world.geography import (
    configure_real,
    switch_mode,
    distance_km,
)
from astrbot_plugin_dynamics_world.weather import (
    EnvironmentService,
    DEFAULTS,
    simulated,
)
from astrbot_plugin_dynamics_world.weather import response_error
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    build_narrative_prompt,
)


def real(engine, revision=1):
    return configure_real(
        engine.spatial,
        SCOPE,
        {
            "name": "测试城市",
            "latitude": 52.52,
            "longitude": 13.405,
            "timezone": "Europe/Berlin",
            "expected_revision": revision,
        },
    )


def weather(engine):
    with engine._db() as db:
        return engine.environment.snapshot(db, SCOPE, engine.clock())


def fixture_forecast(now):
    return {
        "timezone": "Europe/Berlin",
        "current": {
            "time": now,
            "temperature_2m": 9,
            "apparent_temperature": 7,
            "precipitation": 0.3,
            "wind_speed_10m": 8,
            "weather_code": 61,
            "is_day": 0,
        },
        "hourly": {
            "time": [now + 3600],
            "temperature_2m": [8],
            "weather_code": [61],
            "precipitation_probability": [75],
            "is_day": [0],
        },
        "daily": {"time": [now], "sunrise": [now - 3600], "sunset": [now + 3600]},
    }


def test_real_mode_retains_virtual_journey_and_restart(rig):
    engine, now, _ = rig
    act(engine, "locate")
    act(engine, "depart", "b")
    now[0] += 200
    before = state(engine)["spatial"]
    real(engine)
    assert state(engine)["spatial"]["phase"] == "unknown"
    now[0] += 5000
    switch_mode(engine.spatial, SCOPE, "virtual", 2)
    after = state(engine)["spatial"]
    assert (
        after["position"] == before["position"]
        and after["progress"] == before["progress"]
    )
    assert after["journey"]["arrives_at"] == before["journey"]["arrives_at"] + 5000
    assert after["map_revision"] == 3
    now[0] += 600
    assert state(engine)["spatial"]["place_id"] == "b"
    switch_mode(engine.spatial, SCOPE, "real", 3)
    assert state(engine)["spatial"]["map_type"] == "real"
    assert engine.spatial.public_map(SCOPE)["center"] == [13.405, 52.52]


@pytest.mark.asyncio
async def test_mode_switch_keeps_global_pause_and_version_guard(rig):
    engine, now, _ = rig
    act(engine, "locate")
    act(engine, "depart", "b")
    now[0] += 100
    await engine.set_paused(True)
    frozen = state(engine)["spatial"]["position"]
    now[0] += 300
    real(engine)
    now[0] += 500
    with pytest.raises(ValueError):
        switch_mode(engine.spatial, SCOPE, "virtual", 1)
    switch_mode(engine.spatial, SCOPE, "virtual", 2)
    assert state(engine)["spatial"]["position"] == frozen
    now[0] += 600
    await engine.set_paused(False)
    assert state(engine)["spatial"]["position"] == frozen
    now[0] += 700
    assert state(engine)["spatial"]["place_id"] == "b"


def test_real_coordinates_route_edit_and_role_isolation(rig):
    engine, now, _ = rig
    for bad in (float("nan"), float("inf"), True, 91, "52"):
        with pytest.raises(ValueError):
            configure_real(
                engine.spatial,
                SCOPE,
                {
                    "name": "bad",
                    "latitude": bad,
                    "longitude": 13,
                    "expected_revision": 1,
                },
            )
    real(engine)
    doc = engine.spatial.public_map(SCOPE)
    origin = doc["places"][0]["id"]
    act(engine, "locate", origin)
    engine.spatial.save_place(
        SCOPE, {"name": "公园", "x": 13.41, "y": 52.52, "expected_revision": 2}
    )
    target = engine.spatial.public_map(SCOPE)["places"][1]["id"]
    act(engine, "depart", target)
    journey = state(engine)["spatial"]["journey"]
    assert journey["route_kind"] == "straight_line_estimate"
    assert journey["arrives_at"] - now[0] == pytest.approx(
        distance_km([13.405, 52.52], [13.41, 52.52]) / 4.5 * 3600
    )
    other = dict(SCOPE, persona_id="other", instance_id="other")
    assert not state(engine, other)["spatial"]["available"]
    with pytest.raises(ValueError):
        switch_mode(engine.spatial, other, "real", 0)
    with pytest.raises(ValueError):
        engine.spatial.save_place(
            SCOPE, {"name": "test", "x": 13, "y": 52, "expected_revision": 3}
        )
    now[0] = journey["arrives_at"] + 1
    assert state(engine)["spatial"]["place_id"] == target


def test_saved_real_map_cannot_be_accidentally_replaced(rig):
    engine, _, _ = rig
    real(engine)
    switch_mode(engine.spatial, SCOPE, "virtual", 2)
    with pytest.raises(ValueError, match="已有保存"):
        real(engine, 3)
    assert state(engine)["spatial"]["map_type"] == "virtual"


def test_simulation_is_deterministic_no_network_and_can_be_disabled(rig):
    engine, now, _ = rig

    async def forbidden(*args):
        raise AssertionError("network")

    service = engine.environment = EnvironmentService(engine, forbidden)
    a = weather(engine)
    b = weather(engine)
    assert a == b and a["fact_kind"] == "fiction" and len(a["forecast"]) == 6
    service.schedule_all()
    assert not service.tasks
    assert "世界模拟" in state(engine)["activity"]
    service.configure(
        SCOPE, {"expected_revision": 0, "settings": dict(DEFAULTS, mode="off")}
    )
    assert weather(engine)["status"] == "off"
    assert "环境参考" not in state(engine)["activity"]
    with pytest.raises(ValueError):
        service.configure(SCOPE, {"expected_revision": 0, "settings": DEFAULTS})
    with pytest.raises(ValueError):
        service.configure(
            SCOPE,
            {"expected_revision": 1, "settings": dict(DEFAULTS, timezone="invalid")},
        )


@pytest.mark.asyncio
async def test_real_weather_cache_dedup_stale_retry_and_nonblocking_snapshot(rig):
    engine, now, _ = rig
    real(engine)
    calls = []
    gate = asyncio.Event()
    fail = [False]

    async def fetch(kind, params):
        calls.append(params)
        await gate.wait()
        if fail[0]:
            raise TimeoutError()
        return fixture_forecast(now[0])

    service = engine.environment = EnvironmentService(engine, fetch)
    assert weather(engine)["status"] == "pending"
    service.schedule(SCOPE)
    service.schedule(SCOPE)
    for _ in range(50):
        if calls:
            break
        await asyncio.sleep(0.01)
    assert len(calls) == 1 and weather(engine)["status"] == "pending"
    gate.set()
    await asyncio.gather(*list(service.tasks.values()))
    assert weather(engine)["current"]["temperature"] == 9
    assert "地图中心" in weather(engine)["location"]
    service.schedule(SCOPE)
    assert len(calls) == 1
    now[0] += 1801
    fail[0] = True
    service.schedule(SCOPE)
    await asyncio.gather(*list(service.tasks.values()))
    old = weather(engine)
    assert old["stale"] and old["current"]["temperature"] == 9 and old["error"]
    assert "环境参考" not in state(engine)["activity"]
    service.schedule(SCOPE)
    assert len(calls) == 2
    prompt = build_narrative_prompt(
        {"scope": GLOBAL, "snapshot": state(engine), "events": []}, {}
    )
    projected = json.loads(prompt.split("有类型与来源的状态和事件：\n")[1])
    assert "current" not in projected["snapshot"]["environment"]
    await service.close()


@pytest.mark.asyncio
async def test_weather_anchor_switch_does_not_leak_previous_location(rig):
    engine, now, _ = rig
    real(engine)

    async def fetch(kind, params):
        return fixture_forecast(now[0])

    service = engine.environment = EnvironmentService(engine, fetch)
    service.schedule(SCOPE)
    await asyncio.gather(*list(service.tasks.values()))
    old_key = weather(engine)["cache_key"]
    service.configure(
        SCOPE,
        {
            "expected_revision": 0,
            "settings": dict(
                DEFAULTS,
                mode="real",
                reference={"name": "东京", "latitude": 35.68, "longitude": 139.76},
            ),
        },
    )
    fresh = weather(engine)
    assert (
        fresh["cache_key"] != old_key
        and fresh["status"] == "pending"
        and "current" not in fresh
    )
    assert "东京" in fresh["location"]
    await service.close()


@pytest.mark.asyncio
async def test_cancellation_and_missing_reference(rig):
    engine, _, _ = rig

    async def fetch(*args):
        await asyncio.Event().wait()

    service = engine.environment = EnvironmentService(engine, fetch)
    with pytest.raises(ValueError, match="参考城市"):
        service.configure(
            SCOPE, {"expected_revision": 0, "settings": dict(DEFAULTS, mode="real")}
        )
    real(engine)
    service.schedule(SCOPE)
    task = next(iter(service.tasks.values()))
    await asyncio.sleep(0)
    await service.close()
    assert task.cancelled() and not service.tasks


def test_simulation_timezone_and_night():
    night = simulated("p", 1794358800, dict(DEFAULTS, timezone="UTC"))
    changed = simulated("p", 1794358800, dict(DEFAULTS, timezone="Asia/Shanghai"))
    assert night["current"]["is_day"] != changed["current"]["is_day"]


def test_weather_only_settings_block_destructive_legacy_import(tmp_path):
    from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
    from astrbot_plugin_dynamics_world.spatial import SpatialState
    from astrbot_plugin_dynamics_world.migration import destination_has_data

    async def model(_):
        return {"no_change": True}

    root = tmp_path / "initial"
    root.mkdir()
    engine = NarrativeEngine(root / "narrative.sqlite3", {}, model)
    engine.spatial = SpatialState(engine)
    service = EnvironmentService(engine)
    assert not destination_has_data(tmp_path)
    service.configure(
        SCOPE, {"expected_revision": 0, "settings": dict(DEFAULTS, mode="off")}
    )
    assert destination_has_data(tmp_path)


def test_429_has_specific_safe_reason_and_respects_retry_after():
    error = response_error(
        429,
        {
            "reason": "Hourly API request limit exceeded. Please try again in the next hour."
        },
    )
    assert error.rate_limited and error.retry_seconds == 3600 and "本小时" in str(error)
    assert (
        response_error(
            429, {"reason": "Daily API request limit exceeded"}
        ).retry_seconds
        == 86400
    )
    assert response_error(429, {}, "7200").retry_seconds == 7200
    assert (
        response_error(429, {}, "Thu, 01 Jan 1970 02:00:00 GMT", now=0).retry_seconds
        == 7200
    )
    assert response_error(503, {}, "bad").retry_seconds == 300


@pytest.mark.asyncio
async def test_rate_limit_stops_queued_places_and_survives_restart(rig):
    engine, now, _ = rig
    real(engine)
    calls = []

    async def fetch(*args):
        calls.append(args)
        raise response_error(429, {"reason": "Hourly API request limit exceeded"})

    service = engine.environment = EnvironmentService(engine, fetch)
    first = weather(engine)
    await asyncio.gather(
        service._refresh(first["cache_key"], first),
        service._refresh("different", dict(first, latitude=35)),
    )
    assert len(calls) == 1
    limited = weather(engine)
    assert limited["status"] == "unavailable" and "HTTP 429" in limited["error"]
    assert limited["retry_at"] == now[0] + 3600
    restored = EnvironmentService(engine, fetch)
    restored.schedule(SCOPE)
    assert not restored.tasks
    service.configure(
        SCOPE,
        {
            "expected_revision": 0,
            "settings": dict(
                DEFAULTS,
                mode="real",
                reference={"name": "另一城市", "latitude": 35, "longitude": 139},
            ),
        },
    )
    service.schedule(SCOPE)
    assert not service.tasks
    now[0] += 3601

    async def success(*args):
        return fixture_forecast(now[0])

    service.fetch = success
    service.schedule(SCOPE)
    await asyncio.gather(*list(service.tasks.values()))
    assert weather(engine)["status"] == "ready" and not weather(engine)["error"]
    await service.close()
    await restored.close()
