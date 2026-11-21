import assert from 'node:assert/strict';
import test from 'node:test';
import {projectAvatar,projectAmbientMicro,resolveFurnitureLayout} from '../pages/world/avatar-state.js';
import {BED_PLACEMENTS,furniturePoint} from '../pages/world/cabin-layout.js';
import {BED_FRAME,DEFAULT_BODY,avoidBed,crossesBed} from '../pages/world/cabin-bed.js';

const sampleAt = 1_800_000_000_000;
const serverTime = 1_790_000_000;
const selection = {home_room_id: 'room_home', garden_room_id: 'room_garden'};
const rooms = [
  {id: 'room_home', place_id: 'place_home', name: '小屋'},
  {id: 'room_garden', place_id: 'place_home', name: '花园'},
  {id: 'room_entry', place_id: 'place_home', name: '玄关'},
  {id: 'room_elsewhere', place_id: 'place_elsewhere', name: '小屋'},
];

function action(steps, overrides = {}) {
  return {
    id: 'action_a', index: 0, steps, status: 'running', label: '当前动作',
    origin: 'life_model', step_started_at: serverTime - 5, step_ends_at: serverTime + 15,
    progress: 0.25, ...overrides,
  };
}

function snapshot(scene = {}, actor = {}) {
  return {
    server_time: serverTime,
    received_at_ms: sampleAt,
    actor: {phase: 'located', place_id: 'place_home', paused: false, ...actor},
    scene: {
      available: true, phase: 'located', place_id: 'place_home', place_name: '住所',
      room_id: 'room_home', room_name: '小屋', rooms, action: null, paused: false, ...scene,
    },
  };
}

test('only the current step controls the avatar, using the original action and room labels', () => {
  const steps = [{kind: 'leave'}, {kind: 'read_notes'}, {kind: 'project_write'}];
  const data = snapshot({action: action(steps, {index: 1, label: '翻阅旧笔记', activity_code: 'walking'})});
  const view = projectAvatar(data, selection, sampleAt);
  assert.equal(view.visible, true);
  assert.equal(view.location, 'room');
  assert.equal(view.pose, 'read');
  assert.deepEqual(view.position, [-3.25+(BED_FRAME.halfWidth+DEFAULT_BODY.radius), 0.13, 0.75]);
  assert.equal(view.positionBasis, 'action_anchor');
  assert.equal(view.label, '翻阅旧笔记');
  assert.equal(view.locationLabel, '住所 · 小屋');
  assert.equal(view.actionKey, 'action_a:1');
  assert.equal(view.animate, true);
});

test('real reading, writing and rest steps use room and garden anchors', () => {
  const poses = {
    read: 'read', read_notes: 'read', write_note: 'write', project_start: 'write',
    project_write: 'write', project_revise: 'write', rest: 'rest',
  };
  const roomPoints = {read: [-3.25+(BED_FRAME.halfWidth+DEFAULT_BODY.radius), 0.13, 0.75], write: [0, 0.38, 0.22], rest: [-2.13, 0.49, 0.8]};
  const gardenPoints = {read: [3.4, 0.12, 5.1], write: [3.4, 0.12, 5.1], rest: [3.4, 0.12, 5.1]};
  for (const [kind, pose] of Object.entries(poses)) {
    for (const [location, points] of [['room', roomPoints], ['garden', gardenPoints]]) {
      const room_id = location === 'room' ? 'room_home' : 'room_garden';
      const view = projectAvatar(snapshot({room_id, action: action([{kind}])}), selection, sampleAt);
      assert.equal(view.location, location, kind);
      assert.equal(view.pose, pose, kind);
      assert.deepEqual(view.position, points[pose], kind);
      assert.equal(view.rotationY, location === 'room' ? (pose === 'write' ? Math.PI : pose === 'rest' ? Math.PI / 2 : 0) : 0, kind);
      assert.equal(view.animate, pose !== 'rest', kind);
    }
  }
});

test('an unsupported or absent current action stays at a static room anchor', () => {
  const idle = snapshot({last_action: action([{kind: 'leave'}], {status: 'completed'})});
  idle.activity = '正在前往花园';
  const take = snapshot({action: action([{kind: 'take'}, {kind: 'leave'}], {activity_code: 'walking'})});
  for (const data of [idle, take]) {
    const view = projectAvatar(data, selection, sampleAt + 2_000);
    assert.equal(view.pose, 'idle');
    assert.equal(view.animate, false);
    assert.equal(view.positionBasis, 'room_anchor');
    assert.deepEqual(view.position, [1.5, 0.13, 1.5]);
  }
});

