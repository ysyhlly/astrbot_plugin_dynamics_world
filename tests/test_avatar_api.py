import base64
from types import SimpleNamespace

import pytest
import pytest_asyncio

from astrbot_plugin_dynamics_world.world.core import web_api as transport
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from test_avatar_models import GEOMETRY, json_package, png, texture
from test_scenes import finish, start
from test_spatial import document
from test_world_integration import UMO, make_plugin, seed


OTHER_UMO = 'qq:GroupMessage:other'


@pytest_asyncio.fixture
async def avatar_api(tmp_path, monkeypatch):
    plugin, _, routes = await make_plugin(tmp_path, monkeypatch)
    try:
        seed(plugin)
        monkeypatch.setattr(transport, 'json_response', lambda data=None, **kwargs: data)
        monkeypatch.setattr(transport, 'error_response', lambda message, **kwargs: {
            'error': message, 'code': kwargs['status_code'],
        })

        async def call(endpoint, *, body=None, **query):
            method = 'GET' if body is None else 'POST'
            headers = {
                'Host': 'dashboard.local',
                'Origin': 'https://dashboard.local',
                'Sec-Fetch-Site': 'same-origin',
            }
            raw = SimpleNamespace(
                state=SimpleNamespace(dashboard_g=SimpleNamespace(username='admin')),
                method=method,
                headers=headers,
                cookies={},
            )
            request = SimpleNamespace(
                query={'umo': UMO, **query},
                json=lambda **kwargs: body,
                headers=headers,
                cookies={},
                method=method,
                username='admin',
                _request=raw,
            )
            monkeypatch.setattr(transport, 'request', request)
            return await routes[(f'/astrbot_plugin_dynamics_world/{endpoint}', (method,))]()

        yield plugin, call
    finally:
        await plugin.terminate()


def upload_body(raw, filename='test-avatar.json'):
    return {'umo': UMO, 'filename': filename, 'name': '测试角色', 'file_base64': base64.b64encode(raw).decode('ascii')}


def load_scene(engine, scope):
    with engine._db() as db:
        return engine.scenes.load(db, scope)


def seed_scene(engine, scope):
    engine.spatial.install(scope, document())
    with engine._db() as db:
        actor = engine.spatial.snapshot(db, scope, engine.clock())
    engine.spatial.admin_action(scope, {'kind': 'locate', 'target_id': 'a',
        'map_revision': actor['map_revision'], 'position_revision': actor['revision']})
    engine.scenes.bootstrap(scope, {'expected_revision': 0, 'place_id': 'a'})


@pytest.mark.asyncio
async def test_avatar_routes_obey_panel_disabled_and_read_only_guards(avatar_api):
    plugin, call = avatar_api
    panel = plugin.world.web.settings.raw.setdefault('web_panel', {})
    payload = upload_body(json_package(textures=[texture('默认', png())]))
    selection = {'umo': UMO, 'expected_revision': 0, 'model_id': 'builtin'}
    panel['enabled'] = False
    for endpoint, params in [('avatar', {}), ('avatar_model', {'model_id': 'builtin'}),
        ('avatar', {'body': selection}), ('avatar_upload', {'body': payload})]:
        assert (await call(endpoint, **params))['code'] == 403

    panel.update(enabled=True, allow_write=False)
    assert (await call('avatar', body=selection))['code'] == 403
    assert (await call('avatar_upload', body=payload))['code'] == 403
    assert not (plugin.data_root / 'avatar-models').exists()
    catalog = (await call('avatar'))['data']
    assert catalog['can_write'] is False
    assert catalog['selection']['revision'] == 0
    assert (await call('avatar_model', model_id='builtin'))['data']['id'] == 'builtin'


