import assert from 'node:assert/strict';
import test from 'node:test';
import {pathToFileURL} from 'node:url';
import {createAvatar} from '../../pages/world/avatar-model.js';
import {createWorldAvatar} from '../../pages/world/world-avatar.js';
import {BED_PLACEMENTS, DESK_PLACEMENTS} from '../../pages/world/cabin-layout.js';
import {projectAvatar} from '../../pages/world/avatar-state.js';

const THREE = await import(process.env.WORLD_THREE_MODULE
  ? pathToFileURL(process.env.WORLD_THREE_MODULE).href : 'three');
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-6, `${a} != ${b}`);
const png = value => `data:image/png;base64,${value}`;
const cube = (options = {}) => ({origin: [-3, 0, -2], size: [6, 16, 4], uv: [0, 0], ...options});
const model = (bones, animations = {}) => ({
  geometry: {description: {texture_width: 64, texture_height: 64}, bones},
  textures: [{name: 'first', data_url: png('first')}, {name: 'second', data_url: png('second')}],
  animations,
});

function textureLoader(loadAsync) {
  return {...THREE, TextureLoader: class { loadAsync(url) { return loadAsync(url); } }};
}

const home = {id: 'cabin', place_id: 'home'}, gardenRoom = {id: 'garden', place_id: 'home'};
const selection = {home_room_id: home.id, garden_room_id: gardenRoom.id};
function cabinSnapshot(activity, room = home, furniture = []) {
  return {activity_code: activity, server_time: 10, received_at_ms: Date.now(), scene: {
    available: true, phase: 'located', place_id: room.place_id, room_id: room.id,
    rooms: [home, gardenRoom], room_design: {room_id: room.id, furniture},
  }};
}

test('writing, sleeping and standing up use the rendered furniture coordinate frame in every slot', () => {
  const local = (v, placement) => new THREE.Vector3(...v).sub(new THREE.Vector3(...placement.slice(0, 3)))
    .applyAxisAngle(new THREE.Vector3(0, 1, 0), -placement[3]);
  for (const [slot, {chair}] of Object.entries(DESK_PLACEMENTS)) {
    const p = projectAvatar(cabinSnapshot('writing', home, [{kind:'desk', movable:true, position:slot}]), selection);
    const seated = local(p.position, chair), floor = local(p.approach, chair);
    near(seated.x, 0); near(seated.z, .04); near(seated.y, .38);
    near(Math.cos(p.rotationY - chair[3]), -1);
    near(floor.y, .13); assert.ok(Math.abs(floor.x) > .425);
  }
  for (const [slot, bed] of Object.entries(BED_PLACEMENTS)) {
    const p = projectAvatar(cabinSnapshot('sleeping', home, [{kind:'bed', movable:true, position:slot}]), selection);
    const lying = local(p.position, bed), floor = local(p.approach, bed);
    near(lying.x, .47); near(lying.z, .42); near(lying.y, .90);
    near(floor.y, .13); assert.ok(floor.x > 1.2);
  }
});

test('the cabin blends from the seated rig onto the garden path and back onto the chair', async t => {
  let actor;
  t.after(() => actor?.dispose());
  const media = {matches:false, addEventListener() {}, removeEventListener() {}};
  for (const [name, value] of Object.entries({
    matchMedia: () => media, requestAnimationFrame: () => 1, cancelAnimationFrame: () => {},
  })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {value, configurable:true});
    t.after(() => previous ? Object.defineProperty(globalThis, name, previous) : delete globalThis[name]);
  }
  let now = 20_000;
  t.mock.method(Date, 'now', () => now);
  const scene = new THREE.Scene();
  actor = createWorldAvatar(THREE, scene, () => {});
  await actor.setModel(null);
  const bench = cabinSnapshot('reading', gardenRoom), desk = cabinSnapshot('writing');
  const update = (data, ms) => {now += ms; actor.setState(data, selection); return actor.placement().visual_position;};
  update(bench, 0);
  const knee = scene.getObjectByName('leftKnee'), seatedAngle = knee.rotation.x;
  assert.ok(seatedAngle > 1.0);
  update(desk, 0);
  near(knee.rotation.x, seatedAngle);
  const midway = update(desk, 190);
  near(midway[1], (.12 - .25) / 2); near(knee.rotation.x, seatedAngle / 2);
  const before = [...update(desk, 189)], after = update(desk, 2);
  near(after[1], -.25);
  assert.ok(new THREE.Vector3(...before).distanceTo(new THREE.Vector3(...after)) < .01);
  let sawSitting = false, arrived = false;
  for (let i = 0; i < 250; i++) {
    const point = update(desk, 40);
    if (point[1] > .14 && point[1] < .37 && knee.rotation.x > .1 && knee.rotation.x < 1.30) sawSitting = true;
    if (!actor.diagnostics().transit) {arrived = true; break;}
  }
  assert.ok(sawSitting && arrived);
  assert.deepEqual(actor.placement().visual_position, [0,.38,.22]);
  const pen = scene.getObjectByName('pen');
  assert.ok(pen.visible);
  const grip = scene.getObjectByName('rightElbow').localToWorld(new THREE.Vector3(0,-.18,0));
  assert.ok(grip.distanceTo(pen.getWorldPosition(new THREE.Vector3())) < .10);

  update(bench, 40);
  assert.ok(actor.diagnostics().transit);
  const paused = {...bench, scene:{...bench.scene, paused:true}};
  update(paused, 40);
  assert.equal(actor.diagnostics().transit, false);
  assert.equal(actor.diagnostics().animating, false);
  assert.deepEqual(update(paused, 8000), [3.4,.12,5.1]);
  update({...desk, isReplay:true}, 10);
  assert.equal(actor.diagnostics().animating, false);
  media.matches = true;
  assert.deepEqual(update(bench, 10), [3.4,.12,5.1]);
  assert.equal(actor.diagnostics().transit, false);
});

