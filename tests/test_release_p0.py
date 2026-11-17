import copy,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_world_integration import make_plugin,UMO
from test_visual_profiles import prepared,design
from test_spatial import rig,SCOPE,state
from astrbot_plugin_dynamics_world.onboarding import FEATURES

def ready_context(plugin):
    provider=NS(provider_config={'id':'model/test','model':'test'},text_chat=AsyncMock())
    plugin.context.get_all_providers=lambda:[provider]
    plugin.context.get_registered_star=lambda name:NS(activated=True,star_cls=NS(get_world_integration_capabilities=lambda:{'schema_version':1,'features':dict.fromkeys(FEATURES,1)})) if name=='astrbot_plugin_chat_dynamics' else None
    personas={}
    async def get_persona(key):
        if key not in personas:raise KeyError(key)
        return personas[key]
    async def put(**kwargs):personas[kwargs['persona_id']]=kwargs
    plugin.context.persona_manager=NS(get_persona=get_persona,create_persona=put,update_persona=put)
    return personas

@pytest.mark.asyncio
async def test_fresh_install_can_finish_onboarding_without_media_or_chromium(tmp_path,monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch);ready_context(plugin)
    o=plugin.onboarding
    o.browser_status=AsyncMock(return_value={'installed':False,'module_available':True})
    try:
        assert not plugin.world.store.list_cards()
        card=await o.apply({'action':'create_character','preset':'generic','name':'普通角色','prompt':'喜欢散步与阅读的普通角色。'})
        await o.apply({'action':'configure','config_revision':o.revision(),'card_id':card['card_id'],'provider_id':'model/test','umo':UMO,'preset':'generic'})
        status=await o.status(UMO)
        assert status['compatibility']['visual_media']['state']=='missing' and status['visual']['profile']['style_preset']=='generic'
        created=await o.apply({'action':'starter_world','umo':UMO,'place_name':'小屋'})
        await o.apply({'action':'initialize_rooms','umo':UMO,'place_id':created['place_id']})
        await o.apply({'action':'initial_location','umo':UMO,'place_id':created['place_id']})
        status=await o.status(UMO);room=next(r for r in status['world']['rooms'] if r['name']=='房间')
        await o.apply({'action':'register_furniture','umo':UMO,'scene_revision':status['world']['scene_revision'],'room_id':room['id'],'furniture':[{'name':'书桌','kind':'desk','position':'right_wall','movable':True}]})
        await o.apply({'action':'activate','enabled':True,'config_revision':o.revision()})
        assert plugin.runtime_allowed() and (await o.status(UMO))['world']['has_furniture']
        plugin.config['narrative_all_groups']=True;plugin.config['narrative_sessions']=[]
        assert (await o.status())['selected_umo']==UMO
        await o.apply({'action':'activate','enabled':False,'config_revision':o.revision()})
        await o.apply({'action':'activate','enabled':True,'config_revision':o.revision()})
        scope,_=await plugin.web.scope(UMO);snap=await plugin.life.narrative.get_snapshot(scope)
        assert '魔裁' not in json.dumps(snap['visual_sharing'],ensure_ascii=False)
        assert snap['visual_sharing']['generation_available'] is False
        with pytest.raises(ValueError):await o.apply({'action':'starter_world','umo':UMO})
        with pytest.raises(ValueError):await o.apply({'action':'initialize_rooms','umo':UMO,'place_id':created['place_id']})
    finally:await plugin.terminate()

def test_legacy_style_migration_preserves_all_existing_design_and_is_idempotent(rig):
    engine,now,profiles,room,book=prepared(rig)
    with engine._db() as db:key,rev,before=profiles.load(db,SCOPE)
    profiles.migrate_legacy_style()
    with engine._db() as db:_,after_rev,after=profiles.load(db,SCOPE)
    assert after==dict(before,style_preset='manosaba') and after_rev==rev+1
    profiles.migrate_legacy_style()
    with engine._db() as db:assert profiles.load(db,SCOPE)[1]==after_rev
    assert '魔裁' in ''.join(state(engine)['visual_sharing']['rules'])
    profiles.configure(SCOPE,{'action':'style','asset_ids':before['styles'],'preset':'generic','expected_revision':after_rev})
    assert '魔裁' not in ''.join(state(engine)['visual_sharing']['rules'])
    with engine._db() as db:assert profiles.load(db,SCOPE)[2]['items']==before['items']

@pytest.mark.asyncio
async def test_old_companion_blocks_activation_but_editing_and_existing_config_are_retained(tmp_path,monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch);ready_context(plugin);o=plugin.onboarding
    try:
        original=copy.deepcopy(plugin.config)
        plugin.context.get_registered_star=lambda name:NS(activated=True,star_cls=NS())
        assert o.compatibility()['chat_dynamics']['state']=='update_required'
        with pytest.raises(ValueError):await o.apply({'action':'activate','enabled':True,'config_revision':o.revision()})
        assert plugin.config==original
        created=await o.apply({'action':'create_character','preset':'manosaba','name':'预设角色','prompt':'素描本笔谈角色'})
        assert plugin.world.store.get_card(created['card_id']).linked_book_id
        with pytest.raises(ValueError):await o.apply({'action':'create_character','preset':'manosaba','name':'预设角色','prompt':'覆盖尝试'})
        assert plugin.world.store.get_card(created['card_id']).system_prompt=='素描本笔谈角色'
    finally:await plugin.terminate()

@pytest.mark.asyncio
async def test_invalid_or_stale_setup_cannot_change_configuration(tmp_path,monkeypatch):
    plugin,_,_=await make_plugin(tmp_path,monkeypatch);ready_context(plugin);o=plugin.onboarding
    try:
        before=copy.deepcopy(plugin.config)
        with pytest.raises(ValueError):await o.apply({'action':'configure','config_revision':'stale'})
        with pytest.raises(ValueError):await o.apply({'action':'create_character','name':None,'prompt':'x'})
        assert plugin.config==before
        plugin.host_config.save_config=lambda:(_ for _ in ()).throw(OSError('cannot save'))
        with pytest.raises(OSError):o.save_config({'runtime_enabled':True})
        assert plugin.config==before and not plugin.host_config.get('runtime_enabled',False)
    finally:await plugin.terminate()

@pytest.mark.asyncio
async def test_texture_cache_is_persistent_optional_and_rejects_bad_selection(tmp_path):
    import hashlib
    from astrbot_plugin_dynamics_world.texture_resources import TextureResources
    service=TextureResources(tmp_path);blob=b'texture fixture'
    service.manifest={'base_url':'https://example.invalid/','files':[{'name':'fixture.jpg','bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}]}
    service.fetch=AsyncMock(return_value=blob)
    assert not service.selected_path()
    service.start();await service.task
    assert service.status()['installed']
    service.select('fixture.jpg');assert Path(service.selected_path()).read_bytes()==blob
    service.start();await service.task;assert service.fetch.await_count==1
    with pytest.raises(ValueError):service.select('../cmd_config.json')
    (service.root/'fixture.jpg').write_bytes(b'tampered');assert not service.selected_path()
    service.fetch=AsyncMock(side_effect=ValueError('hash mismatch'));service.start();await service.task
    assert service.status()['state']=='failed'
    service.select('');assert service.selected_path()==''
