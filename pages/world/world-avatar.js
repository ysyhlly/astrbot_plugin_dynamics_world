import {createAvatar, createGardenVisitorMesh} from './avatar-model.js';
import {projectAvatar, projectAmbientMicro, projectJourneyRadar, resolveFurnitureLayout} from './avatar-state.js';
import {DEFAULT_BODY,avoidBed,clearBedFloor,crossesBed} from './cabin-bed.js';
import {cabinPlan,relocatePoint} from './cabin-plans.js';

// Visual interpolation never commits world events or starts new daily actions.
// Anchor changes glide through a Bezier-rounded navigation graph that dynamically
// detours around relocated furniture, swings the hinged front door when crossing
// thresholds, and plays stand-up / walk / sit-down transitions.
export const THRESHOLDS = {room: [1.15, .13, 3.55], garden: [1.05, -.25, 4.35]};
const DOORWAY_CENTER = [1.12, 3.74];
const WALK_SPEED = 1.55, STROLL_SPEED = .62;
const STAND_UP_MS = 380, SIT_DOWN_MS = 420;

const BASE_NAV = {
  room: {
    nodes: {
      T: [1.15, .13, 3.55], H: [1.4, .13, 1.5], F: [-.9, .13, 2.95], K: [-3.55, .13, 2.65],
      B: [-1.55, .13, .9], D: [0, .13, 1.0], E: [1.62, .13, 1.85], P: [2.62, .13, 2.95],
      C1: [2.1, .13, -.7], C2: [2.1, .13, -2.75], N: [.08, .13, -2.45], S: [-2.35, .13, -2.45], W: [-3.6, .13, -2.75],
    },
    edges: [['T', 'H'], ['T', 'P'], ['T', 'F'], ['H', 'F'], ['F', 'K'], ['F', 'B'], ['H', 'B'], ['H', 'D'], ['D', 'B'],
      ['H', 'E'], ['H', 'C1'], ['C1', 'C2'], ['C2', 'N'], ['N', 'S'], ['S', 'W']],
    attach: {cook: 'K', wash: 'W', eat: 'E', water: 'P', sweep: 'F', rest: 'B', game: 'B', read: 'B', write: 'D',
      sleep: 'B', idle: 'H', window_gaze: 'N', shelf_browse: 'S', cat_check: 'B', desk_tea: 'D', threshold: 'T'},
  },
  garden: {
    nodes: {
      GT: [1.05, -.25, 4.35], GS: [2.4, -.25, 4.35], GE: [4.85, -.25, 4.35], GX: [5.1, -.25, 5.15],
      GP: [-2.1, -.25, 5.6], GG: [.6, -.25, 6.4], SCALE: [5.05,-.25,6.23],
    },
    edges: [['GT', 'GS'], ['GS', 'GE'], ['GE', 'GX'], ['GX','SCALE'], ['GT', 'GP'], ['GT', 'GG']],
    attach: {water: 'GX', flower_scent: 'GX', pond_koi: 'GP', gate_look: 'GG', survey:'GP',weigh:'SCALE', threshold: 'GT'},
  },
};

export function buildDynamicRoomGraph(layout = null) {
  const nodes = {};
  for (const [k, v] of Object.entries(BASE_NAV.room.nodes)) nodes[k] = [...v];
  const attach = {...BASE_NAV.room.attach, ...(layout?.attachOverrides || {})};
  const occ = layout?.occupiedSlots || {};
  if (occ.center) {
    nodes.H = [1.85, .13, 2.35];
    nodes.D = [-0.65, .13, 0.25];
  }
  if (occ.right_wall === 'bed' || occ.right_wall === 'desk') {
    nodes.C1 = [1.65, .13, -.55];
  }
  if (occ.back_wall === 'bed' || occ.back_wall === 'desk') {
    nodes.C2 = [1.35, .13, -1.65];
  }
  if(layout?.plan?.id && layout.plan.id!=='cottage'){
    const original=cabinPlan('cottage');
    for(const [node,owner] of [['K','kitchen'],['W','washstand'],['E','table'],['P','plant'],['N','window']]){
      nodes[node]=relocatePoint(original[owner],layout.plan[owner],BASE_NAV.room.nodes[node]);
    }
    nodes.D=layout.chairApproach;nodes.B=layout.bedApproach;
    nodes.S=relocatePoint(original.shelves.back_wall,layout.plan.shelves.back_wall,BASE_NAV.room.nodes.S);
  }
  return {nodes, edges: BASE_NAV.room.edges, attach, obstacle:layout?.obstacle};
}

const VISITOR_GARDEN_SPOTS = {
  bench_west: {pos: [-3.4, 0.48, 5.05], yaw: 0.25},
  pond_edge: {pos: [-2.48, -0.24, 6.18], yaw: -0.55},
  arbor_gate: {pos: [1.12, -0.24, 6.72], yaw: -0.35},
  flower_path: {pos: [5.15, -0.24, 4.92], yaw: -1.1},
};

