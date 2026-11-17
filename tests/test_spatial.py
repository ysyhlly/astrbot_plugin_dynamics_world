import copy

import pytest

from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.spatial import SpatialState, route
from astrbot_plugin_dynamics_world.map_service import convert, suggested_places

SCOPE = {
    "platform": "qq",
    "umo": "qq:GroupMessage:one",
    "persona_id": "p",
    "instance_id": "p",
}
GLOBAL = dict(SCOPE, platform="", umo="")


def document():
    return {
        "schema_version": 1,
        "seed": "stable",
        "generator": "test fixture",
        "width": 100,
        "height": 100,
        "image": "data:image/png;base64,",
        "seconds_per_unit": 10,
        "places": [
            {"id": "a", "name": "住所", "x": 10, "y": 10, "cell": 0},
            {"id": "b", "name": "书店", "x": 90, "y": 10, "cell": 2},
        ],
        "graph": {
            "points": [[10, 10], [50, 10], [90, 10]],
            "edges": [[1], [0, 2], [1]],
        },
        "roads": [],
    }


@pytest.fixture
def rig(tmp_path):
    now = [1794366000.0]
    response = {"no_change": True}

    async def model(request):
        return copy.deepcopy(response)

    engine = NarrativeEngine(
        tmp_path / "life.sqlite3",
        {"mode": "narrative", "persona_id": "p", "narrative_all_groups": True},
        model,
        lambda: now[0],
    )
    engine.spatial = SpatialState(engine)
    engine.spatial.install(SCOPE, document())
    return engine, now, response


def state(engine, scope=SCOPE):
    with engine._db() as db:
        return engine._snapshot(db, scope, engine.clock())


def act(engine, kind, target="a", **extra):
    current = state(engine)["spatial"]
    return engine.spatial.admin_action(
        SCOPE,
        {
            "kind": kind,
            "target_id": target,
            "map_revision": current["map_revision"],
            "position_revision": current["revision"],
            **extra,
        },
    )


def test_generation_preserves_unknown_location_and_document_version(rig):
    engine, _, _ = rig
    current = state(engine)["spatial"]
    assert current["phase"] == "unknown" and current["position"] is None
    assert engine.spatial.public_map(SCOPE)["seed"] == "stable"
    assert engine.spatial.public_map(SCOPE, 1) == {"revision": 1, "unchanged": True}
    assert "graph" not in engine.spatial.public_map(SCOPE)


def test_plan_never_moves_departure_and_arrival_follow_program_clock(rig):
    engine, now, _ = rig
    act(engine, "locate")
    act(engine, "plan", "b", not_before=now[0] + 100)
    assert state(engine)["spatial"]["place_id"] == "a"
    assert state(engine)["spatial"]["journey"] is None
    act(engine, "depart", "b")
    assert "前往书店" in state(engine)["activity"]
    now[0] += 400
    snapshot = state(engine)
    assert snapshot["spatial"]["position"] == [50, 10]
    assert snapshot["spatial"]["place_id"] == "a"
    now[0] += 400
    snapshot = state(engine)
    assert (
        snapshot["spatial"]["place_id"] == "b"
        and snapshot["spatial"]["journey"] is None
    )
    assert snapshot["activity"] == "抵达书店"
    with engine._db() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM world_map_events WHERE kind='movement.arrived'"
            ).fetchone()[0]
            == 1
        )
    state(engine)
    with engine._db() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM world_map_events WHERE kind='movement.arrived'"
            ).fetchone()[0]
            == 1
        )


@pytest.mark.asyncio
async def test_pause_freezes_progress_and_restart_preserves_journey(rig):
    engine, now, _ = rig
    act(engine, "locate")
    act(engine, "depart", "b")
    now[0] += 100
    await engine.set_paused(True)
    before = state(engine)["spatial"]["position"]
    now[0] += 10000
    assert state(engine)["spatial"]["position"] == before
    await engine.set_paused(False)
    assert state(engine)["spatial"]["position"] == before
    restored = NarrativeEngine(engine.path, engine.config, engine.model, engine.clock)
    restored.spatial = SpatialState(restored)
    assert state(restored)["spatial"]["position"] == before
    now[0] += 700
    assert state(restored)["spatial"]["place_id"] == "b"
    await restored.close()
    await engine.close()


def test_map_rebuild_and_place_edit_are_blocked_during_journey(rig):
    engine, _, _ = rig
    act(engine, "locate")
    act(engine, "depart", "b")
    with pytest.raises(ValueError, match="正在移动"):
        engine.spatial.install(SCOPE, document(), 1)
    with pytest.raises(ValueError):
        engine.spatial.save_place(
            SCOPE, {"name": "公园", "x": 30, "y": 10, "expected_revision": 1}
        )
    assert state(engine)["spatial"]["journey"]


def test_version_guard_and_invalid_targets_have_no_effect(rig):
    engine, now, _ = rig
    before = state(engine)["spatial"]
    for action in (
        {
            "kind": "locate",
            "target_id": "missing",
            "map_revision": 1,
            "position_revision": before["revision"],
        },
        {
            "kind": "locate",
            "target_id": "a",
            "map_revision": 0,
            "position_revision": before["revision"],
        },
    ):
        with pytest.raises(ValueError):
            engine.spatial.admin_action(SCOPE, action)
    assert state(engine)["spatial"] == before


def test_stable_ids_shared_role_location_but_no_cross_character_leak(rig):
    engine, _, _ = rig
    act(engine, "locate")
    assert (
        state(engine, dict(SCOPE, umo="qq:GroupMessage:two"))["spatial"]["place_id"]
        == "a"
    )
    other = state(engine, dict(SCOPE, persona_id="other", instance_id="other"))[
        "spatial"
    ]
    assert not other["available"]


