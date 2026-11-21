import {compileMolangVector} from './molang.js';
import {measureBedBody} from './cabin-bed.js';

const AVATAR_HEIGHT = 1.7;
const RADIANS = Math.PI / 180;
const TAU = 2 * Math.PI;
const ZERO = [0, 0, 0];
const POSES = ['idle', 'walk', 'read', 'write', 'rest', 'sit', 'sit_read', 'sit_write', 'sleep',
  'cook', 'wash', 'sweep', 'water', 'sit_eat', 'sit_game','survey','weigh'];
const CLIP_NAMES = {
  survey:['spyglass','survey'], weigh:['weighevidence','weigh'],
  idle: ['idle', 'stand', 'standing', 'breathe'],
  walk: ['walk', 'walking', 'move', 'locomotion'],
  read: ['read', 'reading', 'readbook', 'readingbook'],
  write: ['write', 'writing', 'writenote', 'notetaking'],
  rest: ['rest', 'resting', 'relax', 'sit', 'sitting'],
  sit: ['sit', 'sitting', 'rest', 'resting', 'relax'],
  sit_read: ['sitread', 'sit_read', 'read', 'reading', 'readbook', 'readingbook'],
  sit_write: ['sitwrite', 'sit_write', 'write', 'writing', 'writenote', 'notetaking'],
  sleep: ['sleep', 'sleeping', 'lie', 'lying', 'inbed', 'bed'],
  cook: ['cook', 'cooking', 'stir', 'stirring', 'kitchen'],
  wash: ['wash', 'washing', 'washface', 'brush', 'brushteeth'],
  sweep: ['sweep', 'sweeping', 'broom', 'clean', 'cleaning'],
  water: ['water', 'watering', 'garden', 'gardening'],
  sit_eat: ['siteat', 'sit_eat', 'eat', 'eating', 'dine', 'meal'],
  sit_game: ['sitgame', 'sit_game', 'game', 'gaming', 'play', 'handheld'],
};
// Which held prop each pose shows (study props plus everyday household tools).
const POSE_PROPS = {survey:['spyglass'],weigh:['weight'],read: ['book'], sit_read: ['book'], write: ['notebook', 'pen'], sit_write: ['notebook', 'pen'],
  sweep: ['broom'], water: ['can'], sit_eat: ['bowl', 'spoon'], sit_game: ['handheld'], cook: ['ladle'], wash: ['brush']};
const PROP_NAMES = ['book', 'notebook', 'pen', 'broom', 'can', 'bowl', 'spoon', 'handheld', 'ladle', 'brush','spyglass','weight'];
const BONE_NAMES = {
  body: ['body', 'torso', 'chest', 'upperbody', 'bipedbody'],
  head: ['head', 'bipedhead'],
  leftArm: ['leftarm', 'leftupperarm', 'armleft', 'arml', 'larm', 'upperarml', 'bipedleftarm'],
  rightArm: ['rightarm', 'rightupperarm', 'armright', 'armr', 'rarm', 'upperarmr', 'bipedrightarm'],
  leftElbow: ['leftforearm', 'leftlowerarm', 'leftelbow', 'forearml', 'lowerarml'],
  rightElbow: ['rightforearm', 'rightlowerarm', 'rightelbow', 'forearmr', 'lowerarmr'],
  leftHand: ['lefthandlocator', 'lefthand', 'handl', 'lhand', 'leftwrist'],
  rightHand: ['righthandlocator', 'righthand', 'handr', 'rhand', 'rightwrist'],
  leftLeg: ['leftleg', 'leftupperleg', 'legleft', 'legl', 'lleg', 'leftthigh', 'thighl', 'bipedleftleg'],
  rightLeg: ['rightleg', 'rightupperleg', 'legright', 'legr', 'rleg', 'rightthigh', 'thighr', 'bipedrightleg'],
  leftKnee: ['leftshin', 'leftlowerleg', 'leftknee', 'shinl', 'lowerlegl'],
  rightKnee: ['rightshin', 'rightlowerleg', 'rightknee', 'shinr', 'lowerlegr'],
};

function vector(value, length = 3) {
  return Array.isArray(value) && value.length === length &&
    value.every(Number.isFinite) ? value : null;
}

function caseInsensitiveKeys(map) {
  const names = new Map();
  for (const name of map.keys()) {
    const key = name.toLowerCase();
    names.set(key, names.has(key) ? null : name);
  }
  return names;
}

function namedGroup(THREE, name, parent, x = 0, y = 0, z = 0) {
  const node = new THREE.Group();
  node.name = name;
  node.position.set(x, y, z);
  parent.add(node);
  return node;
}

function createBoxes(THREE, geometries, materials) {
  const geometry = new THREE.BoxGeometry(1, 1, 1);
  geometries.add(geometry);
  const palette = new Map();
  return (parent, color, size, position) => {
    if (!palette.has(color)) {
      const material = new THREE.MeshStandardMaterial({color, roughness: .92});
      palette.set(color, material);
      materials.add(material);
    }
    const mesh = new THREE.Mesh(geometry, palette.get(color));
    mesh.position.set(...position);
    mesh.scale.set(...size);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  };
}

