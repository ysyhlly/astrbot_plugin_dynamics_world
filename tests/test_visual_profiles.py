import copy
import hashlib
import json

import pytest

from test_spatial import rig, SCOPE, state
from test_scenes import setup, scene, start, finish, item
from astrbot_plugin_dynamics_world.visual_context import WorldVisualContext, RULES
from astrbot_plugin_dynamics_world.visual_profiles import VisualProfiles
from astrbot_plugin_dynamics_world.geography import configure_real, switch_mode


def prepared(rig):
    engine, now, _ = setup(rig)
    engine.visuals = WorldVisualContext(engine)
    profiles = engine.visuals.profiles
    profiles.asset_root.mkdir()
    assets = {}
    for key, role in [('official', 'style'), ('room', 'layout')]:
        data = (key + '-fixture').encode()
        (profiles.asset_root / (key + '.png')).write_bytes(data)
        assets[key] = {'file': key + '.png', 'role': role, 'sha256': hashlib.sha256(data).hexdigest()}
    (profiles.asset_root / 'index.json').write_text(json.dumps(assets))
    room = next(r['id'] for r in scene(engine)['rooms'] if r['name'] == '房间')
    start(engine, [{'kind': 'enter', 'target_id': room}]);finish(engine, now)
    original = copy.deepcopy(scene(engine)['items'])
    profiles.configure(SCOPE, {'action': 'style', 'asset_ids': ['official'], 'expected_revision': 0})
    profiles.configure(SCOPE, {'action': 'room', 'target_id': room, 'asset_id': 'room', 'layout': '床在左，书桌在右', 'expected_revision': 1})
    book = item(engine, 'book')['id']
    profiles.configure(SCOPE, {'action': 'item', 'target_id': book, 'home_room_id': room, 'appearance': '紫色金边硬封书', 'placement': '书桌左侧', 'expected_revision': 2})
    assert scene(engine)['items'] == original
    return engine, now, profiles, room, book


def design(engine):return state(engine)['visual_sharing']['visual_design']


def test_persistent_layout_reference_and_appearance_with_no_state_reset(rig):
    engine, now, profiles, room, book = prepared(rig)
    before = design(engine)
    assert [r['role'] for r in before['references']] == ['layout', 'style']
    assert before['items'][0]['placement'] == '书桌左侧'
    engine.visuals = WorldVisualContext(engine)
    assert design(engine) == before
    assert len(RULES) <= 12 and all(len(r) <= 240 for r in RULES)
    with pytest.raises(ValueError):
        profiles.configure(SCOPE, {'action': 'style', 'asset_ids': [], 'expected_revision': 0})


def test_carry_and_move_override_reference_and_appearance_follows_item(rig):
    engine, now, profiles, room, book = prepared(rig)
    start(engine, [{'kind': 'take', 'target_id': book}]);finish(engine, now)
    assert '随身携带' in design(engine)['items'][0]['placement']
    entry = next(r['id'] for r in scene(engine)['rooms'] if r['id'] != room)
    start(engine, [{'kind': 'leave'}, {'kind': 'enter', 'target_id': entry}, {'kind': 'put', 'target_id': book}]);finish(engine, now)
    assert 'layout' not in design(engine)
    assert design(engine)['items'][0]['appearance'] == '紫色金边硬封书'
    start(engine, [{'kind': 'leave'}, {'kind': 'enter', 'target_id': room}]);finish(engine, now)
    assert design(engine)['remove_from_layout'] == ['随身读物']
    assert not design(engine)['items']


def test_scope_map_mode_and_missing_or_changed_assets_fail_closed(rig):
    engine, now, profiles, room, book = prepared(rig)
    with engine._db() as db:
        other = profiles.project(db, dict(SCOPE, persona_id='other', instance_id='other'), {}, {})
        assert not other['references'] and not other['revision']
    configure_real(engine.spatial, SCOPE, {'name': '测试城市', 'latitude': 22, 'longitude': 114, 'expected_revision': 1})
    assert 'visual_design' not in state(engine)['visual_sharing']
    switch_mode(engine.spatial,SCOPE,'virtual',2)
    (profiles.asset_root / 'room.png').write_bytes(b'tampered')
    assert design(engine)['generation_ready'] is False
    assert design(engine)['missing_assets'] == ['room']
    assert [r['role'] for r in design(engine)['references']] == ['style']


def test_asset_paths_and_foreign_target_validation(rig):
    engine, now, profiles, room, book = prepared(rig)
    assets = json.loads((profiles.asset_root / 'index.json').read_text())
    assets['escape'] = dict(assets['official'], file='../outside.png')
    (profiles.asset_root / 'index.json').write_text(json.dumps(assets))
    assert 'escape' not in profiles.assets()
    with pytest.raises(ValueError):
        profiles.configure(SCOPE, {'action': 'room', 'target_id': 'foreign', 'asset_id': 'room', 'layout': 'x', 'expected_revision': 3})