def test_land_graph_refuses_unconnected_islands():
    data = document()
    data["graph"]["edges"] = [[1], [0], []]
    with pytest.raises(ValueError, match="陆路"):
        route(data, 0, 2)


def test_model_moves_global_only_and_rejects_teleport_and_stale_maps(rig):
    engine, now, _ = rig
    request = {"scope": SCOPE, "snapshot": state(engine), "now": now[0]}
    with pytest.raises(ValueError, match="全局"):
        engine.spatial.validate({"kind": "locate", "target_id": "a"}, request)
    request["scope"] = GLOBAL
    action = engine.spatial.validate({"kind": "locate", "target_id": "a"}, request)
    engine.spatial.install(SCOPE, document(), 1)
    with engine._db() as db:
        with pytest.raises(ValueError, match="已变化"):
            engine.spatial.commit(db, GLOBAL, action, now[0])
    act(engine, "locate")
    request["snapshot"] = state(engine)
    with pytest.raises(ValueError, match="瞬移"):
        engine.spatial.validate({"kind": "locate", "target_id": "b"}, request)


@pytest.mark.asyncio
async def test_life_model_movement_commits_in_same_transaction(rig):
    engine, now, response = rig
    response.clear()
    response.update(no_change=False, movement={"kind": "locate", "target_id": "a"})
    event = {
        "event_id": "global-tick",
        "type": "life.tick",
        "scope": GLOBAL,
        "occurred_at": now[0],
        "received_at": now[0],
        "fact_kind": "fiction",
        "text": "生活推进",
    }
    result = await engine.advance([event])
    assert result["status"] == "advanced"
    assert result["snapshot"]["spatial"]["place_id"] == "a"
    assert not engine.spatial.public_map(SCOPE).get("events")
    with engine._db() as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    await engine.close()


def test_manual_place_edit_retains_ids_and_unknown_position(rig):
    engine, _, _ = rig
    engine.spatial.save_place(
        SCOPE,
        {
            "name": "安静的书店",
            "place_id": "b",
            "x": 90,
            "y": 10,
            "expected_revision": 1,
        },
    )
    data = engine.spatial.public_map(SCOPE)
    assert data["places"][1]["id"] == "b" and data["revision"] == 2
    assert state(engine)["spatial"]["phase"] == "unknown"
    with engine._db() as db:
        assert db.execute("SELECT COUNT(*) FROM world_map_versions").fetchone()[0] == 2


def test_convert_keeps_names_stable_and_chooses_connected_land():
    raw = {
        "width": 100,
        "height": 100,
        "points": [[10, 10], [50, 10], [90, 10], [90, 90]],
        "edges": [[1], [0, 2], [1], []],
        "heights": [30, 40, 50, 0],
        "burgs": [{"name": "One", "cell": 0}, {"name": "Two", "cell": 2}],
        "image": "data:image/png;base64,",
    }
    first = convert(raw, "seed", ["住所", "书店"])
    second = convert(raw, "seed", ["住所", "书店"])
    assert first["places"] == second["places"]
    assert {p["name"] for p in first["places"]} == {"住所", "书店"}
    assert len(first["graph"]["points"]) == 3 and first["roads"]


def test_worldbook_outdoor_places_exclude_character_names_and_whole_region():
    data = {
        "world_items": [
            {"text": "世界-监狱岛\n有深林、花田、湖、吊桥。"},
            {"text": "世界-牢屋敷结构\n1F：厨房、食堂。森林有守卫。"},
            {"text": "角色-安安\n喜欢读书"},
        ]
    }
    assert suggested_places(data) == ["深林", "花田", "湖", "吊桥", "牢屋敷"]


def test_same_revision_different_character_maps_have_distinct_world_ids(rig):
    engine, _, _ = rig
    other = dict(SCOPE, persona_id="other", instance_id="other")
    engine.spatial.install(other, document())
    a, b = engine.spatial.public_map(SCOPE), engine.spatial.public_map(other)
    assert a["revision"] == b["revision"] and a["world_id"] != b["world_id"]


def test_prompt_drops_detailed_route_geometry(rig):
    from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
        build_narrative_prompt,
    )

    engine, now, _ = rig
    act(engine, "locate")
    act(engine, "depart", "b")
    snapshot = state(engine)
    prompt = build_narrative_prompt(
        {"scope": GLOBAL, "now": now[0], "snapshot": snapshot, "events": []}, {}
    )
    assert '"path":' not in prompt and '"target_id"' not in prompt
    assert snapshot["spatial"]["journey"]["path"]  # Caller snapshot was not mutated.


def test_migration_does_not_overwrite_a_map_only_destination(tmp_path):
    from astrbot_plugin_dynamics_world.migration import destination_has_data

    initial = tmp_path / "initial"
    initial.mkdir()

    async def model(_):
        return {"no_change": True}

    engine = NarrativeEngine(initial / "narrative.sqlite3", {}, model)
    engine.spatial = SpatialState(engine)
    engine.spatial.install(SCOPE, document())
    assert destination_has_data(tmp_path)


def test_cancelling_only_a_plan_preserves_current_activity(rig):
    engine, _, _ = rig
    act(engine, "locate")
    original = state(engine)["activity"]
    act(engine, "plan", "b")
    act(engine, "cancel")
    assert state(engine)["activity"] == original
    with pytest.raises(ValueError, match="没有"):
        act(engine, "cancel")