function createStudyProps(THREE, parent, box) {
  const makeBook = (name, cover, width, x, y, z, tilt) => {
    const book = namedGroup(THREE, name, parent, x, y, z);
    book.rotation.x = tilt;
    book.visible = false;
    for (const sign of [-1, 1]) {
      const page = namedGroup(THREE, 'page', book);
      page.rotation.y = sign * .16;
      box(page, cover, [width / 2, .173, .021], [sign * width / 4, 0, 0]);
      box(page, 0xefe4cb, [width / 2 - .016, .150, .019], [sign * width / 4, .002, .017]);
      for (const line of [-.034, .004, .042]) {
        box(page, 0xc4b69a, [width * .28, .008, .003], [sign * width / 4, line, .028]);
      }
    }
    return book;
  };
  const book = makeBook('book', 0x76534a, .356, 0, .883, .285, -1.00);
  const notebook = makeBook('notebook', 0x395b52, .265, .025, .881, .306, -1.23);
  const pen = namedGroup(THREE, 'pen', parent, -.106, .939, .337);
  pen.visible = false;
  box(pen, 0x433538, [.021, .116, .021], [0, 0, 0]);
  box(pen, 0xd6ad66, [.022, .026, .022], [0, .039, 0]);
  const hidden = (name, x, y, z) => {const node = namedGroup(THREE, name, parent, x, y, z); node.visible = false; return node;};
  // Broom: the hand grips near the top, the straw head brushes the floor ahead.
  const broom = hidden('broom', -.1, .93, .25);
  broom.rotation.x = -.45;
  box(broom, 0xa88d6f, [.034, 1.02, .034], [0, -.34, 0]);
  box(broom, 0x9d8667, [.25, .045, .08], [0, -.83, 0]);
  box(broom, 0xd8bd8c, [.27, .15, .07], [0, -.92, 0]);
  for (const x of [-.09, 0, .09]) box(broom, 0xc9ab79, [.025, .15, .072], [x, -.92, .001]);
  // Watering can hangs from the hand; drops fall from the spout while tipped.
  const can = hidden('can', -.2, .86, .33);
  box(can, 0x9db496, [.2, .16, .15], [0, -.1, 0]);
  box(can, 0x8da58c, [.03, .1, .15], [0, .01, -.01]);
  const spout = box(can, 0x9db496, [.04, .04, .2], [0, -.07, .15]);
  spout.rotation.x = -.5;
  box(can, 0x8da58c, [.07, .03, .07], [0, -.02, .25]);
  const drops = namedGroup(THREE, 'drops', can, 0, -.1, .29);
  for (const [dx, dy] of [[-.02, 0], [.02, -.07], [0, -.14]]) box(drops, 0x9fc4bc, [.018, .045, .018], [dx, dy, 0]);
  // Bowl and spoon for meals.
  const bowl = hidden('bowl', .1, .84, .28);
  box(bowl, 0xefe4cb, [.18, .07, .18], [0, 0, 0]);
  box(bowl, 0x9db496, [.185, .015, .185], [0, .02, 0]);
  box(bowl, 0xe4c77e, [.14, .012, .14], [0, .036, 0]);
  const spoon = hidden('spoon', -.12, .9, .27);
  box(spoon, 0xd8d2ba, [.018, .018, .15], [0, 0, 0]);
  box(spoon, 0xd8d2ba, [.045, .014, .055], [0, -.004, .08]);
  // Handheld console with a lit screen.
  const handheld = hidden('handheld', 0, .89, .3);
  handheld.rotation.x = -1.0;
  box(handheld, 0x4a5a63, [.27, .13, .03], [0, 0, 0]);
  box(handheld, 0xa8e6cf, [.12, .085, .008], [0, .005, .018]);
  box(handheld, 0xdb9690, [.026, .026, .012], [.095, .01, .018]);
  box(handheld, 0xe4c77e, [.026, .026, .012], [-.095, .01, .018]);
  // Ladle for stirring the pot.
  const ladle = hidden('ladle', -.12, 1.02, .37);
  ladle.rotation.x = -.35;
  box(ladle, 0xb9c2b5, [.024, .2, .024], [0, -.05, 0]);
  box(ladle, 0xb9c2b5, [.075, .05, .075], [0, -.15, .01]);
  // Toothbrush held at the mouth.
  const brush = hidden('brush', -.06, 1.24, .29);
  brush.rotation.z = 1.35;
  box(brush, 0x8fd0b0, [.022, .13, .022], [0, 0, 0]);
  box(brush, 0xf4efdc, [.03, .035, .03], [0, .07, .012]);
  const spyglass=hidden('spyglass',0,1.37,.24),weight=hidden('weight',-.12,.91,.24);
  box(spyglass,0x405a83,[.090,.090,.31],[0,0,.08]);
  box(spyglass,0xd6a65e,[.13,.13,.076],[0,0,.24]);
  box(spyglass,0x9bd3d9,[.088,.088,.016],[0,0,.281]);
  box(weight,0xbb955a,[.12,.10,.11],[0,-.035,0]);
  box(weight,0xe5c487,[.058,.052,.061],[0,.038,0]);
  return {book, notebook, pen, broom, can, drops, bowl, spoon, handheld, ladle, brush,spyglass,weight};
}

function createBuiltin(THREE, rig, geometries, materials) {
  const box = createBoxes(THREE, geometries, materials);
  const hair = 0x523331, hairShade = 0x3c2527, hairLight = 0x754a3a;
  const skin = 0xf0c4a7, blush = 0xdc9487, eye = 0x362a36, iris = 0x597674;
  const dress = 0x4a7466, dressShade = 0x395b52, trim = 0xb0bc8e;
  const linen = 0xefe4cb, shoe = 0x433538, brass = 0xd6ad66;
  const body = namedGroup(THREE, 'body', rig, 0, .71);
  const head = namedGroup(THREE, 'head', body, 0, .44);
  box(body, skin, [.15, .10, .14], [0, .42, 0]);
  box(body, linen, [.32, .37, .22], [0, .21, 0]);
  box(body, dress, [.33, .26, .23], [0, .12, .003]);
  box(body, dress, [.055, .16, .014], [-.103, .29, .116]);
  box(body, dress, [.055, .16, .014], [.103, .29, .116]);
  box(body, trim, [.34, .035, .24], [0, .049, .004]);
  box(body, dressShade, [.39, .18, .27], [0, -.05, 0]);
  box(body, dress, [.44, .092, .30], [0, -.118, 0]);
  box(body, trim, [.442, .017, .302], [0, -.155, 0]);
  box(body, brass, [.045, .043, .016], [0, .068, .128]);

  box(head, skin, [.462, .409, .395], [0, .238, .015]);
  box(head, hairShade, [.493, .469, .137], [0, .237, -.161]);
  box(head, hair, [.507, .137, .444], [0, .427, -.004]);
  box(head, hairLight, [.438, .065, .397], [.006, .485, -.016]);
  box(head, hair, [.166, .064, .298], [-.04, .52, -.038]);
  box(head, hair, [.056, .325, .321], [-.238, .266, .039]);
  box(head, hair, [.056, .377, .262], [.238, .226, .003]);
  box(head, hairShade, [.089, .172, .141], [.207, .053, -.139]);
  box(head, hairShade, [.088, .152, .132], [-.208, .068, -.131]);
  box(head, hair, [.263, .079, .038], [-.083, .385, .215]);
  box(head, hairLight, [.143, .059, .031], [.114, .403, .220]);
  box(head, hair, [.079, .067, .036], [-.161, .337, .216]);
  box(head, hairLight, [.055, .052, .038], [-.106, .344, .219]);
  box(head, brass, [.071, .021, .018], [.172, .363, .242]).rotation.z = .22;
  const eyes = [];
  for (const x of [-.109, .109]) {
    const lid = box(head, eye, [.060, .067, .014], [x, .229, .217]);
    const irisMesh = box(head, iris, [.043, .026, .009], [x + .002, .210, .225]);
    const glint = box(head, linen, [.018, .019, .008], [x - .009, .244, .227]);
    box(head, blush, [.049, .018, .011], [x * 1.42, .166, .219]);
    eyes.push({lid, iris: irisMesh, glint, height: .067});
  }
  box(head, 0x9c6662, [.031, .014, .012], [0, .135, .219]);

  const roles = {body, head};
  for (const [side, sign] of [['left', 1], ['right', -1]]) {
    const arm = namedGroup(THREE, side + 'Arm', body, sign * .213, .358);
    const elbow = namedGroup(THREE, side + 'Elbow', arm, 0, -.188);
    box(arm, linen, [.131, .194, .143], [0, -.092, 0]);
    box(arm, trim, [.133, .032, .145], [0, -.174, 0]);
    box(elbow, skin, [.094, .192, .109], [0, -.091, 0]);
    const leg = namedGroup(THREE, side + 'Leg', rig, sign * .108, .637);
    const knee = namedGroup(THREE, side + 'Knee', leg, 0, -.272);
    box(leg, skin, [.148, .278, .154], [0, -.134, 0]);
    box(knee, linen, [.145, .257, .151], [0, -.119, 0]);
    box(knee, trim, [.148, .031, .154], [0, -.02, 0]);
    box(knee, shoe, [.157, .108, .214], [0, -.303, .029]);
    box(knee, dressShade, [.159, .019, .217], [0, -.355, .029]);
    roles[side + 'Arm'] = arm;
    roles[side + 'Elbow'] = elbow;
    roles[side + 'Leg'] = leg;
    roles[side + 'Knee'] = knee;
  }

  const props = createStudyProps(THREE, rig, box);
  props.hands = [roles.leftElbow, roles.rightElbow].map(bone => ({
    bone, local: new THREE.Vector3(0, -.18, 0), point: new THREE.Vector3(),
  }));
  return {bones: new Map(Object.entries(roles)), roles, props, eyes};
}

// The world views the model's north side from +Z. X/Y stay in model units.
function modelPosition(THREE, value) {
  return new THREE.Vector3(value[0], value[1], -value[2]);
}