test('an enter step walks only at its exact bound target at the current place', () => {
  const entering = snapshot({room_id: null, room_name: '地点入口', action: action([{kind: 'enter', target_id: 'room_home'}])});
  const view = projectAvatar(entering, selection, sampleAt + 5_000);
  assert.equal(view.location, 'room');
  assert.equal(view.locationLabel, '住所 · 地点入口');
  assert.equal(view.pose, 'walk');
  assert.equal(view.progress, 0.5);
  assert.deepEqual(view.position, [1.4, 0.13, 2.5]);
  assert.equal(view.rotationY, Math.PI);
  assert.equal(view.animate, true);

  const wrongPlace = {...entering, scene: {...entering.scene, place_id: 'place_elsewhere'}};
  const otherRoom = {...entering, scene: {...entering.scene, room_id: 'room_entry'}};
  const wrongBinding = {home_room_id: '小屋'};
  assert.equal(projectAvatar(wrongPlace, selection, sampleAt).visible, false);
  assert.equal(projectAvatar(otherRoom, selection, sampleAt).visible, false);
  assert.equal(projectAvatar(entering, wrongBinding, sampleAt).visible, false);
  assert.equal(projectAvatar(snapshot({room_id: null}), selection, sampleAt).visible, false);
});

test('a paused walk uses the reported progress even far past the original end time', () => {
  const paused = snapshot({paused: true, action: action([{kind: 'leave'}], {progress: 0.4})});
  const view = projectAvatar(paused, selection, sampleAt + 600_000);
  assert.equal(view.paused, true);
  assert.equal(view.animate, false);
  assert.equal(view.pose, 'walk');
  assert.equal(view.progress, 0.4);
  assert.deepEqual(view.position, [1.4, 0.13, 2.3]);
  assert.equal(view.label, '当前动作');
  assert.deepEqual(projectAvatar(paused, selection, sampleAt), view);
});

test('entering the garden faces toward the yard and leaving faces toward the door', () => {
  const entering = snapshot({room_id: null, action: action([{kind: 'enter', target_id: 'room_garden'}])});
  const leaving = snapshot({room_id: 'room_garden', action: action([{kind: 'leave'}])});
  const arrival = projectAvatar(entering, selection, sampleAt);
  const departure = projectAvatar(leaving, selection, sampleAt);
  assert.equal(arrival.pose, 'walk');
  assert.deepEqual(arrival.position, [0, -0.25, 5]);
  assert.equal(arrival.rotationY, 0);
  assert.equal(departure.pose, 'walk');
  assert.deepEqual(departure.position, [0, -0.25, 6]);
  assert.equal(departure.rotationY, Math.PI);
});

test('time advances only to the current step endpoint and waits for the server there', () => {
  const steps = [{kind: 'leave'}, {kind: 'enter', target_id: 'room_garden'}, {kind: 'read'}];
  const data = snapshot({action: action(steps, {label: '前往地点入口'})});
  const view = projectAvatar(data, selection, sampleAt + 15_000);
  assert.equal(view.location, 'room');
  assert.equal(view.pose, 'walk');
  assert.equal(view.progress, 1);
  assert.deepEqual(view.position, [1.4, 0.13, 3.5]);
  assert.equal(view.label, '前往地点入口 · 等待同步');
  assert.equal(view.actionKey, 'action_a:0');
  assert.equal(view.animate, false);
  assert.deepEqual(projectAvatar(data, selection, sampleAt + 500_000), view);

  const next = snapshot({room_id: null, action: action(steps, {index: 1, progress: 0.5})});
  const nextView = projectAvatar(next, selection, sampleAt);
  assert.equal(nextView.location, 'garden');
  assert.equal(nextView.pose, 'walk');
  assert.deepEqual(nextView.position, [0, -0.25, 5.5]);
  assert.equal(nextView.actionKey, 'action_a:1');
});

test('a cancelled action cannot continue or switch to its next step', () => {
  const stopped = action([{kind: 'leave'}, {kind: 'enter', target_id: 'room_garden'}], {status: 'cancelled'});
  for (const scene of [{last_action: stopped}, {action: stopped}]) {
    const view = projectAvatar(snapshot(scene), selection, sampleAt);
    assert.equal(view.pose, 'idle');
    assert.equal(view.animate, false);
    assert.equal(view.actionKey, null);
    assert.equal(view.label, '');
  }
});

test('outbound and inbound map journeys stay outside the cabin through their ETA', () => {
  for (const [origin_id, destination_id, destination_name] of [
    ['place_home', 'place_elsewhere', '图书馆'], ['place_elsewhere', 'place_home', '住所'],
  ]) {
    const journey = {id: 'journey_1', origin_id, destination_id, destination_name,
      departed_at: serverTime - 25, arrives_at: serverTime + 75, path: [[0, 0], [14, 18]]};
    const data = snapshot({phase: 'travelling', room_id: null, place_id: origin_id, destination: destination_name},
      {phase: 'travelling', journey, progress: 0.25});
    const moving = projectAvatar(data, selection, sampleAt + 25_000);
    assert.equal(moving.visible, false);
    assert.equal(moving.location, 'away');
    assert.equal(moving.positionBasis, 'journey');
    assert.equal(moving.progress, 0.5);
    assert.equal(moving.locationLabel, `前往 ${destination_name}`);
    const overdue = projectAvatar(data, selection, sampleAt + 80_000);
    assert.equal(overdue.visible, false);
    assert.equal(overdue.progress, 1);
    assert.equal(overdue.label, '等待同步');
  }
});

