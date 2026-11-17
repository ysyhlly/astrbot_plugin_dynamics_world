import assert from 'node:assert/strict';
import test from 'node:test';
import {pathToFileURL} from 'node:url';
import {createAvatar} from '../../pages/world/avatar-model.js';

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