test('built-in character has two legs, hinged elbows, and action props', async () => {
  const avatar = createAvatar(THREE);
  await avatar.ready;
  const {group} = avatar;
  const node = name => group.getObjectByName(name);
  const box = new THREE.Box3().setFromObject(node('avatar-rig'), true);
  assert.ok(box.max.y > 1.69 && box.max.y < 1.73);
  near(box.min.y, .0005);
  assert.equal(group.userData.portalKey, undefined);
  assert.deepEqual(avatar.diagnostics().supported_poses, ['idle', 'walk', 'read', 'write', 'rest', 'sit', 'sit_read', 'sit_write', 'sleep',
    'cook', 'wash', 'sweep', 'water', 'sit_eat', 'sit_game']);

  avatar.setPose('walk', .15);
  const stride = node('leftLeg').rotation.x;
  assert.ok(stride > .45);
  near(node('rightLeg').rotation.x, -stride);
  assert.ok(node('leftArm').rotation.x < 0);
  avatar.setPose('pause', 2);
  near(node('leftLeg').rotation.x, stride);
  avatar.setPose('walk', .15);
  near(node('leftLeg').rotation.x, stride);

  avatar.setPose('read');
  assert.ok(node('book').visible);
  assert.ok(node('leftElbow').rotation.x < -.7);
  assert.equal(node('notebook').visible, false);
  avatar.setPose('write');
  assert.ok(node('notebook').visible && node('pen').visible);
  assert.equal(node('book').visible, false);
  avatar.setPose('sit');
  assert.ok(node('leftLeg').rotation.x < -1);
  assert.ok(node('leftKnee').rotation.x > 1);
  avatar.setPose('idle');
  near(node('leftLeg').rotation.x, 0);
  assert.equal(node('pen').visible, false);

  const scene = new THREE.Scene();
  scene.add(group);
  const geometry = node('head').children[0].geometry;
  let disposed = 0;
  geometry.addEventListener('dispose', () => disposed++);
  avatar.dispose();
  avatar.dispose();
  assert.equal(disposed, 1);
  assert.equal(scene.children.length, 0);
});

test('import chooses one texture, orients the north face, and mirrors per-face UVs', async () => {
  const image = new THREE.Texture();
  const requested = [];
  const Three = textureLoader(async url => { requested.push(url); return image; });
  const uploaded = model([{
    name: 'unrecognized', cubes: [cube({mirror: true, uv: {
      north: {uv: [5, 12], uv_size: [6, 16]},
      east: {uv: [21, 13], uv_size: [4, 16]},
    }})],
  }], {walk: {bones: {unrecognized: {rotation: [0, 0, 0]}}}});
  const avatar = createAvatar(Three, uploaded, 1);
  await avatar.ready;
  assert.deepEqual(requested, [png('second')]);
  assert.equal(image.magFilter, THREE.NearestFilter);
  assert.equal(image.minFilter, THREE.NearestFilter);
  assert.equal(image.generateMipmaps, false);
  assert.equal(image.colorSpace, THREE.SRGBColorSpace);
  const bounds = new THREE.Box3().setFromObject(avatar.group, true);
  near(bounds.min.y, 0);
  near(bounds.max.y, 1.7);
  const mesh = avatar.group.getObjectByName('unrecognized').children[0];
  assert.equal(mesh.material.map, image);
  assert.ok(mesh.material.alphaTest > 0);
  const {position, normal, uv} = mesh.geometry.attributes;
  assert.equal(position.count, 8);
  near(normal.getX(0), 1);
  near(uv.getX(0), 25 / 64);
  near(normal.getZ(4), 1);
  near(uv.getX(4), 11 / 64);
  near(uv.getY(4), 1 - 12 / 64);
  assert.ok(uv.getX(5) < uv.getX(4));
  avatar.group.updateMatrixWorld(true);
  const front = new THREE.Raycaster(new THREE.Vector3(0, .8, 2), new THREE.Vector3(0, 0, -1));
  assert.ok(front.intersectObject(mesh).length);
  avatar.setPose('walk', 1);
  assert.equal(avatar.diagnostics().mode, 'static');
  assert.deepEqual(avatar.diagnostics().supported_poses, []);
  let disposed = 0;
  image.addEventListener('dispose', () => disposed++);
  avatar.dispose();
  assert.equal(disposed, 1);
});