test('an unknown position, absent scene or different room never uses a cabin anchor', () => {
  for (const data of [null, {scene: {available: false}}, snapshot({phase: 'unknown'}),
    snapshot({place_id: 'place_elsewhere', room_id: 'room_elsewhere', room_name: '小屋'}),
    snapshot({place_id: 'place_elsewhere', room_id: 'room_home'}), snapshot({room_id: 'room_entry'})]) {
    const view = projectAvatar(data, selection, sampleAt);
    assert.equal(view.visible, false);
    assert.equal(view.animate, false);
    assert.equal(view.positionBasis, 'unknown');
  }
});

test('room and scope changes depend on the supplied data and binding each time', () => {
  const current = snapshot({action: action([{kind: 'project_write'}])});
  const nextScope = snapshot({rooms: [{id: 'scope_two_garden', place_id: 'place_home'}],
    room_id: 'scope_two_garden', room_name: '另一处花园'});
  const nextSelection = {garden_room_id: 'scope_two_garden'};
  const first = projectAvatar(current, selection, sampleAt);
  assert.equal(first.pose, 'write');
  assert.equal(projectAvatar(current, nextSelection, sampleAt).visible, false);
  assert.equal(projectAvatar(nextScope, selection, sampleAt).visible, false);
  const garden = projectAvatar(nextScope, nextSelection, sampleAt);
  assert.equal(garden.location, 'garden');
  assert.equal(garden.pose, 'idle');
  assert.equal(garden.actionKey, null);
  assert.deepEqual(garden.position, [-2.8, -0.25, 5.7]);
  first.position[0] = 99;
  assert.deepEqual(projectAvatar(current, selection, sampleAt).position, [0, 0.38, 0.22]);
});

test('without a receive time the server epoch provides the local clock reference', () => {
  const {received_at_ms, ...data} = snapshot({action: action([{kind: 'leave'}])});
  const view = projectAvatar(data, selection, (serverTime + 5) * 1000);
  assert.equal(view.progress, 0.5);
  assert.equal(view.animate, true);
});

test('watching the cat keeps the whole body beside each rendered bed, including old snapshots', () => {
  const body={...DEFAULT_BODY,radius:.59};
  for(const [slot,bed] of Object.entries(BED_PLACEMENTS)){
    const data=snapshot({room_designs:[],room_design:{furniture:[{kind:'bed',position:slot,movable:true}]}});
    const layout=resolveFurnitureLayout(data,body);
    const base=projectAvatar(data,selection,sampleAt,layout);
    let cat;
    for(let i=0;i<6;i++){
      const spot=projectAmbientMicro(data,base,sampleAt+i*90000,layout);
      if(spot.id==='cat_check'){cat=spot;break;}
    }
    assert.ok(cat,slot);
    const [x,y,z]=cat.position, dx=x-bed[0], dz=z-bed[2];
    const localX=dx*Math.cos(bed[3])-dz*Math.sin(bed[3]);
    assert.ok(localX>BED_FRAME.halfWidth+body.radius,slot);
    assert.equal(y,.13);
    assert.equal(cat.rotationY,bed[3]-Math.PI/2);
    assert.equal(layout.bedSlot,slot);
  }
});

test('a central bed leaves a walkable route from the threshold to the cat', () => {
  const data=snapshot({room_design:{furniture:[{kind:'bed',position:'center',movable:true}]}});
  const layout=resolveFurnitureLayout(data,{...DEFAULT_BODY,radius:.62});
  const threshold=[1.15,.13,3.55];
  assert.ok(crossesBed(threshold,layout.catWatch,layout.obstacle));
  const route=avoidBed([threshold,layout.catWatch],layout.obstacle);
  assert.deepEqual(route[0],threshold);
  assert.deepEqual(route.at(-1),layout.catWatch);
  assert.ok(route.length>2);
  for(let i=1;i<route.length;i++)assert.equal(crossesBed(route[i-1],route[i],layout.obstacle),false);
});

test('a live bed move takes precedence over the previously received furniture slot', () => {
  const data=snapshot({room_design:{furniture:[{kind:'bed',position:'left_wall',movable:true}]}});
  const body={...DEFAULT_BODY,rest:.81,game:.73,sleep:1.32};
  const layout=resolveFurnitureLayout(data,body,'back_wall');
  assert.deepEqual(layout.anchors.room.rest,furniturePoint(BED_PLACEMENTS.back_wall,1.12,.81,.75));
  assert.deepEqual(layout.anchors.room.sleep,furniturePoint(BED_PLACEMENTS.back_wall,.47,1.32,.42));
});