const PEER_VISIT_SPOTS = {
  garden_bench: {pos: [2.85, 0.12, 5.08], yaw: -0.2, pose: 'sit', location: 'garden'},
  tea_table: {pos: [2.78, 0.13, 2.58], yaw: Math.PI, pose: 'idle', location: 'room'},
  pond_side: {pos: [-2.12, -0.25, 5.88], yaw: -0.62, pose: 'idle', location: 'garden'},
};

const STROLL_LOOP = [[.8, -.25, 4.9], [1.0, -.25, 6.6], [-.6, -.25, 6.85], [-2.0, -.25, 6.0], [-1.0, -.25, 4.95]];
const easeInOut = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const flat = (a, b) => Math.hypot(a[0] - b[0], a[2] - b[2]);
const lerp3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];

// Ease over the first and last steps, with a constant pace in between.
function walkingProgress(elapsed, duration) {
  const t = Math.max(0, Math.min(1, elapsed / duration));
  const ramp = Math.min(.22, 320 / duration);
  if (t < ramp) return t * t / (2 * ramp * (1 - ramp));
  if (t > 1 - ramp) return 1 - (1 - t) ** 2 / (2 * ramp * (1 - ramp));
  return (t - ramp / 2) / (1 - ramp);
}

function shortestYaw(from, to) {
  let delta = (to - from) % (Math.PI * 2);
  if (delta > Math.PI) delta -= Math.PI * 2;
  if (delta < -Math.PI) delta += Math.PI * 2;
  return delta;
}

export function pathLength(path) {
  let total = 0;
  for (let i = 1; i < path.length; i++) total += dist(path[i - 1], path[i]);
  return total;
}

// Builds piecewise linear + quadratic Bezier corner arcs so interior turns never snap yaw.
function buildRoundedSegments(path, cornerRadius = 0.42, obstacle = null) {
  if (!Array.isArray(path) || path.length === 0) return {segments: [], total: 0};
  if (path.length === 1) return {segments: [{kind: 'line', a: path[0], b: path[0], len: 0}], total: 0};
  if (path.length === 2) {
    const len = dist(path[0], path[1]);
    return {segments: [{kind: 'line', a: path[0], b: path[1], len}], total: len};
  }
  const n = path.length;
  const trimIn = new Array(n).fill(0);
  const trimOut = new Array(n).fill(0);
  for (let i = 1; i < n - 1; i++) {
    const lenPrev = dist(path[i - 1], path[i]);
    const lenNext = dist(path[i], path[i + 1]);
    const r = Math.min(cornerRadius, lenPrev * 0.38, lenNext * 0.38);
    if (r > 0.03) {
      if (obstacle && crossesBed(lerp3(path[i],path[i-1],r/lenPrev),lerp3(path[i],path[i+1],r/lenNext),obstacle)) continue;
      trimIn[i] = r;
      trimOut[i] = r;
    }
  }
  const segments = [];
  let total = 0;
  let cursor = path[0];
  for (let i = 1; i < n - 1; i++) {
    const prev = path[i - 1], corner = path[i], next = path[i + 1];
    const dPrev = Math.max(1e-6, dist(prev, corner));
    const dNext = Math.max(1e-6, dist(corner, next));
    if (trimIn[i] > 0) {
      const entry = lerp3(corner, prev, trimIn[i] / dPrev);
      const exit = lerp3(corner, next, trimOut[i] / dNext);
      const lineLen = dist(cursor, entry);
      if (lineLen > 1e-5) {
        segments.push({kind: 'line', a: cursor, b: entry, len: lineLen});
        total += lineLen;
      }
      // Approximate quadratic Bezier arc length with 4 chords
      let bezLen = 0, lastP = entry;
      for (let s = 1; s <= 4; s++) {
        const u = s / 4, inv = 1 - u;
        const p = [
          inv * inv * entry[0] + 2 * inv * u * corner[0] + u * u * exit[0],
          inv * inv * entry[1] + 2 * inv * u * corner[1] + u * u * exit[1],
          inv * inv * entry[2] + 2 * inv * u * corner[2] + u * u * exit[2],
        ];
        bezLen += dist(lastP, p);
        lastP = p;
      }
      segments.push({kind: 'bezier', a: entry, c: corner, b: exit, len: Math.max(1e-5, bezLen)});
      total += Math.max(1e-5, bezLen);
      cursor = exit;
    } else {
      const lineLen = dist(cursor, corner);
      if (lineLen > 1e-5) {
        segments.push({kind: 'line', a: cursor, b: corner, len: lineLen});
        total += lineLen;
      }
      cursor = corner;
    }
  }
  const end = path[n - 1];
  const tailLen = dist(cursor, end);
  if (tailLen > 1e-5 || !segments.length) {
    segments.push({kind: 'line', a: cursor, b: end, len: tailLen});
    total += tailLen;
  }
  return {segments, total};
}