function modelRotation(THREE, value) {
  return new THREE.Euler(value[0] * RADIANS, -value[1] * RADIANS, -value[2] * RADIANS, 'ZYX');
}

// Each face uses top-left, top-right, bottom-right and bottom-left corners.
// The source side names follow the GeckoLib/YSM face convention.
const FACES = [
  {name: 'west', normal: [1, 0, 0], corners: [7, 6, 2, 3], axes: [2, 1]},
  {name: 'east', normal: [-1, 0, 0], corners: [4, 5, 1, 0], axes: [2, 1]},
  {name: 'up', normal: [0, 1, 0], corners: [4, 6, 7, 5], axes: [0, 2]},
  {name: 'down', normal: [0, -1, 0], corners: [1, 3, 2, 0], axes: [0, 2]},
  {name: 'north', normal: [0, 0, 1], corners: [5, 7, 3, 1], axes: [0, 1]},
  {name: 'south', normal: [0, 0, -1], corners: [6, 4, 0, 2], axes: [0, 1]},
];

function cubeUVs(cube, size) {
  if (!Array.isArray(cube.uv) && cube.uv != null) {
    const rects = {};
    for (const {name, axes} of FACES) {
      const data = cube.uv[name];
      const start = vector(data?.uv, 2);
      if (!start) continue;
      const extent = vector(data.uv_size, 2) ?? axes.map(axis => size[axis]);
      rects[name] = [...start, ...extent, data.uv_rotation ?? 0];
    }
    return rects;
  }
  const [u, v] = vector(cube.uv, 2) ?? ZERO;
  const [x, y, z] = size.map(Math.floor);
  return {
    west: [u + z + x, v + z, z, y, 0],
    east: [u, v + z, z, y, 0],
    up: [u + z, v, x, z, 0],
    down: [u + z + x, v + z, x, -z, 0],
    north: [u + z, v + z, x, y, 0],
    south: [u + 2 * z + x, v + z, x, y, 0],
  };
}

function appendCube(THREE, buffer, cube, bone, width, height) {
  const origin = vector(cube.origin);
  const size = vector(cube.size);
  if (!origin || !size || size.some(axis => axis < 0)) return;
  const inflate = cube.inflate ?? bone.data.inflate ?? 0;
  if (!Number.isFinite(inflate)) return;
  const center = origin.map((value, axis) => value + size[axis] / 2);
  const pivot = modelPosition(THREE, vector(cube.pivot) ?? center);
  const rotation = new THREE.Quaternion().setFromEuler(modelRotation(THREE, vector(cube.rotation) ?? ZERO));
  const half = size.map(axis => Math.max(0, axis / 2 + inflate));
  const [x, y, z] = modelPosition(THREE, center).toArray();
  const corners = Array.from({length: 8}, (_, index) => new THREE.Vector3(
    x + (index & 2 ? half[0] : -half[0]),
    y + (index & 4 ? half[1] : -half[1]),
    z + (index & 1 ? half[2] : -half[2]),
  ));
  for (let index = 0; index < corners.length; index++) {
    corners[index].sub(pivot).applyQuaternion(rotation).add(pivot).sub(bone.pivot);
  }
  const mirror = cube.mirror ?? bone.data.mirror ?? false;
  const rects = cubeUVs(cube, size);
  for (const face of FACES) {
    if (face.axes.some(axis => half[axis] === 0)) continue;
    const source = mirror && face.name === 'east' ? 'west'
      : mirror && face.name === 'west' ? 'east' : face.name;
    const rect = rects[source];
    if (!rect) continue;
    const [u, v, w, h, angle] = rect;
    const [left, right] = mirror ? [u + w, u] : [u, u + w];
    const uv = [[left, v], [right, v], [right, v + h], [left, v + h]];
    const turns = [90, 180, 270].includes(angle) ? angle / 90 : 0;
    const normal = new THREE.Vector3(...face.normal).applyQuaternion(rotation);
    const index = buffer.positions.length / 3;
    for (let vertex = 0; vertex < 4; vertex++) {
      const point = corners[face.corners[vertex]];
      const [texX, texY] = uv[(vertex + 4 - turns) % 4];
      buffer.positions.push(point.x, point.y, point.z);
      buffer.normals.push(normal.x, normal.y, normal.z);
      buffer.uvs.push(texX / width, 1 - texY / height);
    }
    buffer.indices.push(index, index + 2, index + 1, index, index + 3, index + 2);
  }
}

function loadImported(THREE, rig, model, geometries, materials) {
  const description = model.geometry?.description;
  const width = description?.texture_width;
  const height = description?.texture_height;
  if (!(Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0) ||
      !Array.isArray(model.geometry?.bones)) {
    throw new Error('Avatar geometry is missing bones or texture dimensions');
  }
  const definitions = new Map();
  for (const data of model.geometry.bones) {
    if (typeof data?.name !== 'string' || !data.name.trim()) throw new Error('Invalid avatar bone name');
    const name = data.name;
    if (definitions.has(name)) throw new Error('Duplicate avatar bone name');
    definitions.set(name, {data, pivot: modelPosition(THREE, vector(data.pivot) ?? ZERO)});
  }
  const lowerNames = caseInsensitiveKeys(definitions);
  const material = new THREE.MeshStandardMaterial({
    color: 0xffffff, roughness: .95, transparent: true, alphaTest: .08,
  });
  materials.add(material);
  const bones = new Map();
  const visiting = new Set();
  const addBone = name => {
    if (bones.has(name)) return bones.get(name);
    if (visiting.has(name)) throw new Error('Avatar bone hierarchy contains a cycle');
    visiting.add(name);
    const bone = definitions.get(name);
    const rawParent = bone.data.parent;
    const parentName = definitions.has(rawParent) ? rawParent : lowerNames.get(rawParent?.toLowerCase());
    const parent = definitions.get(parentName);
    if (rawParent && !parent) throw new Error('Avatar bone has an unknown parent');
    const node = namedGroup(THREE, bone.data.name, parent ? addBone(parentName) : rig);
    node.position.copy(bone.pivot);
    if (parent) node.position.sub(parent.pivot);
    node.rotation.copy(modelRotation(THREE, vector(bone.data.rotation) ?? ZERO));
    const buffer = {positions: [], normals: [], uvs: [], indices: []};
    for (const cube of bone.data.cubes ?? []) appendCube(THREE, buffer, cube, bone, width, height);
    if (buffer.indices.length) {
      const geometry = new THREE.BufferGeometry();
      geometries.add(geometry);
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(buffer.positions, 3));
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(buffer.normals, 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(buffer.uvs, 2));
      geometry.setIndex(buffer.indices);
      geometry.computeBoundingBox();
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      node.add(mesh);
    }
    visiting.delete(name);
    bones.set(name, node);
    return node;
  };
  for (const name of definitions.keys()) addBone(name);
  const bounds = new THREE.Box3().setFromObject(rig, true);
  const size = bounds.getSize(new THREE.Vector3());
  if (bounds.isEmpty() || !Number.isFinite(size.y) || size.y < .0001) {
    throw new Error('Avatar geometry has no visible height');
  }
  const scale = AVATAR_HEIGHT / size.y;
  const center = bounds.getCenter(new THREE.Vector3());
  rig.scale.setScalar(scale);
  rig.position.set(-center.x * scale, -bounds.min.y * scale, -center.z * scale);
  const normalizedNames = new Map([...bones].map(([name, node]) => [name.toLowerCase().replace(/[^a-z0-9]/g, ''), node]));
  const roles = {};
  for (const [role, aliases] of Object.entries(BONE_NAMES)) {
    const name = aliases.find(alias => normalizedNames.has(alias));
    if (name) roles[role] = normalizedNames.get(name);
  }
  return {bones, roles, material};
}

