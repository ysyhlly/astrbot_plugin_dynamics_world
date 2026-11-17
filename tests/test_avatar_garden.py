import copy
import pytest
from test_spatial import GLOBAL
from test_scenes import setup, scene, start


def test_adding_garden_during_daily_action_preserves_running_step_and_existing_rooms(
    rig,
):
    engine, _, _ = setup(rig)
    start(engine, [{"kind": "rest"}])
    before = copy.deepcopy(scene(engine))
    engine.scenes.configure(
        GLOBAL,
        {
            "action": "room",
            "expected_revision": before["revision"],
            "place_id": before["place_id"],
            "name": "花园",
            "sheltered": False,
            "accessible": True,
            "water": False,
        },
    )
    after = scene(engine)
    assert after["action"]["id"] == before["action"]["id"]
    assert after["action"]["step_ends_at"] == before["action"]["step_ends_at"]
    assert all(room in after["rooms"] for room in before["rooms"])
    garden = next(room for room in after["rooms"] if room["name"] == "花园")
    assert not garden["sheltered"] and garden["accessible"]
    assert after["items"] == before["items"]
    with pytest.raises(ValueError, match="完成或取消"):
        engine.scenes.configure(
            GLOBAL,
            {
                "action": "room",
                "room_id": garden["id"],
                "expected_revision": after["revision"],
                "place_id": after["place_id"],
                "name": "改变旧房间",
                "sheltered": True,
                "accessible": False,
                "water": False,
            },
        )