function sampleRoute({segments, total}, t, ease = true) {
  if (!segments.length || total <= 1e-6) {
    return {point: [...(segments[0]?.a || [0, 0, 0])], yaw: 0, distance: 0};
  }
  const clamped = Math.max(0, Math.min(1, t));
  const distance = (ease ? easeInOut(clamped) : clamped) * total;
  let target = distance;
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    if (target <= seg.len || i === segments.length - 1) {
      const u = seg.len > 1e-6 ? Math.min(1, Math.max(0, target / seg.len)) : 1;
      if (seg.kind === 'bezier') {
        const inv = 1 - u;
        const point = [
          inv * inv * seg.a[0] + 2 * inv * u * seg.c[0] + u * u * seg.b[0],
          inv * inv * seg.a[1] + 2 * inv * u * seg.c[1] + u * u * seg.b[1],
          inv * inv * seg.a[2] + 2 * inv * u * seg.c[2] + u * u * seg.b[2],
        ];
        const tx = 2 * inv * (seg.c[0] - seg.a[0]) + 2 * u * (seg.b[0] - seg.c[0]);
        const tz = 2 * inv * (seg.c[2] - seg.a[2]) + 2 * u * (seg.b[2] - seg.c[2]);
        const yaw = (Math.abs(tx) > 1e-5 || Math.abs(tz) > 1e-5)
          ? Math.atan2(tx, tz)
          : Math.atan2(seg.b[0] - seg.a[0], seg.b[2] - seg.a[2]);
        return {point, yaw, distance};
      }
      const point = lerp3(seg.a, seg.b, u);
      const yaw = Math.atan2(seg.b[0] - seg.a[0], seg.b[2] - seg.a[2]);
      return {point, yaw, distance};
    }
    target -= seg.len;
  }
  return {point: [...segments.at(-1).b], yaw: 0, distance};
}

export function smoothCornerPathPoint(path, t, ease = true, cornerRadius = 0.42) {
  const {point, yaw} = sampleRoute(buildRoundedSegments(path, cornerRadius), t, ease);
  return {point, yaw};
}

function nearestNode(graph, point) {
  let best = null, bestDistance = Infinity;
  for (const [name, node] of Object.entries(graph.nodes)) {
    const d = flat(node, point);
    if (d < bestDistance) {best = name; bestDistance = d;}
  }
  return best;
}

function route(graph, start, goal) {
  if (start === goal) return [start];
  const neighbours = new Map(Object.keys(graph.nodes).map(name => [name, []]));
  for (const [a, b] of graph.edges) {neighbours.get(a).push(b); neighbours.get(b).push(a);}
  const cost = new Map([[start, 0]]), previous = new Map(), open = new Set([start]);
  while (open.size) {
    let current = null;
    for (const name of open) if (current === null || cost.get(name) < cost.get(current)) current = name;
    open.delete(current);
    if (current === goal) break;
    for (const next of neighbours.get(current)) {
      const value = cost.get(current) + flat(graph.nodes[current], graph.nodes[next]);
      if (value < (cost.get(next) ?? Infinity)) {cost.set(next, value); previous.set(next, current); open.add(next);}
    }
  }
  if (!previous.has(goal)) return [start, goal];
  const names = [goal];
  while (names[0] !== start) names.unshift(previous.get(names[0]));
  return names;
}

function graphPath(location, from, to, pose, roomGraph) {
  const graph = location === 'room' ? roomGraph : BASE_NAV.garden;
  const goalNode = graph?.attach[pose];
  if (!graph || !goalNode || flat(from, to) < .85) return [from, to];
  const startNode = nearestNode(graph, from);
  const names = route(graph, startNode, goalNode);
  const points = names.map(name => graph.nodes[name]);
  const path = [from];
  for (const point of points) if (flat(path[path.length - 1], point) > .25) path.push(point);
  if (flat(path[path.length - 1], to) > .02) path.push(to);
  if (path.length > 2 && flat(from, path[2]) < flat(path[1], path[2]) && flat(from, path[1]) < 1.2) path.splice(1, 1);
  return path;
}

function localPath(location,from,to,pose,roomGraph) {
  const path=graphPath(location,from,to,pose,roomGraph);
  return location==='room'?avoidBed(path,roomGraph?.obstacle):path;
}

// Fold the legs (or turn onto the back) on the clear side, then slide onto
// the bedding. Reversing these phases gets the whole rig clear before standing.
function bedTransfer(aisle,onBed,t) {
  const fold=Math.min(1,t/.46), slide=Math.max(0,(t-.46)/.54);
  const point=lerp3(aisle,onBed,slide);
  point[1]=aisle[1]+(onBed[1]-aisle[1])*fold;
  return {point,fold};
}

function buildPath(fromLocation, from, toLocation, to, pose, roomGraph) {
  if (!fromLocation || fromLocation === toLocation || !THRESHOLDS[fromLocation] || !THRESHOLDS[toLocation]) {
    return localPath(toLocation, from, to, pose, roomGraph);
  }
  const out = localPath(fromLocation, from, THRESHOLDS[fromLocation], 'threshold', roomGraph);
  const inside = localPath(toLocation, THRESHOLDS[toLocation], to, pose, roomGraph);
  return out && inside ? [...out, ...inside] : null;
}

function modelPose(projection, overridePose = null) {
  if (!projection) return 'idle';
  const p = overridePose || projection.pose;
  if (projection.seated && p === 'read') return 'sit_read';
  if (projection.seated && p === 'write') return 'sit_write';
  if (p === 'eat') return projection.seated ? 'sit_eat' : 'idle';
  if (p === 'game') return 'sit_game';
  if (p === 'stroll') return 'walk';
  return p;
}