function handAnchor(THREE, roles, side) {
  const hand = roles[side + 'Hand'];
  if (hand) return {bone: hand, local: new THREE.Vector3(), point: new THREE.Vector3()};
  const bone = roles[side + 'Elbow'] ?? roles[side + 'Arm'];
  const mesh = bone?.children.find(node => node.isMesh);
  const bounds = mesh?.geometry.boundingBox;
  if (!bounds) return null;
  const local = bounds.getCenter(new THREE.Vector3());
  local.y = bounds.min.y + .06 * (bounds.max.y - bounds.min.y);
  return {bone, local, point: new THREE.Vector3()};
}

function placeHeldProps(props, pose, seconds) {
  const [left, right] = props.hands;
  const {book, notebook, pen} = props;
  const parent = book.parent;
  for (const {bone, local, point} of props.hands) parent.worldToLocal(bone.localToWorld(point.copy(local)));
  for (const name of ['broom', 'can', 'ladle', 'brush', 'spoon','weight','spyglass']) if (props[name].visible) props[name].position.copy(right.point);
  if (props.bowl.visible) props.bowl.position.copy(left.point);
  if (props.handheld.visible) props.handheld.position.copy(left.point).lerp(right.point, .5);
  if (pose === 'read' || pose === 'sit_read') {
    book.position.copy(left.point).lerp(right.point, .5);
    book.position.y += .012;
    book.position.z += .025;
    book.scale.setScalar(Math.max(.65, Math.min(1.25, left.point.distanceTo(right.point) / .34)));
  } else if (notebook.visible) {
    notebook.position.copy(left.point).lerp(right.point, .34);
    notebook.position.z += .025;
    pen.position.copy(right.point).lerp(left.point, .13);
    pen.position.y += .027;
    pen.position.z += .021;
    pen.position.x += Math.sin(seconds * 9) * .011;
  }
}

function numericVector(value) {
  if (Number.isFinite(value)) return [value, value, value];
  if (vector(value, 1)) return [value[0], value[0], value[0]];
  return vector(value);
}