test('animated imported bones keep their bind transforms and skip expression tracks', async () => {
  const Three = textureLoader(async () => new THREE.Texture());
  const uploaded = model([
    {name: 'Root', pivot: [0, 4, 3], cubes: [cube()]},
    {name: 'Head', parent: 'root', pivot: [0, 12, -1], rotation: [15, 10, 0],
      cubes: [cube({origin: [-2, 12, -3], size: [4, 4, 4], pivot: [0, 12, -1], rotation: [0, 0, 20]})]},
  ], {
    'animation.sample.walk': {animation_length: 2, loop: true, bones: {HEAD: {
      rotation: {'0.0': [0, 0, 0], '1.0': {pre: [60, 0, 0], post: [80, 0, 0]}, '2.0': [0, 0, 0]},
      position: [0, 1, -2], scale: [1.25],
    }}},
    idle: {bones: {head: {rotation: [5, 0, 0], position: ['query.anim_time', 0, 0]}}},
    read: {bones: {head: {rotation: [25, 0, 0]}}},
    write: {bones: {head: {rotation: ['Math.sin(query.anim_time)', 0, 0]}}},
  });
  const avatar = createAvatar(Three, uploaded);
  avatar.setPose('walk', .5);
  await avatar.ready;
  const head = avatar.group.getObjectByName('Head');
  assert.equal(head.parent.name, 'Root');
  near(head.position.y, 9);
  near(head.position.z, 6);
  near(head.rotation.x, Math.PI / 4);
  near(head.scale.x, 1.25);
  avatar.setPose('walk', 1);
  near(head.rotation.x, 95 * Math.PI / 180);
  avatar.setPose('walk', 2.5);
  near(head.rotation.x, Math.PI / 4);
  avatar.setPose('idle');
  near(head.position.z, 4);
  near(head.rotation.x, 20 * Math.PI / 180);
  near(head.scale.x, 1);
  const state = avatar.diagnostics();
  assert.equal(state.clips.idle, 'idle');
  assert.equal(state.clips.walk, 'animation.sample.walk');
  assert.equal(state.clips.read, 'read');
  assert.equal(state.actions.write, 'static');
  assert.equal(state.warnings.length, 2);
  avatar.dispose();
});

test('an imported humanoid holds study props near its animated hands', async () => {
  const Three = textureLoader(async () => new THREE.Texture());
  const uploaded = model([
    {name: 'body', cubes: [cube()]},
    {name: 'LeftArm', parent: 'body', pivot: [4, 15, 0], cubes: [
      cube({origin: [3, 7, -1], size: [2, 8, 2]}),
    ]},
    {name: 'RightArm', parent: 'body', pivot: [-4, 15, 0], cubes: [
      cube({origin: [-5, 7, -1], size: [2, 8, 2]}),
    ]},
    {name: 'LeftHandLocator', parent: 'LeftArm', pivot: [4, 7, 0]},
    {name: 'RightHandLocator', parent: 'RightArm', pivot: [-4, 7, 0]},
  ]);
  const avatar = createAvatar(Three, uploaded);
  await avatar.ready;
  const node = name => avatar.group.getObjectByName(name);
  assert.equal(avatar.diagnostics().actions.read, 'procedural');
  assert.equal(avatar.diagnostics().study_props, true);
  assert.equal(node('book').visible, false);
  avatar.setPose('read', .2);
  assert.ok(node('book').visible && !node('pen').visible);
  const hand = node('LeftHandLocator').getWorldPosition(new THREE.Vector3());
  const book = node('book').getWorldPosition(new THREE.Vector3());
  near(book.z - hand.z, .025);
  avatar.setPose('write', .5);
  assert.ok(node('notebook').visible && node('pen').visible);
  assert.equal(node('book').visible, false);
  avatar.setPose('idle');
  assert.equal(node('notebook').visible, false);
  assert.equal(node('pen').visible, false);
  avatar.dispose();
});

test('texture errors and invalid hierarchies reject ready; disposed loads release late textures', async () => {
  const uploaded = model([{name: 'body', cubes: [cube()]}]);
  const invalidTexture = createAvatar(textureLoader(async () => { throw new Error('decode failed'); }), uploaded);
  await assert.rejects(invalidTexture.ready, /decode failed/);
  assert.equal(invalidTexture.diagnostics().status, 'error');
  assert.equal(invalidTexture.group.getObjectByName('body'), undefined);
  const invalidHierarchy = createAvatar(THREE, model([{name: 'body', parent: 'body', cubes: [cube()]}]));
  await assert.rejects(invalidHierarchy.ready, /hierarchy contains a cycle/);

  let complete, loaded;
  const started = new Promise(resolve => { loaded = resolve; });
  const Three = textureLoader(() => new Promise(resolve => { complete = resolve; loaded(); }));
  const late = createAvatar(Three, uploaded);
  await started;
  late.dispose();
  const image = new THREE.Texture();
  let disposed = 0;
  image.addEventListener('dispose', () => disposed++);
  complete(image);
  await late.ready;
  assert.equal(disposed, 1);
  assert.equal(late.diagnostics().status, 'disposed');
});