const strollRoute = buildRoundedSegments([...STROLL_LOOP, STROLL_LOOP[0]], .55);

export function createWorldAvatar(THREE, scene, render, {onDoorSwing = null, getBedSlot = ()=>null,getPlan=()=>cabinPlan('cottage')} = {}) {
  let character = null, modelId = '', textureIndex = 0, data = null, selection = {}, projection = null;
  let active = true, disposed = false, epoch = 0, guestEpoch = 0, frame = 0, lastFrame = 0, onState = () => {}, signature = '';
  let visual = null, yaw = 0, transit = null, settling = false, lastLocation = null, lastApproach = null, lastSample = 0, lastPath = null, strollFrom = 0;
  let body=DEFAULT_BODY, previousBedSlot=null, lastOnBed=false;
  let guestAvatar = null, guestKey = '', guestModelData = null, guestModelId = 'builtin', guestTexIdx = 0;
  let guestVisual = null, guestYaw = 0, guestTransit = null, hadHydratedScene = false;
  let doorAngle = 0;
  const visitorMeshes = new Map();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');

  function buildGuestPath(spotKey) {
    const spotCfg = PEER_VISIT_SPOTS[spotKey] || PEER_VISIT_SPOTS.garden_bench;
    const gateStart = [0.6, -0.25, 6.48];
    if (spotCfg.location === 'room') {
      return [gateStart, THRESHOLDS.garden, THRESHOLDS.room, [...spotCfg.pos]];
    }
    return [gateStart, [1.1, -0.25, 5.2], [...spotCfg.pos]];
  }

  function spawnGuestInstance(activeVisit, animateWalkIn) {
    if (guestAvatar) {guestAvatar.dispose(); guestAvatar = null;}
    if (!activeVisit || disposed) {
      guestVisual = null;
      guestTransit = null;
      return;
    }
    const spotKey = PEER_VISIT_SPOTS[activeVisit.spot] ? activeVisit.spot : 'garden_bench';
    const spotCfg = PEER_VISIT_SPOTS[spotKey];
    const tex = Number.isFinite(Number(activeVisit.texture_index)) ? Number(activeVisit.texture_index) : guestTexIdx;
    const mdl = (guestModelData && guestModelData.id === activeVisit.model_id && guestModelData.format !== 'builtin') ? guestModelData : null;
    guestAvatar = createAvatar(THREE, mdl, tex, {molang: true});
    guestAvatar.group.userData.worldAvatar = true;
    guestAvatar.group.userData.guestAvatar = true;
    scene.add(guestAvatar.group);
    if (animateWalkIn && !reduced.matches && !data?.isReplay) {
      const gPath = buildGuestPath(spotKey);
      const end = gPath.at(-1);
      if (spotCfg.pose === 'sit') gPath[gPath.length - 1] = [end[0], -.25, end[2]+.52];
      const route = buildRoundedSegments(gPath);
      guestVisual = [...gPath[0]];
      guestYaw = Math.atan2(gPath[1][0] - gPath[0][0], gPath[1][2] - gPath[0][2]);
      guestTransit = {route, start: Date.now(), walkMs: Math.max(900, route.total / WALK_SPEED * 1000), spotCfg};
      guestAvatar.group.position.set(guestVisual[0], guestVisual[1], guestVisual[2]);
      guestAvatar.group.rotation.y = guestYaw;
      guestAvatar.setPose('walk', 0);
    } else {
      guestTransit = null;
      guestVisual = [...spotCfg.pos];
      guestYaw = spotCfg.yaw;
      guestAvatar.group.position.set(spotCfg.pos[0], spotCfg.pos[1], spotCfg.pos[2]);
      guestAvatar.group.rotation.y = spotCfg.yaw;
      guestAvatar.setPose(spotCfg.pose, 0);
    }
  }

  function syncGuestAndVisitors() {
    const activeVisit = data?.world_space?.active_guest || data?.world_space?.active_visit || null;
    const nextGuestKey = activeVisit
      ? `${activeVisit.name || activeVisit.peer_character_id || activeVisit.peer_key || 'peer'}|${activeVisit.spot || 'garden_bench'}|${activeVisit.model_id || 'builtin'}|${activeVisit.texture_index || 0}`
      : '';
    if (nextGuestKey !== guestKey) {
      const wasEmpty = !guestKey;
      guestKey = nextGuestKey;
      spawnGuestInstance(activeVisit, wasEmpty && hadHydratedScene);
    }
    const list = Array.isArray(data?.mailbox?.visitors) ? data.mailbox.visitors : (Array.isArray(data?.mailbox?.active_visitors) ? data.mailbox.active_visitors : []);
    const rawVisitors = list.slice(0, 2);
    const keepIds = new Set();
    const usedSpots = new Set();
    for (const v of rawVisitors) {
      const vid = String(v?.visitor_id || v?.id || v?.sender_id || '');
      if (!vid) continue;
      keepIds.add(vid);
      let spotKey = VISITOR_GARDEN_SPOTS[v.spot] ? v.spot : 'arbor_gate';
      if (usedSpots.has(spotKey)) {
        spotKey = Object.keys(VISITOR_GARDEN_SPOTS).find(k => !usedSpots.has(k)) || 'pond_edge';
      }
      usedSpots.add(spotKey);
      const spotCfg = VISITOR_GARDEN_SPOTS[spotKey];
      const sig = `${v.form || 'pixel_avatar'}|${v.critter_species || ''}|${v.palette_seed || 0}|${spotKey}`;
      const existing = visitorMeshes.get(vid);
      if (existing && existing.sig === sig) continue;
      if (existing) existing.mesh.dispose();
      if (!disposed) {
        const mesh = createGardenVisitorMesh(THREE, v);
        mesh.group.userData.worldAvatar = true;
        mesh.group.position.set(spotCfg.pos[0], spotCfg.pos[1], spotCfg.pos[2]);
        mesh.group.rotation.y = spotCfg.yaw;
        scene.add(mesh.group);
        visitorMeshes.set(vid, {sig, mesh, visitor: v, spot: spotKey});
      }
    }
    for (const [vid, entry] of visitorMeshes) {
      if (!keepIds.has(vid)) {
        entry.mesh.dispose();
        visitorMeshes.delete(vid);
      }
    }
  }

  function updateDoorProximity(dt) {
    let nearDoor = false;
    const checkPos = (pos, moving) => {
      if (!pos) return false;
      const d = Math.hypot(pos[0] - DOORWAY_CENTER[0], pos[2] - DOORWAY_CENTER[1]);
      return moving ? d < 1.38 : d < 0.62;
    };
    if (projection?.visible && checkPos(visual, Boolean(transit || projection.pose === 'walk'))) nearDoor = true;
    if (!nearDoor && guestAvatar && checkPos(guestVisual, Boolean(guestTransit))) nearDoor = true;
    const targetAngle = nearDoor ? 1.22 : 0;
    if (Math.abs(targetAngle - doorAngle) > 0.004) {
      if (reduced.matches || dt <= 0) doorAngle = targetAngle;
      else doorAngle += (targetAngle - doorAngle) * Math.min(1, dt * 7.5);
      if (Math.abs(targetAngle - doorAngle) <= 0.005) doorAngle = targetAngle;
      onDoorSwing?.(doorAngle);
      return true;
    }
    return false;
  }

  function publish() {
    const key = JSON.stringify([
      projection?.visible, projection?.pose, projection?.seated, projection?.location,
      projection?.paused, projection?.label, projection?.locationLabel, projection?.positionBasis,
      projection?.source, projection?.micro?.id, character?.diagnostics().mode, !!transit,
      guestKey, !!guestTransit, visitorMeshes.size,
    ]);
    if (key !== signature) {signature = key; onState(projection, character?.diagnostics());}
  }

  function place(point, rotation) {
    character.group.position.set(point[0], point[1], point[2]);
    character.group.rotation.y = rotation;
  }

  function phaseFor(now) {
    if (reduced.matches) return 0;
    if (projection.pose === 'walk') return projection.walkDistance / WALK_SPEED;
    if ((projection.paused || data?.isReplay) && projection.clock === 'wall') return data.server_time || 0;
    if (projection.pose === 'sleep' || projection.clock === 'wall') return now / 1000;
    const action = data?.scene?.action;
    const duration = Math.max(0, (action?.step_ends_at || 0) - (action?.step_started_at || 0));
    return projection.progress * duration;
  }

  function stroll(now, dt) {
    if (!strollFrom) strollFrom = now;
    const distance = (now - strollFrom) / 1000 * STROLL_SPEED;
    const s = sampleRoute(strollRoute, (distance % strollRoute.total) / strollRoute.total, false);
    visual = s.point;
    yaw += shortestYaw(yaw, s.yaw) * Math.min(1, (dt || .04) * 8);
    place(visual, yaw);
    character.setPose('walk', distance / WALK_SPEED);
  }

  function sample(now = Date.now()) {
    const layout = resolveFurnitureLayout(data,body,getBedSlot(),getPlan());
    const roomGraph = buildDynamicRoomGraph(layout);
    const base = projectAvatar(data, selection, now,layout);
    const micro = projectAmbientMicro(data, base, now,layout);
    const journeyRadar = (base.location === 'away' || data?.scene?.phase === 'travelling' || data?.actor?.phase === 'travelling')
      ? projectJourneyRadar(data, now)
      : null;
    projection = {...base, micro, journeyRadar};
    const targetPos = micro.active ? micro.position : projection.position;
    const targetYaw = micro.active ? micro.rotationY : (projection.rotationY || 0);
    const effectivePose = micro.active ? micro.pose : projection.pose;
    const onBed=projection.location==='room' && ['rest','game','sleep'].includes(effectivePose);
    const bedKey=layout.plan.id+'/'+layout.bedSlot;
    if(previousBedSlot!==null && previousBedSlot!==bedKey && lastLocation==='room' && visual){
      transit=null;
      visual=lastOnBed && onBed?null:clearBedFloor([visual[0],.13,visual[2]],layout.obstacle);
      if(visual)place(visual,yaw);
      lastApproach=null;lastOnBed=false;
    }
    previousBedSlot=bedKey;
    const navKey = projection.cabinActivity==='cabin_testimony'?'write':micro.active && micro.id !== 'center_stand' ? micro.id : effectivePose;
    const dt = lastSample ? Math.min(.1, (now - lastSample) / 1000) : 0.033;
    lastSample = now;

    const still = reduced.matches || projection.paused || data?.isReplay;
    if (guestAvatar && guestTransit && still) {
      const {spotCfg} = guestTransit;
      guestTransit = null;
      guestVisual = [...spotCfg.pos];
      guestYaw = spotCfg.yaw;
      guestAvatar.group.position.set(...guestVisual);
      guestAvatar.group.rotation.y = guestYaw;
      guestAvatar.setPose(spotCfg.pose, 0);
    }
    if (guestAvatar && guestTransit) {
      const {route, start, walkMs, spotCfg} = guestTransit;
      const elapsed = Math.max(0, now - start);
      const gp = sampleRoute(route, walkingProgress(elapsed, walkMs), false);
      const arrived = elapsed >= walkMs;
      const sit = spotCfg.pose === 'sit' && arrived;
      const weight = sit ? easeInOut(Math.min(1, (elapsed - walkMs) / SIT_DOWN_MS)) : 0;
      guestVisual = sit ? lerp3(gp.point, spotCfg.pos, weight) : gp.point;
      guestYaw += shortestYaw(guestYaw, arrived ? spotCfg.yaw : gp.yaw) * Math.min(1, dt * 10);
      guestAvatar.group.position.set(guestVisual[0], guestVisual[1], guestVisual[2]);
      guestAvatar.group.rotation.y = guestYaw;
      if (sit) {
        guestTransit.sitFrom ??= guestAvatar.capturePose();
        guestAvatar.setPose('sit', 0, guestTransit.sitFrom, weight);
      } else guestAvatar.setPose('walk', gp.distance / WALK_SPEED);
      if (arrived && (!sit || weight === 1)) {
        guestTransit = null;
        guestVisual = [...spotCfg.pos];
        guestYaw = spotCfg.yaw;
        guestAvatar.group.position.set(spotCfg.pos[0], spotCfg.pos[1], spotCfg.pos[2]);
        guestAvatar.group.rotation.y = spotCfg.yaw;
        guestAvatar.setPose(spotCfg.pose, now / 1000);
      }
    }

    if (character) {
      character.group.visible = projection.visible;
      const phase = phaseFor(now);
      if (effectivePose !== 'stroll') strollFrom = 0;
      if (transit && dist(transit.to, targetPos) > .06) {
        // A fresh snapshot can move the chair or interrupt the activity partway through.
        lastApproach = transit.sitFrom ? transit.path.at(-1)
          : now < transit.start + transit.standUpMs ? transit.path[0] : null;
        lastOnBed = !!lastApproach && (transit.sitFrom ? transit.ontoBed : transit.offBed);
        transit = null;
      }
      if (!projection.visible) {
        visual = null; transit = null; settling = false; lastLocation = null; lastApproach = null; lastOnBed=false;
        character.setPose('idle', 0);
      } else if (still || effectivePose === 'walk' || !visual) {
        transit = null; settling = false; visual = [...targetPos]; yaw = targetYaw; place(visual, yaw);
        character.setPose(
          effectivePose === 'stroll' ? (still ? 'idle' : 'walk') : modelPose(projection, effectivePose),
          phase,
        );
        lastLocation = projection.location;
        lastApproach = projection.approach;
        lastOnBed=onBed;
      } else if (transit) {
        const elapsed = Math.max(0, now - transit.start);
        if (elapsed < transit.standUpMs) {
          const weight = easeInOut(elapsed / transit.standUpMs);
          const transfer=transit.offBed?bedTransfer(transit.path[0],transit.from,1-weight):null;
          visual = transfer?transfer.point:lerp3(transit.from, transit.path[0], weight);
          place(visual, yaw);
          character.setPose('idle', 0, transit.standFrom, transfer?1-transfer.fold:weight);
        } else if (elapsed < transit.standUpMs + transit.walkMs) {
          // Stage 2: Smooth Bezier corner-rounded walk
          const walkElapsed = elapsed - transit.standUpMs;
          const wt = walkingProgress(walkElapsed, transit.walkMs);
          const samplePoint = sampleRoute(transit.route, wt, false);
          visual = samplePoint.point;
          yaw += shortestYaw(yaw, samplePoint.yaw) * Math.min(1, dt * 10);
          place(visual, yaw);
          character.setPose('walk', samplePoint.distance / WALK_SPEED);
        } else if (elapsed < transit.totalMs) {
          // Stage 3: Settle & sit down onto target anchor
          const sitElapsed = elapsed - transit.standUpMs - transit.walkMs;
          const weight = easeInOut(sitElapsed / transit.sitDownMs);
          transit.sitFrom ??= character.capturePose();
          transit.arrivalYaw ??= yaw;
          const transfer=transit.ontoBed?bedTransfer(transit.path.at(-1),transit.to,weight):null;
          const poseWeight=transfer?transfer.fold:weight;
          visual = transfer?transfer.point:lerp3(transit.path.at(-1), transit.to, weight);
          yaw = transit.arrivalYaw + shortestYaw(transit.arrivalYaw, targetYaw) * poseWeight;
          place(visual, yaw);
          character.setPose(modelPose(projection, effectivePose), phase, transit.sitFrom, poseWeight);
        } else {
          visual = [...transit.to];
          yaw=targetYaw;
          place(visual, yaw);
          character.setPose(modelPose(projection, effectivePose), phase);
          transit = null;
          settling = true;
          lastApproach = projection.approach;
          lastOnBed=onBed;
        }
      } else if (effectivePose === 'stroll' && strollFrom) {
        stroll(now, dt);
      } else if (dist(visual, targetPos) > .06) {
        const from = [...visual];
        const walkStart = lastApproach || from, walkEnd = projection.approach || targetPos;
        const path = buildPath(lastLocation, [...walkStart], projection.location, [...walkEnd], navKey, roomGraph);
        if (!path) {
          // If an unusually wide model cannot fit the aisle, hold the safe
          // side until a new destination or furniture layout supplies a route.
          visual=clearBedFloor([...walkStart],layout.obstacle);
          place(visual,yaw);
          character.setPose('idle',0);
          lastApproach=null;lastOnBed=false;settling=false;lastPath=null;
          updateDoorProximity(dt);publish();render();
          return projection;
        }
        lastPath = path;
        const route = buildRoundedSegments(path,.42,layout.obstacle);
        const standUpMs = lastApproach ? STAND_UP_MS : 0;
        const sitDownMs = projection.approach ? SIT_DOWN_MS : 0;
        const walkMs = Math.max(460, route.total / WALK_SPEED * 1000);
        transit = {
          path, route, from, to: [...targetPos],offBed:lastOnBed,ontoBed:onBed,
          start: now,
          standFrom: standUpMs ? character.capturePose() : null,
          standUpMs,
          walkMs,
          sitDownMs,
          totalMs: standUpMs + walkMs + sitDownMs,
        };
        lastApproach = null;
        lastOnBed=false;
        if (!standUpMs) character.setPose('walk', 0);
      } else if (effectivePose === 'stroll') {
        stroll(now, dt);
      } else {
        visual = [...targetPos];
        const delta = shortestYaw(yaw, targetYaw);
        yaw += delta * Math.min(1, dt * 8);
        settling = Math.abs(delta) > .01;
        lastApproach = projection.approach;
        lastOnBed=onBed;
        place(visual, yaw);
        character.setPose(modelPose(projection, effectivePose), phase);
      }
      if (projection.visible) lastLocation = projection.location;
    }
    if (data?.scene?.available) hadHydratedScene = true;
    updateDoorProximity(dt);
    publish();
    render();
    return projection;
  }

  function doorAnimating() {
    return doorAngle > 0.004 && doorAngle < 1.215;
  }

  function needsFrames() {
    return !reduced.matches && !projection?.paused && !data?.isReplay && (
      guestTransit ||
      doorAnimating() ||
      (character && projection?.visible && (transit || settling || (projection.animate && (projection.pose === 'walk' || character.diagnostics().mode !== 'static'))))
    );
  }

  function tick(now) {
    frame = 0;
    if (disposed || !active) return;
    if (now - lastFrame >= 33) {lastFrame = now; sample();}
    if (needsFrames()) frame = requestAnimationFrame(tick);
  }

  function update() {
    cancelAnimationFrame(frame);
    frame = 0;
    if (!active || disposed) return;
    syncGuestAndVisitors();
    sample();
    if (needsFrames()) frame = requestAnimationFrame(tick);
  }

  const motion = () => update();
  reduced.addEventListener('change', motion);

  function visibleBounds() {
    if (!character) return null;
    character.group.updateMatrixWorld(true);
    const box = new THREE.Box3(), part = new THREE.Box3(), parts = [];
    let any = false;
    character.group.traverseVisible(node => {
      if (!node.isMesh) return;
      if (!node.geometry.boundingBox) node.geometry.computeBoundingBox();
      part.copy(node.geometry.boundingBox).applyMatrix4(node.matrixWorld);
      box.union(part);
      parts.push([part.min.toArray(), part.max.toArray()]);
      any = true;
    });
    return any ? {min: box.min.toArray(), max: box.max.toArray(), parts} : null;
  }

  function placement() {
    return {projection, visual_position: visual, guest_position: guestVisual};
  }

  return {
    placement,
    refreshLayout:update,
    async setModel(model, index = 0) {
      const own = ++epoch;
      const next = createAvatar(THREE, model?.format === 'builtin' ? null : model, index, {molang: true});
      next.group.userData.worldAvatar = true;
      try {await next.ready;} catch (error) {next.dispose(); throw error;}
      if (own !== epoch || disposed) {next.dispose(); return false;}
      body=next.bedBody();
      character?.dispose();
      character = next;
      modelId = model?.id || 'builtin';
      textureIndex = index;
      visual = null; transit = null; settling = false; lastLocation = null; lastApproach = null;
      lastOnBed=false;previousBedSlot=null;
      scene.add(next.group);
      signature = '';
      update();
      return true;
    },
    async setGuestModel(model, index = 0) {
      const own = ++guestEpoch;
      guestModelData = model?.format === 'builtin' ? null : (model || null);
      guestModelId = model?.id || 'builtin';
      guestTexIdx = Number(index) || 0;
      const activeVisit = data?.world_space?.active_guest || data?.world_space?.active_visit || null;
      if (!activeVisit || disposed) return true;
      const next = createAvatar(THREE, guestModelData, guestTexIdx, {molang: true});
      next.group.userData.worldAvatar = true;
      next.group.userData.guestAvatar = true;
      try {await next.ready;} catch (error) {next.dispose(); return false;}
      if (own !== guestEpoch || disposed) {next.dispose(); return false;}
      const pos = guestVisual || (PEER_VISIT_SPOTS[activeVisit.spot]?.pos || PEER_VISIT_SPOTS.garden_bench.pos);
      const rot = guestYaw || (PEER_VISIT_SPOTS[activeVisit.spot]?.yaw || 0);
      guestAvatar?.dispose();
      guestAvatar = next;
      if (guestTransit) guestTransit.sitFrom = null;
      guestAvatar.group.position.set(pos[0], pos[1], pos[2]);
      guestAvatar.group.rotation.y = rot;
      const spotCfg = PEER_VISIT_SPOTS[activeVisit.spot] || PEER_VISIT_SPOTS.garden_bench;
      guestAvatar.setPose(guestTransit ? 'walk' : spotCfg.pose, 0);
      scene.add(guestAvatar.group);
      render();
      return true;
    },
    setState(value, chosen) {data = value; selection = chosen || {}; signature = ''; update();},
    setActive(value) {active = value; update();},
    animateIdle(seconds) {
      if (disposed || !active || reduced.matches || projection?.paused || data?.isReplay) return;
      for (const entry of visitorMeshes.values()) entry.mesh.tick(seconds);
      if (guestAvatar && !guestTransit) {
        const activeVisit = data?.world_space?.active_guest || data?.world_space?.active_visit;
        const spotCfg = PEER_VISIT_SPOTS[activeVisit?.spot] || PEER_VISIT_SPOTS.garden_bench;
        guestAvatar.setPose(spotCfg.pose, seconds);
      }
      if (doorAngle > 0.004 && !transit && !guestTransit) {
        updateDoorProximity(0.04);
      }
      if (!character || !projection || !projection.visible || transit || projection.paused) return;
      const effPose = projection.micro?.active ? projection.micro.pose : projection.pose;
      if (effPose === 'stroll') {
        const tgt = projection.micro?.active ? projection.micro.position : projection.position;
        if (strollFrom || dist(visual || tgt, tgt) <= .06) {
          const now = Date.now();
          const dt = lastSample ? Math.min(.1, (now - lastSample) / 1000) : .04;
          lastSample = now;
          stroll(now, dt);
        }
        return;
      }
      if (projection.animate) return;
      if (projection.clock === 'wall' || effPose === 'idle' || effPose === 'rest') {
        character.setPose(modelPose(projection, effPose), seconds);
      }
    },
    onState(callback) {onState = callback || (() => {}); signature = ''; if (projection) publish();},
    diagnostics() {
      return {
        model_id: modelId,
        texture_index: textureIndex,
        ...placement(),
        model: character?.diagnostics() || null,
        animating: !!frame,
        active,
        transit: !!transit,
        door_angle: +doorAngle.toFixed(3),
        yaw,
        path: transit?.path || lastPath,
        bounds: visibleBounds(),
        guest: guestKey || null,
        guest_model_id: guestModelId,
        visitors: visitorMeshes.size,
      };
    },
    project(camera, host) {
      if (!character) return null;
      scene.updateMatrixWorld();
      const box = new THREE.Box3().setFromObject(character.group), point = box.getCenter(new THREE.Vector3()).project(camera);
      return {x: (point.x + 1) * host.clientWidth / 2, y: (1 - point.y) * host.clientHeight / 2};
    },
    projectHead(camera, host) {
      if (!character || !projection?.visible || !visual) return null;
      const headOffset = projection.pose === 'sleep' ? 0.55 : projection.seated ? 1.52 : 1.88;
      const point = new THREE.Vector3(visual[0], visual[1] + headOffset, visual[2]).project(camera);
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y) || point.z < -1 || point.z > 1) return null;
      return {x: (point.x + 1) * host.clientWidth / 2, y: (1 - point.y) * host.clientHeight / 2};
    },
    dispose() {
      disposed = true; ++epoch; ++guestEpoch; cancelAnimationFrame(frame); reduced.removeEventListener('change', motion);
      character?.dispose(); character = null;
      guestAvatar?.dispose(); guestAvatar = null;
      for (const entry of visitorMeshes.values()) entry.mesh.dispose();
      visitorMeshes.clear();
    },
  };
}