function compileTrack(value, allowMolang = false) {
  const constant = numericVector(value);
  if (constant) return [{time: 0, pre: constant, post: constant}];
  if (allowMolang) {
    const mv = compileMolangVector(value);
    if (mv) {
      if (!mv.dynamic) return [{time: 0, pre: mv.constant, post: mv.constant}];
      return [{time: 0, pre: ZERO, post: ZERO, preFn: mv.eval, postFn: mv.eval, molangDynamic: true}];
    }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const frames = [];
  for (const [key, frame] of Object.entries(value)) {
    if (!/^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(key)) return null;
    const time = Number(key);
    if (!Number.isFinite(time)) return null;
    if (!allowMolang) {
      const direct = numericVector(frame);
      const pre = direct ?? numericVector(frame?.pre);
      const post = direct ?? numericVector(frame?.post);
      if (!pre && !post) return null;
      if ((frame?.pre != null && !pre) || (frame?.post != null && !post)) return null;
      frames.push({time, pre: pre ?? post, post: post ?? pre, curve: frame?.lerp_mode});
    } else {
      const directMv = compileMolangVector(frame);
      const preMv = directMv ?? (frame?.pre != null ? compileMolangVector(frame.pre) : null);
      const postMv = directMv ?? (frame?.post != null ? compileMolangVector(frame.post) : null);
      if (!preMv && !postMv) return null;
      if ((frame?.pre != null && !preMv) || (frame?.post != null && !postMv)) return null;
      const effPre = preMv ?? postMv;
      const effPost = postMv ?? preMv;
      frames.push({
        time,
        pre: effPre.dynamic ? ZERO : effPre.constant,
        post: effPost.dynamic ? ZERO : effPost.constant,
        preFn: effPre.dynamic ? effPre.eval : null,
        postFn: effPost.dynamic ? effPost.eval : null,
        molangDynamic: Boolean(effPre.dynamic || effPost.dynamic),
        curve: frame?.lerp_mode,
      });
    }
  }
  return frames.length ? frames.sort((a, b) => a.time - b.time) : null;
}

function mergeAnimationTables(primary, molangExtra) {
  if (!molangExtra || typeof molangExtra !== 'object') return primary;
  const merged = {};
  for (const [name, anim] of Object.entries(primary ?? {})) {
    merged[name] = {
      ...anim,
      bones: {...(anim?.bones ?? {})},
    };
  }
  for (const [name, anim] of Object.entries(molangExtra)) {
    if (!merged[name]) {
      merged[name] = {...anim, bones: {...(anim?.bones ?? {})}};
      continue;
    }
    if (anim?.loop !== undefined && merged[name].loop === undefined) merged[name].loop = anim.loop;
    if (anim?.animation_length !== undefined && merged[name].animation_length === undefined) {
      merged[name].animation_length = anim.animation_length;
    }
    for (const [boneName, boneChannels] of Object.entries(anim?.bones ?? {})) {
      merged[name].bones[boneName] = {
        ...(merged[name].bones[boneName] ?? {}),
        ...(boneChannels ?? {}),
      };
    }
  }
  return merged;
}

function compileClips(animations, bones, allowMolang = false) {
  const clips = [];
  let ignoredTracks = 0;
  let linearizedCurves = false;
  const lowerNames = caseInsensitiveKeys(bones);
  for (const [name, animation] of Object.entries(animations ?? {})) {
    const channels = [];
    let duration = 0;
    let hasMolang = false;
    for (const [boneName, data] of Object.entries(animation?.bones ?? {})) {
      const bone = bones.get(boneName) ?? bones.get(lowerNames.get(boneName.toLowerCase()));
      if (!bone) continue;
      for (const channel of ['position', 'rotation', 'scale']) {
        if (data?.[channel] == null) continue;
        const frames = compileTrack(data[channel], allowMolang);
        if (!frames) {
          ignoredTracks++;
          continue;
        }
        if (frames.some(frame => frame.molangDynamic)) hasMolang = true;
        if (frames.some(frame => frame.curve === 'catmullrom')) linearizedCurves = true;
        duration = Math.max(duration, frames.at(-1).time);
        channels.push({bone, channel, frames});
      }
    }
    if (!channels.length) continue;
    if (Number.isFinite(animation.animation_length) && animation.animation_length > 0) {
      duration = animation.animation_length;
    }
    const dynamic = hasMolang || channels.some(({frames}) => {
      const start = frames[0].post;
      return frames.slice(1).some(({pre, post}) => start.some((value, axis) =>
        value !== pre[axis] || value !== post[axis]));
    });
    const loop = animation.loop === true || animation.loop === 'loop' ||
      (allowMolang && hasMolang && animation.loop !== false);
    clips.push({name, channels, duration, dynamic, hasMolang, loop});
  }
  return {clips, ignoredTracks, linearizedCurves};
}

function chooseClip(clips, pose) {
  let best = null;
  let bestScore = Infinity;
  for (const clip of clips) {
    if (pose === 'walk' && !clip.dynamic) continue;
    const name = clip.name.toLowerCase();
    const suffix = name.split('.').at(-1);
    const tokens = suffix.split(/[^a-z0-9]+/);
    const normalized = suffix.replace(/[^a-z0-9]/g, '');
    for (const [index, alias] of CLIP_NAMES[pose].entries()) {
      const score = name === alias ? index : suffix === alias ? 10 + index
        : normalized === alias ? 20 + index : tokens.includes(alias) ? 30 + index : Infinity;
      if (score < bestScore) {
        best = clip;
        bestScore = score;
      }
    }
  }
  return best;
}

function evalFrameVec(frame, side, queryCtx) {
  if (side === 'pre') return frame.preFn ? frame.preFn(queryCtx) : frame.pre;
  return frame.postFn ? frame.postFn(queryCtx) : frame.post;
}

function sampleTrack(frames, time, out, queryCtx = null) {
  const first = frames[0];
  if (time < first.time) return evalFrameVec(first, 'pre', queryCtx);
  let low = 0, high = frames.length;
  while (low + 1 < high) {
    const mid = (low + high) >> 1;
    if (frames[mid].time <= time) low = mid;
    else high = mid;
  }
  const from = frames[low], to = frames[high];
  if (!to || time === from.time) return evalFrameVec(from, 'post', queryCtx);
  const t = (time - from.time) / (to.time - from.time);
  const fromVec = evalFrameVec(from, 'post', queryCtx);
  const toVec = evalFrameVec(to, 'pre', queryCtx);
  for (let axis = 0; axis < 3; axis++) out[axis] = fromVec[axis] + t * (toVec[axis] - fromVec[axis]);
  return out;
}

function applyClip(clip, seconds, sample, queryCtx = null) {
  const time = clip.loop
    ? (clip.duration > 0 ? seconds % clip.duration : seconds)
    : Math.min(seconds, clip.duration);
  if (queryCtx) queryCtx.anim_time = time;
  for (const {bone, channel, frames} of clip.channels) {
    const [x, y, z] = sampleTrack(frames, time, sample, queryCtx);
    if (channel === 'position') {
      bone.position.x += x;
      bone.position.y += y;
      bone.position.z -= z;
    } else if (channel === 'rotation') {
      bone.rotation.x += x * RADIANS;
      bone.rotation.y -= y * RADIANS;
      bone.rotation.z -= z * RADIANS;
    } else {
      bone.scale.x *= x;
      bone.scale.y *= y;
      bone.scale.z *= z;
    }
  }
}

function applyProcedural(roles, motion, pose, seconds) {
  const rotate = (bone, x, y = 0, z = 0) => {
    if (!bone) return;
    bone.rotation.x += x;
    bone.rotation.y += y;
    bone.rotation.z += z;
  };
  const {body, head, leftArm, rightArm, leftElbow, rightElbow, leftLeg, rightLeg, leftKnee, rightKnee} = roles;
  // Shoulder + elbow bend; models without an elbow fold part of the bend into the shoulder.
  const limb = (arm, elbow, a, e) => {rotate(arm, elbow ? a : a + e * .6); rotate(elbow, e);};
  const seat = () => {
    motion.position.y = -.235;
    rotate(leftLeg, -1.38, -.10);
    rotate(rightLeg, -1.38, .10);
    rotate(leftKnee, 1.32);
    rotate(rightKnee, 1.32);
  };
  const breath = Math.sin(seconds * 2.4);
  if(pose==='survey'){
    rotate(head,-.08,Math.sin(seconds*.57)*.12);rotate(body,-.025);
    limb(rightArm,rightElbow,-1.32,-1.28);limb(leftArm,leftElbow,-1.02,-.82);
  }else if(pose==='weigh'){
    rotate(head,.22);rotate(body,.06);
    limb(rightArm,rightElbow,-.85-Math.sin(seconds*1.55)*.24,-.66);limb(leftArm,leftElbow,-.48,-.32);
  }else if (pose === 'cook') {
    // Stirring the pot: right hand circles the ladle, left steadies the handle.
    const stir = Math.sin(seconds * 3.6);
    motion.position.y = Math.abs(breath) * .008;
    rotate(body, .06, stir * .03);
    rotate(head, .24, -.12 + Math.sin(seconds * .8) * .05);
    limb(rightArm, rightElbow, -1.3 + stir * .08, -.3);
    rotate(rightArm, 0, 0, Math.cos(seconds * 3.6) * .1);
    limb(leftArm, leftElbow, -1.15, -.35);
    rotate(leftLeg, .03);
  } else if (pose === 'wash') {
    // Leaning over the basin, hands at the face, brushing.
    const scrub = Math.sin(seconds * 8);
    rotate(body, .14);
    rotate(head, .1, scrub * .03);
    limb(rightArm, rightElbow, -1.6, -1.0 + scrub * .06);
    limb(leftArm, leftElbow, -1.35, -1.1);
    rotate(rightArm, 0, 0, scrub * .05);
  } else if (pose === 'sweep') {
    const swing = Math.sin(seconds * 2.4);
    motion.position.y = Math.abs(swing) * .01;
    rotate(body, .12, swing * .2);
    rotate(head, .2, -swing * .12);
    limb(rightArm, rightElbow, -.9, -.2);
    limb(leftArm, leftElbow, -.55, -.75);
    rotate(leftLeg, -.08 + swing * .05);
    rotate(rightLeg, .06 - swing * .05);
  } else if (pose === 'water') {
    motion.position.y = Math.abs(breath) * .008;
    rotate(body, .08, -.05);
    rotate(head, .28, Math.sin(seconds * .9) * .06);
    limb(rightArm, rightElbow, -.9, -.3);
    limb(leftArm, leftElbow, -.15, -.25);
    rotate(leftArm, 0, 0, .1);
  } else if (pose === 'sit_eat') {
    seat();
    // Spoon travels from bowl to mouth in an unhurried rhythm.
    const lift = (1 - Math.cos(seconds * 1.7)) / 2;
    rotate(body, .08);
    rotate(head, .2 - lift * .14, Math.sin(seconds * .6) * .05);
    limb(leftArm, leftElbow, -.5, -.9);
    limb(rightArm, rightElbow, -.5 - lift * .5, -.9 - lift * .9);
  } else if (pose === 'sit_game') {
    seat();
    const tap = Math.sin(seconds * 11);
    rotate(body, .1);
    rotate(head, .36, Math.sin(seconds * .7) * .04);
    limb(leftArm, leftElbow, -.56 + tap * .015, -.83);
    limb(rightArm, rightElbow, -.56 - tap * .015, -.83);
  } else if (pose === 'walk') {
    const stride = Math.sin(seconds * TAU * 1.64);
    motion.position.y = .027 * Math.abs(stride);
    rotate(body, .045, stride * .08);
    rotate(head, -.04, -stride * .06);
    rotate(leftLeg, stride * .48);
    rotate(rightLeg, -stride * .48);
    rotate(leftKnee, Math.max(0, stride) * .28);
    rotate(rightKnee, Math.max(0, -stride) * .28);
    rotate(leftArm, -stride * .45, 0, .07);
    rotate(rightArm, stride * .45, 0, -.07);
    rotate(leftElbow, -.16);
    rotate(rightElbow, -.16);
  } else if (pose === 'rest' || pose === 'sit') {
    motion.position.y = -.235;
    rotate(body, .04);
    rotate(head, .13, Math.sin(seconds * 1.4) * .10);
    rotate(leftLeg, -1.38, -.10);
    rotate(rightLeg, -1.38, .10);
    rotate(leftKnee, 1.32);
    rotate(rightKnee, 1.32);
    rotate(leftArm, -.39);
    rotate(rightArm, -.39);
    rotate(leftElbow, -.46);
    rotate(rightElbow, -.46);
  } else if (pose === 'sit_read' || pose === 'sit_write') {
    motion.position.y = -.235;
    rotate(body, .06);
    rotate(leftLeg, -1.38, -.10);
    rotate(rightLeg, -1.38, .10);
    rotate(leftKnee, 1.32);
    rotate(rightKnee, 1.32);
    const writing = pose === 'sit_write';
    rotate(head, .29, writing ? .10 : Math.sin(seconds * 1.6) * .08);
    const stroke = writing ? Math.sin(seconds * 9) * .065 : 0;
    rotate(leftArm, leftElbow ? -.56 : -1.09, 0, -.10);
    rotate(rightArm, rightElbow ? -.58 : -1.09 + stroke, 0, .10);
    rotate(leftElbow, -.83);
    rotate(rightElbow, -.79 + stroke);
  } else if (pose === 'read' || pose === 'write') {
    const writing = pose === 'write';
    rotate(head, .29, writing ? .10 : Math.sin(seconds * 1.6) * .08);
    const stroke = writing ? Math.sin(seconds * 9) * .065 : 0;
    rotate(leftArm, leftElbow ? -.56 : -1.09, 0, -.10);
    rotate(rightArm, rightElbow ? -.58 : -1.09 + stroke, 0, .10);
    rotate(leftElbow, -.83);
    rotate(rightElbow, -.79 + stroke);
  } else if (pose === 'sleep') {
    motion.rotation.x = -Math.PI / 2;
    motion.position.y = Math.sin(seconds * 1.1) * .012;
    rotate(head, 0, .12, .05);
    rotate(leftArm, .06, 0, .16);
    rotate(rightArm, .06, 0, -.16);
  } else {
    const breath = Math.sin(seconds * 2.4);
    const shift = Math.sin(seconds * .5);
    motion.position.y = Math.abs(breath) * .012;
    rotate(body, 0, shift * .03, breath * .025);
    rotate(head, .012 + Math.sin(seconds * .9) * .03, Math.sin(seconds * 1.5) * .09, Math.sin(seconds * .7) * .02);
    rotate(leftArm, breath * .05, 0, .075 + shift * .02);
    rotate(rightArm, -breath * .05, 0, -.075 - shift * .02);
    rotate(leftLeg, shift * .02);
    rotate(rightLeg, -shift * .02);
  }
}

function animatePropDetails(props, pose, seconds) {
  if (pose === 'sit_eat') props.spoon.rotation.x = -(1 - Math.cos(seconds * 1.7)) * .25;
  if (pose === 'sweep') {
    props.broom.rotation.z = Math.sin(seconds * 2.4) * .3;
    props.broom.rotation.y = Math.sin(seconds * 2.4) * .2;
  }
  if (pose === 'water') props.can.rotation.x = .3 + Math.sin(seconds * 1.4) * .12;
  if (props.drops) {
    props.drops.visible = pose === 'water' && props.can?.visible;
    if (props.drops.visible) props.drops.position.y = -.1 - ((seconds * 1.6) % 1) * .12;
  }
}

/**
 * Creates a cabin character facing +Z. Pose time is elapsed seconds within the
 * current action. The caller owns the animation clock and scene placement.
 */
export function createAvatar(THREE, model = null, textureIndex = 0, options = {}) {
  const enableMolang = Boolean(options?.molang);
  const group = new THREE.Group();
  group.name = 'cabin-avatar';
  const motion = namedGroup(THREE, 'avatar-motion', group);
  const rig = namedGroup(THREE, 'avatar-rig', motion);
  const geometries = new Set(), materials = new Set();
  const builtin = model == null || model === 'builtin' || model?.format === 'builtin' || model?.source === 'builtin';
  const warnings = Array.isArray(model?.warnings) ? model.warnings.filter(item => typeof item === 'string') : [];
  const actions = {};
  const selectedClips = {};
  const clipSample = [0, 0, 0];
  let molangVars = Object.create(null);
  let bases = [], character = null, texture = null, disposed = false, boneCount = 0;
  let status = builtin ? 'ready' : 'loading';
  let currentPose = 'idle', currentPhase = 0, error = null;
  const selectedTexture = Number.isInteger(textureIndex) && textureIndex >= 0 ? textureIndex : 0;

  function setup(result, clips = []) {
    character = result;
    boneCount = character.bones.size;
    bases = [...character.bones.values()].map(bone => ({
      bone, position: bone.position.clone(), rotation: bone.rotation.clone(), scale: bone.scale.clone(),
    }));
    const roles = character.roles;
    const legs = Boolean(roles.leftLeg && roles.rightLeg);
    const arms = Boolean(roles.leftArm && roles.rightArm);
    if (!builtin) {
      const hands = ['left', 'right'].map(side => handAnchor(THREE, roles, side));
      if (hands.every(Boolean)) {
        const box = createBoxes(THREE, geometries, materials);
        character.props = {...createStudyProps(THREE, motion, box), hands};
      } else {
        warnings.push('模型缺少可定位的双手，阅读和写字道具不可用');
      }
    }
    const study = Boolean(arms && character.props);
    const procedural = {idle: Boolean(roles.body || roles.head || arms), walk: legs, read: study, write: study, rest: legs, sit: legs, sit_read: legs && study, sit_write: legs && study, sleep: Boolean(roles.body || roles.head),
      cook: arms, wash: arms, sweep: arms, water: arms, survey:arms, weigh:arms, sit_eat: legs && arms, sit_game: legs && arms};
    for (const pose of POSES) {
      const clip = chooseClip(clips, pose);
      if (clip) selectedClips[pose] = clip;
      actions[pose] = clip ? 'clip' : builtin || procedural[pose] ? 'procedural' : 'static';
    }
    // Minecraft / Yes Steve Model sleep clips animate side-curling & eyelids along the standing +Y spine
    // and expect the entity renderer to pitch -90 deg onto the bed mattress. Auto-detect upright sleep clips
    // and calibrate mattress lift + pillow alignment so imported YSM avatars lie flat on the bed.
    if (!builtin && selectedClips.sleep) {
      const sleepClip = selectedClips.sleep;
      const probeCtx = enableMolang ? {
        anim_time: 0, life_time: 0, ground_speed: 0, modified_move_speed: 0, modified_distance_moved: 0,
        is_on_ground: 0, is_in_water: 0, hurt_time: 0, head_x_rotation: 0, head_y_rotation: 0, vars: molangVars,
      } : null;
      motion.position.set(0, 0, 0);
      motion.rotation.set(0, 0, 0);
      applyClip(sleepClip, 0, clipSample, probeCtx);
      rig.updateMatrixWorld(true);
      const standBox = new THREE.Box3().setFromObject(rig);
      const sizeY = standBox.max.y - standBox.min.y;
      const sizeZ = standBox.max.z - standBox.min.z;
      if (Number.isFinite(sizeY) && Number.isFinite(sizeZ) && sizeY > sizeZ * 1.1) {
        sleepClip.needsBedPitch = true;
        motion.rotation.x = -Math.PI / 2;
        motion.updateMatrixWorld(true);
        const lieBox = new THREE.Box3().setFromObject(motion);
        if (Number.isFinite(lieBox.min.y)) {
          sleepClip.bedLiftY = Math.max(0.08, Math.min(0.62, -lieBox.min.y + 0.14));
        }
        if (Number.isFinite(lieBox.min.z)) {
          const headTargetZ = -1.52;
          const deltaZ = lieBox.min.z > -1.28 ? (headTargetZ - lieBox.min.z)
            : (lieBox.min.z < -1.80 ? (-1.75 - lieBox.min.z) : 0);
          sleepClip.bedShiftZ = Math.max(-0.35, Math.min(0.35, deltaZ));
        }
      }
      motion.position.set(0, 0, 0);
      motion.rotation.set(0, 0, 0);
    }
    setPose(currentPose, currentPhase);
  }

  function capturePose() {
    return [motion, ...bases.map(({bone}) => bone)].map(node => ({
      node, position: node.position.clone(), rotation: node.quaternion.clone(), scale: node.scale.clone(),
    }));
  }

  function setPose(pose, phase = 0, from = null, weight = 1) {
    if (disposed || pose === 'pause' || pose === 'paused') return;
    currentPose = POSES.includes(pose) ? pose : 'idle';
    currentPhase = Number.isFinite(phase) ? Math.max(0, phase) : 0;
    if (!character) return;
    const seconds = currentPhase;
    for (const {bone, position, rotation, scale} of bases) {
      bone.position.copy(position);
      bone.rotation.copy(rotation);
      bone.scale.copy(scale);
    }
    motion.position.set(0, 0, 0);
    motion.rotation.set(0, 0, 0);
    const clip = selectedClips[currentPose];
    if (clip) {
      const speed = currentPose === 'walk' ? 1.55 : 0;
      const queryCtx = enableMolang ? {
        anim_time: 0,
        life_time: seconds,
        ground_speed: speed,
        modified_move_speed: currentPose === 'walk' ? 0.65 : 0,
        modified_distance_moved: seconds * speed * 16,
        is_on_ground: currentPose === 'sleep' ? 0 : 1,
        is_in_water: 0,
        hurt_time: 0,
        head_x_rotation: 0,
        head_y_rotation: 0,
        vars: molangVars,
      } : null;
      applyClip(clip, seconds, clipSample, queryCtx);
      if (currentPose === 'sleep' && clip.needsBedPitch) {
        motion.rotation.x = -Math.PI / 2;
        motion.position.y = (clip.bedLiftY ?? 0.16) + Math.sin(seconds * 1.1) * .008;
        motion.position.z = clip.bedShiftZ ?? 0;
      }
    } else if (actions[currentPose] === 'procedural') {
      applyProcedural(character.roles, motion, currentPose, seconds);
    }
    // Imported (YSM) models without a dynamic idle clip or mapped bones still breathe and sway.
    const dynamicIdle = (clip && clip.dynamic) || (!clip && actions[currentPose] === 'procedural');
    if (!builtin && !dynamicIdle && (currentPose === 'idle' || currentPose === 'rest')) {
      const breath = Math.sin(seconds * 2.2);
      motion.position.y = Math.abs(breath) * .02;
      motion.rotation.z = breath * .02;
      motion.rotation.y = Math.sin(seconds * .5) * .04;
    }
    // Interpolate the actual sampled clip, including root motion and imported bone scales.
    if (from && weight < 1) {
      const remaining = 1 - Math.max(0, weight);
      for (const {node, position, rotation, scale} of from) {
        node.position.lerp(position, remaining);
        node.quaternion.slerp(rotation, remaining);
        node.scale.lerp(scale, remaining);
      }
    }
    const props = character.props;
    if (props) {
      const {pen} = props;
      const supported = actions[currentPose] !== 'static';
      const shown = supported ? POSE_PROPS[currentPose] || [] : [];
      for (const name of PROP_NAMES) if (props[name]) props[name].visible = shown.includes(name);
      if (shown.length) {
        placeHeldProps(props, currentPose, seconds);
        if (pen.visible) pen.rotation.z = -.57 + Math.sin(seconds * 9) * .14;
      }
      animatePropDetails(props, currentPose, seconds);
    }
    if (character.eyes) {
      const closed = currentPose === 'sleep';
      const awake = currentPose !== 'walk' && currentPose !== 'sleep';
      const blink = !closed && awake && (seconds % 3.6) > 3.45;
      const shut = closed || blink;
      for (const eye of character.eyes) {
        eye.lid.scale.y = eye.height * (shut ? .22 : 1);
        eye.iris.visible = !shut;
        eye.glint.visible = !shut;
      }
    }
  }

  const ready = builtin ? Promise.resolve() : Promise.resolve().then(async () => {
    if (disposed) return;
    const dataUrl = model.textures?.[selectedTexture]?.data_url;
    if (typeof dataUrl !== 'string' || !dataUrl.startsWith('data:image/png;base64,')) {
      throw new Error('Selected avatar texture is missing or is not PNG');
    }
    const imported = loadImported(THREE, rig, model, geometries, materials);
    const animTable = enableMolang ? mergeAnimationTables(model.animations, model.molang_animations) : model.animations;
    const {clips, ignoredTracks, linearizedCurves} = compileClips(animTable, imported.bones, enableMolang);
    if (ignoredTracks) warnings.push(`${ignoredTracks} unsupported animation tracks skipped`);
    if (linearizedCurves) warnings.push('部分模型动画曲线使用线性插值');
    setup(imported, clips);
    const image = await new THREE.TextureLoader().loadAsync(dataUrl);
    if (disposed) {
      image.dispose();
      return;
    }
    texture = image;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.magFilter = THREE.NearestFilter;
    texture.minFilter = THREE.NearestFilter;
    texture.generateMipmaps = false;
    texture.needsUpdate = true;
    imported.material.map = texture;
    imported.material.needsUpdate = true;
    rig.visible = true;
    status = 'ready';
  }).catch(reason => {
    if (disposed) return;
    status = 'error';
    error = reason instanceof Error ? reason.message : 'Avatar texture could not be decoded';
    release();
    throw new Error(error);
  });
  if (builtin) setup(createBuiltin(THREE, rig, geometries, materials));
  else rig.visible = false;

  function release() {
    texture?.dispose();
    texture = null;
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
    geometries.clear();
    materials.clear();
    rig.clear();
    motion.clear();
    bases = [];
    character = null;
    for (const pose of POSES) {
      delete selectedClips[pose];
      delete actions[pose];
    }
    boneCount = 0;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    status = 'disposed';
    group.removeFromParent();
    release();
  }

  function diagnostics() {
    return {
      source: builtin ? 'builtin' : 'ysm',
      status,
      pose: currentPose,
      motion_y: motion.position.y,
      mode: actions[currentPose] ?? 'static',
      molang: enableMolang,
      bone_count: boneCount,
      study_props: Boolean(character?.props),
      texture_index: builtin ? null : selectedTexture,
      actions: {...actions},
      supported_poses: POSES.filter(pose => actions[pose] && actions[pose] !== 'static'),
      clips: Object.fromEntries(Object.entries(selectedClips).map(([pose, clip]) => [pose, clip.name])),
      warnings: [...warnings],
      error,
    };
  }

  function bedBody() {
    const pose=currentPose, phase=currentPhase, liveVars=molangVars;
    // Sampling the sitting and sleeping clips must not advance a real model's
    // persistent Molang variables before its first displayed animation frame.
    molangVars=Object.assign(Object.create(null),liveVars);
    try {
      return measureBedBody(THREE,{group,setPose});
    } finally {
      molangVars=Object.assign(Object.create(null),liveVars);
      setPose(pose,phase);
      molangVars=liveVars;
    }
  }

  return {group, ready, capturePose, setPose, bedBody, dispose, diagnostics};
}

const OUTFIT_SYNONYMS = [
  [['睡衣', '家居服', '睡裙', 'pajama', 'sleepwear', 'nightgown'], ['pajama', 'sleep', 'home', 'night', '睡衣', '家居']],
  [['制服', '校服', '水手服', '学园', 'uniform', 'school', 'sailor'], ['uniform', 'school', 'sailor', '制服', '校服', '水手']],
  [['女仆', '围裙', 'maid', 'apron'], ['maid', 'apron', '女仆', '围裙']],
  [['冬装', '大衣', '毛衣', '围巾', '羽绒', 'winter', 'coat', 'sweater'], ['winter', 'coat', 'sweater', 'warm', '冬', '大衣', '毛衣']],
  [['夏装', '短袖', '连衣裙', '泳装', 'summer', 'dress', 'swim'], ['summer', 'dress', 'swim', 'light', '夏', '裙', '短袖']],
  [['常服', '日常', '便服', '休闲', 'casual', 'default', 'normal'], ['casual', 'normal', 'default', 'everyday', '常服', '日常', '便服']],
  [['礼服', '正装', 'formal', 'party', 'gala'], ['formal', 'party', 'dress', '礼服', '正装']],
  [['雨衣', '雨披', '防水', '户外', 'raincoat', 'outdoor', 'rain'], ['rain', 'raincoat', 'outdoor', 'coat', '雨衣', '户外', '防水']],
];

export function matchOutfitTexture(outfitText, textureNames = []) {
  if (typeof outfitText !== 'string' || !outfitText.trim() || !Array.isArray(textureNames) || textureNames.length < 2) {
    return null;
  }
  const text = outfitText.toLowerCase();
  const normalized = textureNames.map(n => String(n || '').toLowerCase().replace(/\.png$/i, ''));
  for (let i = 0; i < normalized.length; i++) {
    const clean = normalized[i].split('/').at(-1) || normalized[i];
    if (clean.length >= 2 && text.includes(clean)) return i;
  }
  let bestIdx = null;
  let bestScore = 0;
  for (let i = 0; i < normalized.length; i++) {
    const target = normalized[i];
    let score = 0;
    for (const [triggers, texTokens] of OUTFIT_SYNONYMS) {
      if (triggers.some(t => text.includes(t)) && texTokens.some(tok => target.includes(tok))) {
        score += 2;
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
    }
  }
  return bestScore > 0 ? bestIdx : null;
}

const VISITOR_COATS = [0x6d9286, 0x9b7f98, 0xc09b6e, 0x6f89a6, 0xa88276, 0x829b72];
const VISITOR_HAIRS = [0x4c3734, 0x6e5240, 0x383e4c, 0x8b6b52, 0x564352, 0x3b312d];

export function createGardenVisitorMesh(THREE, visitor = {}) {
  const group = new THREE.Group();
  group.name = 'garden-visitor';
  const geometries = new Set(), materials = new Set();
  const box = createBoxes(THREE, geometries, materials);
  const rawSeed = visitor?.palette_seed;
  const parsedSeed = typeof rawSeed === 'string' && /^[0-9a-f]+$/i.test(rawSeed)
    ? parseInt(rawSeed.slice(0, 8), 16)
    : Number(rawSeed);
  const seed = Math.abs(Number.isFinite(parsedSeed) && parsedSeed > 0 ? parsedSeed : 17);
  const rawForm = String(visitor?.form || 'pixel_avatar');
  const isCritter = rawForm === 'critter' || ['dove', 'squirrel', 'kitten'].includes(rawForm);
  const form = isCritter ? 'critter' : 'pixel_avatar';
  const species = ['dove', 'squirrel', 'kitten'].includes(rawForm) ? rawForm : (visitor?.critter_species || 'dove');
  let animTarget = null;

  if (form === 'critter') {
    const body = namedGroup(THREE, 'critter-body', group, 0, 0.12, 0);
    animTarget = body;
    if (species === 'squirrel') {
      box(body, 0xb87b4b, [0.22, 0.18, 0.28], [0, 0.04, 0]);
      box(body, 0xe8d5b8, [0.14, 0.13, 0.06], [0, 0.02, 0.14]);
      box(body, 0xb87b4b, [0.18, 0.16, 0.18], [0, 0.18, 0.08]);
      for (const sx of [-0.06, 0.06]) {
        box(body, 0x9c6238, [0.045, 0.065, 0.04], [sx, 0.28, 0.08]);
        box(body, 0x2c2422, [0.028, 0.028, 0.02], [sx, 0.19, 0.175]);
      }
      const tail = namedGroup(THREE, 'tail', body, 0, 0.12, -0.15);
      box(tail, 0xc98a57, [0.16, 0.26, 0.16], [0, 0.08, -0.05]);
      box(tail, 0xdca06d, [0.14, 0.14, 0.14], [0, 0.22, 0.02]);
    } else if (species === 'kitten') {
      box(body, 0xe6dcd0, [0.22, 0.16, 0.30], [0, 0.03, 0]);
      box(body, 0xd99b66, [0.12, 0.08, 0.14], [0.05, 0.08, -0.03]);
      box(body, 0xe6dcd0, [0.20, 0.17, 0.18], [0, 0.16, 0.11]);
      for (const sx of [-0.065, 0.065]) {
        box(body, 0xd99b66, [0.05, 0.07, 0.04], [sx, 0.265, 0.11]);
        box(body, 0x35302d, [0.028, 0.03, 0.02], [sx, 0.17, 0.202]);
      }
      box(body, 0xd8a0a0, [0.03, 0.02, 0.015], [0, 0.14, 0.205]);
      box(body, 0xd99b66, [0.05, 0.05, 0.20], [0, 0.10, -0.22]);
    } else {
      // Default: white/cream messenger dove
      box(body, 0xf2efe4, [0.20, 0.17, 0.28], [0, 0.04, 0]);
      box(body, 0xd9d5c5, [0.23, 0.11, 0.20], [0, 0.05, -0.01]);
      box(body, 0xf2efe4, [0.15, 0.15, 0.15], [0, 0.17, 0.09]);
      box(body, 0xe0b25d, [0.045, 0.035, 0.07], [0, 0.155, 0.19]);
      for (const sx of [-0.055, 0.055]) {
        box(body, 0x2f2a28, [0.024, 0.024, 0.018], [sx, 0.18, 0.165]);
        box(body, 0xd89c60, [0.03, 0.08, 0.03], [sx, -0.07, 0.02]);
      }
      box(body, 0xe5dfd0, [0.14, 0.04, 0.14], [0, 0.03, -0.18]);
    }
  } else {
    const coat = VISITOR_COATS[seed % VISITOR_COATS.length];
    const hair = VISITOR_HAIRS[(seed >> 3) % VISITOR_HAIRS.length];
    const body = namedGroup(THREE, 'visitor-chibi', group, 0, 0, 0);
    body.scale.setScalar(0.86);
    animTarget = body;
    box(body, 0x46393b, [0.12, 0.26, 0.13], [-0.08, 0.13, 0]);
    box(body, 0x46393b, [0.12, 0.26, 0.13], [0.08, 0.13, 0]);
    box(body, coat, [0.32, 0.42, 0.22], [0, 0.47, 0]);
    box(body, 0xefe6cf, [0.34, 0.07, 0.24], [0, 0.66, 0.01]);
    for (const sx of [-0.21, 0.21]) box(body, coat, [0.10, 0.34, 0.12], [sx, 0.48, 0]);
    box(body, 0xf0c6aa, [0.38, 0.36, 0.35], [0, 0.88, 0.01]);
    box(body, hair, [0.41, 0.14, 0.38], [0, 1.04, 0]);
    box(body, hair, [0.41, 0.34, 0.12], [0, 0.89, -0.14]);
    for (const sx of [-0.09, 0.09]) box(body, 0x332930, [0.045, 0.055, 0.015], [sx, 0.87, 0.188]);
  }

  return {
    group,
    tick(seconds) {
      if (!animTarget) return;
      const phase = seconds * 2.1 + (seed % 7);
      animTarget.position.y = (form === 'critter' ? 0.12 : 0) + Math.abs(Math.sin(phase)) * 0.025;
      animTarget.rotation.y = Math.sin(seconds * 0.9 + seed) * 0.14;
    },
    dispose() {
      group.removeFromParent();
      for (const g of geometries) g.dispose();
      for (const m of materials) m.dispose();
      geometries.clear();
      materials.clear();
    },
  };
}
