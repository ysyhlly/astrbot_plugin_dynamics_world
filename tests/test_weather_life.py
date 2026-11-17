import copy
import json

import pytest

from test_spatial import rig,GLOBAL,state
from astrbot_plugin_dynamics_world.weather import EnvironmentService
from astrbot_plugin_dynamics_world.weather_life import WeatherLifeObserver
from astrbot_plugin_dynamics_world.spatial import identity
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import build_narrative_prompt


def setup(rig):
    engine,now,_=rig
    now[0]=int(now[0]//3600)*3600+600
    service=engine.environment=EnvironmentService(engine)
    env={'available':True,'status':'ready','mode':'real','provider':'met','source':'MET Norway','fact_kind':'external_weather',
         'revision':1,'latitude':22.5,'longitude':114,'timezone':'Asia/Shanghai','location':'测试参考城市',
         'current':{'temperature':24,'wind_speed':8,'effect':'cloud','label':'多云','is_day':True}}
    service.snapshot=lambda *args:copy.deepcopy(env)
    state(engine,GLOBAL)
    with engine._db() as db:
        row=db.execute('SELECT state FROM lives WHERE identity=?',(identity(GLOBAL),)).fetchone()
        life=json.loads(row[0]);life.update(valid_until=now[0]+7200,next_check=now[0]+7200,availability='available',activity='在室内读书',activity_code='reading')
        db.execute('UPDATE lives SET state=? WHERE identity=?',(json.dumps(life),identity(GLOBAL)))
        db.execute("INSERT INTO maintenance VALUES(?,'hourly',?)",(identity(GLOBAL),now[0]))
    calls=[]
    async def model(request):calls.append(request);return {'no_change':True}
    engine.model=model
    return engine,now,env,calls


def rain(env):env['current'].update(effect='rain',label='雨')


@pytest.mark.asyncio
async def test_weather_change_advances_without_waiting_for_next_hour_and_no_broadcast(rig):
    engine,now,env,calls=setup(rig)
    await engine.tick();assert not calls
    rain(env);now[0]+=30;await engine.tick();assert not calls
    now[0]+=120;result=await engine.tick()
    assert result['results'][0]['status']=='no_change' and len(calls)==1
    event=calls[0]['events'][0]
    assert event['type']=='life.tick' and event['data']['trigger']=='weather_change'
    assert event['scope']['umo']=='' and event['fact_kind']=='fiction'
    assert event['data']['environment_change']['reasons']==['precipitation_changed']
    for _ in range(5):now[0]+=30;await engine.tick()
    assert len(calls)==1
    with engine._db() as db:
        assert db.execute("SELECT COUNT(*) FROM calls WHERE kind='weather'").fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM intents').fetchone()[0]==0
    prompt=build_narrative_prompt(calls[0],{})
    assert 'environment_change' in prompt and '可以保持不变' in prompt


@pytest.mark.asyncio
async def test_tiny_fluctuations_and_short_weather_pulses_do_not_evaluate(rig):
    engine,now,env,calls=setup(rig);await engine.tick()
    for temp in [24.4,23.8,25.2,24.1]:
        now[0]+=30;env['current']['temperature']=temp;await engine.tick()
    rain(env);now[0]+=30;await engine.tick()
    env['current'].update(effect='cloud',label='多云');now[0]+=60;await engine.tick()
    assert not calls


@pytest.mark.asyncio
async def test_pause_sleep_stale_city_switch_and_long_offline_do_not_wake_role(rig):
    engine,now,env,calls=setup(rig);await engine.tick()
    await engine.set_paused(True)
    rain(env);now[0]+=30;await engine.tick();now[0]+=150;await engine.tick()
    await engine.set_paused(False);await engine.tick();assert not calls
    env['current']['temperature']=10;env['stale']=True;now[0]+=30;await engine.tick()
    env['stale']=False;now[0]+=150;await engine.tick();assert not calls
    env['latitude']=35;env['current']['temperature']=30;now[0]+=30;await engine.tick();now[0]+=150;await engine.tick()
    assert not calls
    with engine._db() as db:
        row=db.execute('SELECT state FROM lives WHERE identity=?',(identity(GLOBAL),)).fetchone();life=json.loads(row[0]);life['availability']='asleep'
        db.execute('UPDATE lives SET state=? WHERE identity=?',(json.dumps(life),identity(GLOBAL)))
    env['current']['temperature']=12;now[0]+=30;await engine.tick();now[0]+=150;await engine.tick();assert not calls


@pytest.mark.asyncio
async def test_restart_outbox_uses_same_event_id_and_same_payload(rig):
    engine,now,env,calls=setup(rig);await engine.tick();rain(env);now[0]+=30;await engine.tick();now[0]+=120
    observer=engine.environment.life_observer
    with engine._db() as db:first=observer.poll(db,GLOBAL,now[0])
    assert first
    engine.environment.life_observer=WeatherLifeObserver(engine.environment)
    now[0]+=30
    with engine._db() as db:second=engine.environment.life_observer.poll(db,GLOBAL,now[0])
    assert first==second
    await engine.tick();assert len(calls)==1
    with engine._db() as db:assert db.execute('SELECT COUNT(*) FROM events WHERE event_id=?',(first['event_id'],)).fetchone()[0]==1


@pytest.mark.asyncio
async def test_hourly_and_weather_change_coalesce_into_one_model_call(rig):
    engine,now,env,calls=setup(rig);await engine.tick();rain(env);now[0]+=30;await engine.tick();now[0]+=120
    with engine._db() as db:db.execute("UPDATE maintenance SET last=last-3600 WHERE kind='hourly'")
    await engine.tick();assert len(calls)==1 and len(calls[0]['events'])==2
    with engine._db() as db:assert db.execute("SELECT COUNT(*) FROM calls WHERE kind='hourly'").fetchone()[0]==1
    now[0]+=30;await engine.tick();assert len(calls)==1


@pytest.mark.asyncio
async def test_failed_weather_inference_respects_retry_and_stale_event_is_retired(rig):
    engine,now,env,calls=setup(rig);await engine.tick();rain(env);now[0]+=30;await engine.tick();now[0]+=120
    async def failure(request):calls.append(request);raise TimeoutError()
    engine.model=failure
    await engine.tick();assert len(calls)==1
    now[0]+=30;await engine.tick();assert len(calls)==1
    env['current'].update(effect='cloud',label='多云');now[0]+=30;await engine.tick()
    with engine._db() as db:
        assert db.execute("SELECT status FROM events WHERE event_id=?",(calls[0]['events'][0]['event_id'],)).fetchone()[0]=='observed_only'


@pytest.mark.asyncio
async def test_weather_only_cannot_create_contact_intent(rig):
    engine,now,env,calls=setup(rig);await engine.tick();rain(env);now[0]+=30;await engine.tick();now[0]+=120
    async def forbidden(request):
        calls.append(request)
        return {'contact_intents':[{'intent_id':'bad','reason':'下雨了去提醒群友','source_ids':[request['events'][0]['event_id']],
                                  'not_before':request['now'],'expires_at':request['now']+600}]}
    engine.model=forbidden
    await engine.tick()
    with engine._db() as db:assert db.execute('SELECT COUNT(*) FROM intents').fetchone()[0]==0


@pytest.mark.asyncio
async def test_weather_replanning_updates_future_schedule_and_preserves_past(rig):
    from astrbot_plugin_dynamics_world.life.core.narrative_schema import narrative_schema
    from datetime import datetime
    from zoneinfo import ZoneInfo
    engine,now,env,calls=setup(rig)
    old={'start':now[0]-600,'end':now[0]-1,'activity':'午饭','fact_kind':'plan'}
    future={'start':now[0]+600,'end':now[0]+1200,'activity':'湖边散步','fact_kind':'plan'}
    with engine._db() as db:
        row=db.execute('SELECT state FROM lives').fetchone();life=json.loads(row[0]);life.update(plan=[old,future],plan_date=datetime.fromtimestamp(now[0],ZoneInfo('Asia/Shanghai')).date().isoformat())
        db.execute('UPDATE lives SET state=?',(json.dumps(life),))
    await engine.tick();rain(env);now[0]+=30;await engine.tick();now[0]+=120
    async def model(request):
        assert request['weather_reassessment'] and 'daily_plan' in narrative_schema(request)['properties']
        return {'no_change':False,'state':{'activity_code':'reading','availability':'available'},
                'daily_plan':[{'start':request['now']+10,'end':request['now']+600,'activity':'在住所读书'}]}
    engine.model=model;result=await engine.tick()
    assert result['results'][0]['status']=='advanced'
    admin=await engine.get_narrative_admin(GLOBAL)
    assert admin['daily_plan'][0]==old and admin['daily_plan'][1]['activity']=='在住所读书'
    assert not any(p['activity']=='湖边散步' for p in admin['daily_plan'])