@pytest.mark.asyncio
async def test_avatar_upload_catalog_selection_round_trip_preserves_world_scene(avatar_api, monkeypatch):
    plugin, call = avatar_api
    engine = plugin.life.narrative
    now = [1_794_366_000.0]
    monkeypatch.setattr(engine, 'clock', lambda: now[0])
    scope, _ = await plugin.web.scope(UMO)
    seed_scene(engine, scope)
    start(engine, preset='write_note', title='原有笔记', text='角色模型操作须保留这行笔记。')
    finish(engine, now)
    before = load_scene(engine, scope)
    notes = next(item['notes'] for item in before[2]['items'].values() if item['kind'] == 'notebook')
    assert notes[0]['text'] == '角色模型操作须保留这行笔记。'

    variants = [texture('晴空', png()), texture('夜色', png('blue'))]
    uploaded = (await call('avatar_upload', body=upload_body(json_package(textures=variants))))['data']
    assert uploaded['geometry'] == GEOMETRY['minecraft:geometry'][0]
    assert uploaded['textures'] == variants
    catalog = (await call('avatar'))['data']
    assert catalog['scene_available'] is True
    assert catalog['can_write'] is True
    assert catalog['rooms'] == list(before[2]['rooms'].values())
    assert catalog['models'][1]['id'] == uploaded['id']
    assert catalog['models'][1]['texture_names'] == ['晴空', '夜色']
    assert catalog['selection']['model_id'] == 'builtin'

    room, garden = (entry['id'] for entry in catalog['rooms'])
    selection = {'model_id': uploaded['id'], 'texture_index': 1, 'home_room_id': room, 'garden_room_id': garden}
    payload = {'umo': UMO, 'expected_revision': 0, **selection}
    assert (await call('avatar', body=payload))['data'] == {'revision': 1, **selection}
    assert (await call('avatar', body=payload))['code'] == 409
    assert (await call('avatar'))['data']['selection'] == {'revision': 1, **selection}
    assert (await call('avatar_model', model_id=uploaded['id']))['data'] == uploaded
    assert (await call('avatar_model', model_id='0' * 64))['code'] == 404
    assert load_scene(engine, scope) == before


@pytest.mark.asyncio
async def test_avatar_room_bindings_validate_current_scene_and_are_scoped(avatar_api):
    plugin, call = avatar_api
    engine = plugin.life.narrative
    plugin.world.store.upsert_card(CharacterCard(id='other-card', name='另一角色', persona_id='other'))
    plugin.world.store.update_session(OTHER_UMO, card_id='other-card')
    scope, _ = await plugin.web.scope(UMO)
    other_scope, _ = await plugin.web.scope(OTHER_UMO)
    seed_scene(engine, scope)
    seed_scene(engine, other_scope)
    catalog = (await call('avatar'))['data']
    other_catalog = (await call('avatar', umo=OTHER_UMO))['data']
    home, garden = (room['id'] for room in catalog['rooms'])
    other_home = other_catalog['rooms'][0]['id']
    assert other_home not in {home, garden}

    for fields in [{'home_room_id': other_home}, {'garden_room_id': '房间'},
        {'home_room_id': home, 'garden_room_id': home}]:
        result = await call('avatar', body={'umo': UMO, 'expected_revision': 0, **fields})
        assert result['code'] == 409
    chosen = (await call('avatar', body={'umo': UMO, 'expected_revision': 0,
        'home_room_id': home, 'garden_room_id': garden}))['data']
    duplicate = await call('avatar', body={'umo': UMO, 'expected_revision': 1, 'garden_room_id': home})
    assert duplicate['code'] == 409
    assert '同一个房间' in duplicate['error']
    assert (await call('avatar'))['data']['selection'] == chosen
    assert (await call('avatar', umo=OTHER_UMO))['data']['selection'] == other_catalog['selection']

    other_chosen = (await call('avatar', body={'umo': OTHER_UMO, 'expected_revision': 0, 'home_room_id': other_home}))['data']
    assert other_chosen['home_room_id'] == other_home and other_chosen['revision'] == 1
    assert (await call('avatar'))['data']['selection'] == chosen


@pytest.mark.asyncio
async def test_avatar_invalid_uploads_do_not_publish_models(avatar_api):
    plugin, call = avatar_api
    before = (await call('avatar'))['data']
    for payload, message in [
        (upload_body(b'YSM\x00\xff', 'encrypted.ysm'), '加密 .ysm'),
        (upload_body(b'{broken JSON'), 'JSON'),
        ({'umo': UMO, 'filename': 'test-avatar.json', 'file_base64': 'not+base64!'}, '编码'),
        (['not a JSON object'], 'JSON 对象'),
    ]:
        result = await call('avatar_upload', body=payload)
        assert result['code'] == 400
        assert message in result['error']
        assert (await call('avatar'))['data'] == before
    assert not (plugin.data_root / 'avatar-models').exists()
