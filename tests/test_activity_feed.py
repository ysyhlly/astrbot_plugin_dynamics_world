import json
import pytest
from test_spatial import SCOPE
from test_scenes import setup, start, finish, item
from astrbot_plugin_dynamics_world.activity_feed import page


def test_feed_only_contains_committed_effects_and_no_private_draft_text(rig):
    engine, now, _ = setup(rig)
    note = item(engine, "notebook")
    start(
        engine,
        [
            {"kind": "enter", "target_id": note["room_id"]},
            {"kind": "take", "target_id": note["id"]},
            {
                "kind": "project_start",
                "target_id": note["id"],
                "title": "小故事",
                "text": "PRIVATE_UNSAVED_OUTLINE",
                "parts": 1,
            },
        ],
    )
    with engine._db() as db:
        assert page(engine, db, SCOPE, category="projects")["events"] == []
    finish(engine, now)
    with engine._db() as db:
        result = page(engine, db, SCOPE, category="projects")
    assert len(result["events"]) == 1 and "小故事" in result["events"][0]["title"]
    assert "PRIVATE_UNSAVED_OUTLINE" not in json.dumps(result)


def test_paging_tied_timestamps_does_not_duplicate_or_skip_and_scope_isolated(rig):
    engine, now, _ = setup(rig)
    with engine._db() as db:
        key = engine.scenes.key(db, SCOPE)
        for i in range(12):
            engine.scenes.audit(
                db, key, "admin.item", now[0], {"name": "物品" + str(i)}
            )
        first = page(engine, db, SCOPE, limit=4, category="admin")
        seen = []
        result = first
        while True:
            seen += [r["id"] for r in result["events"]]
            if not result["next_cursor"]:
                break
            result = page(
                engine,
                db,
                SCOPE,
                before=result["next_cursor"],
                limit=4,
                category="admin",
            )
        expected = page(engine, db, SCOPE, limit=50, category="admin")["events"]
        assert len(seen) == len(set(seen)) == len(expected)
        other = dict(SCOPE, persona_id="other", instance_id="other")
        assert page(engine, db, other)["events"] == []
        with pytest.raises(ValueError):
            page(engine, db, SCOPE, before="bad")
        with pytest.raises(ValueError):
            page(engine, db, SCOPE, category="unknown")
