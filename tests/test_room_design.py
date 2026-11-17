import copy,json
import pytest
from test_spatial import rig,SCOPE,state
from test_scenes import setup,scene,start,finish,step,item
from astrbot_plugin_dynamics_world.visual_context import WorldVisualContext
from astrbot_plugin_dynamics_world.life.core.narrative_schema import narrative_schema
from astrbot_plugin_dynamics_world.geography import configure_real,switch_mode

def prepare(rig,enter=True):
    engine,now,_=setup(rig);engine.visuals=WorldVisualContext(engine)
    rid=item(engine,'notebook')['room_id']
    furniture=[{'name':'床','kind':'bed','position':'left_wall','movable':True},
               {'name':'书桌','kind':'desk','position':'right_wall','movable':True},
               {'name':'椅子','kind':'chair','position':'center','movable':True},
               {'name':'书柜','kind':'bookcase','position':'back_wall','movable':True},
               {'name':'台灯','kind':'lamp','position':'desk_right','movable':True},
               {'name':'窗户','kind':'window','position':'right_wall','movable':False}]
    engine.scenes.configure(SCOPE,{'action':'room_design','expected_revision':scene(engine)['revision'],'place_id':'a','room_id':rid,'enabled':True,'furniture':furniture,'lighting':'warm','curtains':'open'})
    if enter:start(engine,[{'kind':'enter','target_id':rid}]);finish(engine,now)
    return engine,now,rid

def design(engine):return scene(engine)['room_designs'][0]
def furniture(engine,kind):return next(f for f in design(engine)['furniture'] if f['kind']==kind)

def test_movement_takes_time_persists_and_is_reflected_in_image_context(rig):
    engine,now,rid=prepare(rig);desk=furniture(engine,'desk');before=copy.deepcopy(scene(engine)['items'])
    start(engine,[{'kind':'move_furniture','target_id':desk['id'],'position':'near_window'}])
    assert furniture(engine,'desk')['position']=='right_wall'
    finish(engine,now)
    assert furniture(engine,'desk')['position']=='near_window' and len(design(engine)['history'])==1
    visual=state(engine)['visual_sharing']['visual_design'];assert '书桌在窗边' in visual['layout'] and visual['room_state']['changed']
    assert scene(engine)['items']==before
    from astrbot_plugin_dynamics_world.scenes import SceneService
    engine.scenes=SceneService(engine)
    assert furniture(engine,'desk')['position']=='near_window'

def test_cancel_preserves_finished_changes_but_never_applies_unfinished_step(rig):
    engine,now,rid=prepare(rig);chair=furniture(engine,'chair')
    start(engine,[{'kind':'move_furniture','target_id':chair['id'],'position':'bedside'},{'kind':'set_lighting','target_id':rid,'mode':'off'}])
    step(engine,now)
    engine.scenes.administer(SCOPE,{'action':'cancel','expected_revision':scene(engine)['revision']})
    assert furniture(engine,'chair')['position']=='bedside' and design(engine)['lighting']=='warm'
    now[0]+=7200;assert design(engine)['lighting']=='warm' and len(design(engine)['history'])==1

def test_placements_and_display_require_real_objects_and_saved_records(rig):
    engine,now,rid=prepare(rig);note=item(engine,'notebook')
    with pytest.raises(ValueError):start(engine,[{'kind':'display_note','target_id':note['id'],'record_id':'future-note','position':'desk_left'}])
    with engine._db() as db:
        key,rev,s=engine.scenes.load(db,SCOPE)
        s['items'][note['id']]['notes']=[{'id':'note-existing','title':'PRIVATE_TITLE','text':'PRIVATE_NOTE_BODY','created_at':now[0]-10,'fact_kind':'fiction'}]
        engine.scenes.save(db,key,rev,s)
    start(engine,[{'kind':'display_note','target_id':note['id'],'record_id':'note-existing','position':'desk_left'}]);finish(engine,now)
    assert item(engine,'notebook')['placement']=='书桌左侧，摊开展示已写纸页'
    visual=state(engine)['visual_sharing'];assert 'PRIVATE_' not in json.dumps(visual)
    assert visual['visual_design']['items'][0]['placement'].startswith('书桌左侧')
    start(engine,[{'kind':'take','target_id':note['id']}]);finish(engine,now)
    assert item(engine,'notebook')['carried'] and 'displayed_note_id' not in item(engine,'notebook')
    assert item(engine,'notebook')['notes'][0]['text']=='PRIVATE_NOTE_BODY'

def test_fixed_building_foreign_room_and_running_computer_cannot_be_rearranged(rig):
    engine,now,rid=prepare(rig,enter=False)
    with pytest.raises(ValueError):start(engine,[{'kind':'move_furniture','target_id':furniture(engine,'desk')['id'],'position':'center'}])
    start(engine,[{'kind':'enter','target_id':rid}]);finish(engine,now)
    with pytest.raises(ValueError):start(engine,[{'kind':'move_furniture','target_id':furniture(engine,'window')['id'],'position':'left_wall'}])
    computer=item(engine,'computer');start(engine,[{'kind':'power_on','target_id':computer['id']}]);finish(engine,now)
    with pytest.raises(ValueError):start(engine,[{'kind':'place_item','target_id':computer['id'],'position':'desk_left'}])
    with pytest.raises(ValueError):start(engine,[{'kind':'move_furniture','target_id':furniture(engine,'desk')['id'],'position':'center'}])
    assert design(engine)['history']==[]

def test_lighting_curtains_are_current_facts_and_room_scope_isolated(rig):
    engine,now,rid=prepare(rig)
    start(engine,[{'kind':'set_lighting','target_id':rid,'mode':'off'},{'kind':'set_curtains','target_id':rid,'mode':'closed'}]);finish(engine,now)
    assert design(engine)['lighting']=='off' and design(engine)['curtains']=='closed'
    visual=state(engine)['visual_sharing']['visual_design'];assert '灯已关闭' in visual['layout'] and '窗帘合拢' in visual['layout']
    from astrbot_plugin_chat_dynamics.core.scene_context import scene_context
    projected=scene_context(state(engine));assert projected['room_design']['curtains_label']=='窗帘合拢'
    from astrbot_plugin_chat_dynamics.core.world_visual_context import world_visual_context
    reply=world_visual_context(state(engine),now[0]);assert reply['visual_design']['room_state']['lighting']=='室内灯已关闭'
    start(engine,[{'kind':'leave'}]);finish(engine,now)
    assert 'room_design' not in scene_context(state(engine))
    assert 'room_state' not in state(engine)['visual_sharing'].get('visual_design',{})
    configure_real(engine.spatial,SCOPE,{'name':'测试','latitude':22,'longitude':114,'expected_revision':1})
    assert not scene(engine).get('room_designs')
    switch_mode(engine.spatial,SCOPE,'virtual',2)
    assert design(engine)['curtains']=='closed'

def test_global_only_permission_and_disable_keep_existing_changes(rig):
    engine,now,rid=prepare(rig)
    action={'operation':'start','steps':[{'kind':'set_lighting','target_id':rid,'mode':'off'}]}
    with pytest.raises(ValueError):engine.scenes.validate(action,{'scope':SCOPE,'snapshot':state(engine)})
    engine.scenes.configure(SCOPE,{'action':'room_design','place_id':'a','room_id':rid,'enabled':False,'expected_revision':scene(engine)['revision']})
    assert not any(a.get('kind')=='set_lighting' for a in scene(engine)['available_actions'])
    with pytest.raises(ValueError):start(engine,action['steps'])
    assert design(engine)['lighting']=='warm' and len(design(engine)['furniture'])==6
