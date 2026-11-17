// The cabin illustration provides a position for each room and action pose.
// Anchors align with the furniture: desk chair, bed edge, dining stool, kitchen
// counter, washstand, potted plant and the garden bench / vegetable patch, and
// dynamically remap when movable room_design furniture is relocated.
const BASE_ANCHORS = {
  room: {
    idle: [1.5, 0.13, 1.5],
    read: [-1.75, 0.13, 0.75],
    write: [0, 0.38, 0.22],
    rest: [-2.13, 0.49, 0.8],
    game: [-2.13, 0.49, 0.8],
    sleep: [-2.78, 0.90, 0.47],
    cook: [-3.96, 0.13, 2.50],
    eat: [2.1, 0.38, 1.85],
    wash: [-4.0, 0.13, -2.7],
    sweep: [-0.55, 0.13, 2.95],
    water: [3.36, 0.13, 2.68],
    threshold: [1.4, 0.13, 3.5],
    hall: [1.4, 0.13, 1.5],
  },
  garden: {
    idle: [-2.8, -0.25, 5.7],
    read: [3.4, 0.12, 5.1],
    write: [3.4, 0.12, 5.1],
    rest: [3.4, 0.12, 5.1],
    eat: [3.4, 0.12, 5.1],
    game: [3.4, 0.12, 5.1],
    water: [4.92, -0.25, 5.55],
    stroll: [0.8, -0.25, 4.9],
    threshold: [0, -0.25, 4.5],
    hall: [0, -0.25, 6.5],
  },
};

const BASE_FACING = {
  room: {
    write: Math.PI, rest: Math.PI / 2, game: Math.PI / 2, eat: Math.PI / 2, cook: -Math.PI / 2,
    wash: -Math.PI / 2, sweep: -Math.PI / 2.6, water: Math.PI / 2,
  },
  garden: {water: -1.02},
};

const DESK_SLOT_ANCHORS = {
  left_wall: {write: [-3.08, 0.38, 0.38], yaw: -Math.PI / 2, attach: 'B'},
  right_wall: {write: [2.82, 0.38, 0.12], yaw: Math.PI / 2, attach: 'C1'},
  back_wall: {write: [1.55, 0.38, -1.62], yaw: Math.PI, attach: 'C2'},
  center: {write: [0.22, 0.38, 1.92], yaw: Math.PI, attach: 'H'},
  bedside: {write: [-1.72, 0.38, -0.28], yaw: Math.PI, attach: 'B'},
};

const BED_SLOT_ANCHORS = {
  right_wall: {rest: [2.68, 0.49, 0.22], sleep: [2.88, 0.90, -0.27], yaw: -Math.PI / 2, sleepYaw: Math.PI, attach: 'C1'},
  back_wall: {rest: [1.38, 0.49, -1.86], sleep: [1.23, 0.90, -1.78], yaw: 0, sleepYaw: -Math.PI / 2, attach: 'C2'},
  center: {rest: [0.96, 0.49, 1.15], sleep: [0.72, 0.90, 1.57], yaw: -Math.PI / 2, sleepYaw: 0, attach: 'H'},
  near_window: {rest: [0.12, 0.49, -1.52], sleep: [-0.27, 0.90, -1.48], yaw: 0, sleepYaw: -Math.PI / 2, attach: 'N'},
};

const BOOKCASE_SLOT_ANCHORS = {
  left_wall: {read: [-3.28, 0.13, 0.48], yaw: -Math.PI / 2, attach: 'B'},
  right_wall: {read: [2.75, 0.13, -0.25], yaw: Math.PI / 2, attach: 'C1'},
  center: {read: [0.68, 0.13, 1.18], yaw: -Math.PI / 2, attach: 'H'},
  near_window: {read: [0.62, 0.13, -2.15], yaw: Math.PI, attach: 'N'},
};

export function resolveFurnitureLayout(data) {
  const roomAnchors = {...BASE_ANCHORS.room};
  const roomFacing = {...BASE_FACING.room};
  const attachOverrides = {};
  const occupiedSlots = {};

  const scene = data?.scene;
  const designs = Array.isArray(scene?.room_designs)
    ? scene.room_designs
    : (scene?.room_design ? [scene.room_design] : []);
  const activeDesign = designs.find(d => d && d.room_id && d.room_id === scene?.room_id) || designs[0] || null;
  const furniture = Array.isArray(activeDesign?.furniture) ? activeDesign.furniture : [];

  for (const item of furniture) {
    if (!item || !item.kind || !item.position) continue;
    occupiedSlots[item.position] = item.kind;
    if (item.kind === 'desk' && item.movable && item.position !== 'near_window' && DESK_SLOT_ANCHORS[item.position]) {
      const cfg = DESK_SLOT_ANCHORS[item.position];
      roomAnchors.write = [...cfg.write];
      roomFacing.write = cfg.yaw;
      attachOverrides.write = cfg.attach;
      attachOverrides.desk_tea = cfg.attach;
    } else if (item.kind === 'bed' && item.movable && item.position !== 'left_wall' && BED_SLOT_ANCHORS[item.position]) {
      const cfg = BED_SLOT_ANCHORS[item.position];
      roomAnchors.rest = [...cfg.rest];
      roomAnchors.game = [...cfg.rest];
      roomAnchors.sleep = [...cfg.sleep];
      roomFacing.rest = cfg.yaw;
      roomFacing.game = cfg.yaw;
      roomFacing.sleep = cfg.sleepYaw ?? 0;
      attachOverrides.rest = cfg.attach;
      attachOverrides.game = cfg.attach;
      attachOverrides.sleep = cfg.attach;
    } else if (item.kind === 'bookcase' && item.movable && item.position !== 'back_wall' && BOOKCASE_SLOT_ANCHORS[item.position]) {
      const cfg = BOOKCASE_SLOT_ANCHORS[item.position];
      roomAnchors.read = [...cfg.read];
      roomFacing.read = cfg.yaw;
      attachOverrides.read = cfg.attach;
      attachOverrides.shelf_browse = cfg.attach;
    }
  }
  if (occupiedSlots.center) {
    roomAnchors.idle = [1.85, 0.13, 2.25];
  }
  return {
    anchors: {room: roomAnchors, garden: BASE_ANCHORS.garden},
    facing: {room: roomFacing, garden: BASE_FACING.garden},
    attachOverrides,
    occupiedSlots,
  };
}

const SEATED = {room: new Set(['write', 'rest', 'game', 'eat']), garden: new Set(['read', 'write', 'rest', 'eat', 'game'])};
const STAGED = {
  room: new Set(['read', 'write', 'rest', 'game', 'eat', 'cook', 'wash', 'sweep', 'water']),
  garden: new Set(['read', 'write', 'rest', 'eat', 'game', 'water', 'stroll']),
};

const stepPoses = new Map([
  ['read', 'read'], ['read_notes', 'read'], ['write_note', 'write'],
  ['project_start', 'write'], ['project_write', 'write'], ['project_revise', 'write'],
  ['computer_work', 'write'], ['refill', 'cook'],
  ['rest', 'rest'],
  ['water_garden', 'water'], ['harvest_garden', 'water'],
  ['prepare_meal', 'cook'], ['brew_tea', 'cook'],
  ['open_mailbox', 'stroll'],
]);

const CODE_POSES = {eating: 'eat', gaming: 'game', chores: 'sweep', reading: 'read', writing: 'write',
  resting: 'rest', sleeping: 'rest', walking: 'stroll'};
const CODE_ALLOWS = {eating: ['eat', 'cook'], chores: ['sweep', 'wash', 'cook', 'water'], resting: ['rest'],
  sleeping: ['rest'], reading: ['read'], writing: ['write'], gaming: ['game'], walking: ['stroll']};
const KEYWORDS = [
  ['wash', /洗漱|刷牙|洗脸|梳洗|梳头|洗澡|沐浴|淋浴|护肤|洗手|梳妆/],
  ['cook', /做饭|烹|煮|炒菜|烤面包|下厨|备餐|煎|泡茶|沏茶|冲咖啡|手冲|烧水|准备.{0,2}[早午晚]?[餐饭]|洗碗|厨房/],
  ['eat', /早餐|午餐|晚餐|早饭|午饭|晚饭|用餐|吃|进食|夜宵|宵夜|甜点|点心|下午茶|喝茶|喝咖啡|喝水/],
  ['game', /游戏|掌机|switch|电玩|打机/i],
  ['write', /写|笔记|日记|记录|创作|稿/],
  ['read', /读|阅读|看书|翻看|书页/],
  ['water', /浇水|浇花|园艺|除草|菜畦|菜园|花圃|修剪|绿植/],
  ['sweep', /打扫|清扫|扫地|拖地|整理|收拾|家务|擦拭|晾|洗衣|叠衣|日常事务/],
  ['stroll', /散步|漫步|遛|走走|踱步|闲逛/],
  ['rest', /休息|小憩|歇|发呆|放空|躺|午睡|打盹|就寝|睡|冥想|伸展|拉伸/],
];
const cleanText = value => typeof value === 'string' ? value.split('；环境参考')[0].trim() : '';
const GENERIC = new Set(['独自写作', '独自玩游戏', '休息', '睡觉', '用餐', '独自阅读', '散步', '处理日常事务', '未知', '行动流程已完成']);
function keywordPose(text) {
  for (const [pose, pattern] of KEYWORDS) if (pattern.test(text)) return pose;
  return null;
}
function lifePose(data, location) {
  const code = typeof data?.activity_code === 'string' ? data.activity_code : 'unknown';
  const activity = cleanText(data?.activity);
  const plan = cleanText(data?.plan_now);
  const byCode = CODE_POSES[code] || null;
  let pose = null, source = null, text = '';
  for (const [candidate, from] of [[activity, 'life'], [plan, 'plan']]) {
    if (from === 'life' && GENERIC.has(candidate)) continue;
    const found = candidate && keywordPose(candidate);
    if (!found) continue;
    if (byCode && !CODE_ALLOWS[code].includes(found)) continue;
    pose = found; source = from; text = candidate; break;
  }
  if (!pose && byCode) {pose = byCode; source = 'life'; text = GENERIC.has(activity) ? plan || activity : activity;}
  if (!pose) return null;
  if (location === 'garden' && pose === 'sweep') pose = 'water';
  if (!STAGED[location].has(pose)) return null;
  return {pose, source, text};
}

const clampProgress = value => Math.max(0, Math.min(1, value));

function sampleProgress(progress, start, end, data, nowMs, paused) {
  const duration = end - start;
  const timed = Number.isFinite(start) && Number.isFinite(end) && duration > 0;
  const hasServerTime = Number.isFinite(data?.server_time);
  const hasReceiveTime = Number.isFinite(data?.received_at_ms);
  const sampled = Number.isFinite(progress) ? clampProgress(progress) :
    timed && hasServerTime && !paused ? clampProgress((data.server_time - start) / duration) : 0;
  if (paused || !timed) return {progress: sampled, expired: false, running: false};

  const serverTime = hasServerTime ? data.server_time : start + duration * sampled;
  const receiveTime = hasReceiveTime ? data.received_at_ms : hasServerTime ? serverTime * 1000 : nowMs;
  const elapsed = Math.max(0, nowMs - receiveTime) / 1000;
  const projected = clampProgress(sampled + elapsed / duration);
  const expired = projected === 1 || serverTime + elapsed >= end;
  return {progress: expired ? 1 : projected, expired, running: !expired && (hasReceiveTime || hasServerTime)};
}

function actionLabel(label, expired) {
  if (!expired) return label;
  return [label, '等待同步'].filter(Boolean).join(' · ');
}

export function projectAvatar(data, selection, nowMs = Date.now()) {
  const scene = data?.scene;
  const actor = data?.actor;
  const paused = scene?.paused === true || actor?.paused === true;
  const action = scene?.action;
  const step = Number.isInteger(action?.index) && action.index >= 0 && Array.isArray(action.steps) &&
    (!action.status || action.status === 'running') ? action.steps[action.index] : null;
  const actionTime = step ? sampleProgress(action.progress, action.step_started_at, action.step_ends_at, data, nowMs, paused) :
    {progress: 0, expired: false, running: false};
  const label = step && typeof action.label === 'string' ? action.label : '';
  const locationLabel = [scene?.place_name || actor?.place_name, scene?.room_name].filter(Boolean).join(' · ');
  const projection = {
    visible: false,
    location: 'unknown',
    pose: 'idle',
    seated: false,
    position: [0, 0, 0],
    rotationY: 0,
    paused,
    label: actionLabel(label, actionTime.expired),
    locationLabel,
    positionBasis: 'unknown',
    progress: actionTime.progress,
    actionKey: step && action.id ? action.id + ':' + action.index : null,
    animate: false,
    source: 'none',
    clock: 'action',
  };

  if (scene?.phase === 'travelling' || (!scene?.phase && actor?.phase === 'travelling')) {
    const journey = actor?.journey;
    const destination = scene?.destination || journey?.destination_name;
    const journeyTime = journey ? sampleProgress(actor.progress, journey.departed_at, journey.arrives_at, data, nowMs, paused) : actionTime;
    return {
      ...projection,
      location: 'away',
      positionBasis: 'journey',
      locationLabel: destination ? '前往 ' + destination : '正在途中',
      label: actionLabel(label, actionTime.expired || journeyTime.expired),
      progress: journeyTime.progress,
    };
  }
  if (scene?.phase !== 'located') return projection;

  const rooms = Array.isArray(scene.rooms) ? scene.rooms : [];
  const placeId = scene.place_id || actor?.place_id;
  const boundRoom = id => id && rooms.find(room => room.id === id);
  const home = boundRoom(selection?.home_room_id);
  const garden = boundRoom(selection?.garden_room_id);
  const roomId = scene.room_id || (step?.kind === 'enter' ? step.target_id : null);
  const matchesRoom = room => placeId && room && room.id === roomId && room.place_id === placeId;
  const location = matchesRoom(home) ? 'room' : matchesRoom(garden) ? 'garden' : null;
  if (!location) {
    const atBoundPlace = placeId && (home?.place_id === placeId || garden?.place_id === placeId);
    return {...projection, location: placeId && (scene.room_id || !atBoundPlace) ? 'away' : 'unknown'};
  }

  const layout = resolveFurnitureLayout(data);
  const entering = step?.kind === 'enter' && step.target_id === roomId;
  const leaving = step?.kind === 'leave' && Boolean(scene.room_id);
  const walking = entering || leaving;
  let pose = walking ? 'walk' : stepPoses.get(step?.kind) || 'idle';
  if (!STAGED[location].has(pose) && pose !== 'walk') pose = 'idle';
  let source = walking || pose !== 'idle' ? 'action' : 'idle';
  let lifeLabel = '';
  const asleep = data?.availability === 'asleep' || action?.activity_code === 'sleeping' || data?.activity_code === 'sleeping';
  if (!walking && asleep) {pose = location === 'room' ? 'sleep' : 'rest'; source = 'sleep';}
  else if (!walking && pose === 'idle') {
    const life = lifePose(step ? {...data, activity: label || data?.activity} : data, location);
    if (life) {pose = life.pose; source = life.source; lifeLabel = life.text;}
    else if (data?.environment?.current?.is_day === false) {pose = 'rest'; source = 'night';}
  }
  const seated = !walking && SEATED[location].has(pose);
  const points = layout.anchors[location];
  const from = entering ? points.threshold : points.hall;
  const to = entering ? points.hall : points.threshold;
  const position = walking ? from.map((value, axis) => value + (to[axis] - value) * actionTime.progress) : [...points[pose]];
  const rotationY = walking ? Math.atan2(to[0] - from[0], to[2] - from[2]) : layout.facing[location][pose] || 0;
  const actionPose = source === 'action';
  return {
    ...projection,
    visible: true,
    location,
    pose,
    seated,
    position,
    rotationY,
    source,
    clock: actionPose || walking ? 'action' : 'wall',
    label: projection.label || lifeLabel.slice(0, 40),
    positionBasis: pose === 'idle' ? 'room_anchor' : 'action_anchor',
    animate: pose === 'sleep' ? !paused : actionPose && pose !== 'rest' && actionTime.running,
  };
}

function stableHash(str) {
  let h = 2166136261;
  const s = String(str || 'cabin');
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function projectAmbientMicro(data, baseProjection, nowMs = Date.now()) {
  const fallback = {
    active: false,
    bucket: 0,
    id: 'none',
    position: baseProjection?.position ? [...baseProjection.position] : [0, 0, 0],
    rotationY: baseProjection?.rotationY || 0,
    pose: baseProjection?.pose || 'idle',
    thought: '',
  };
  if (
    !baseProjection ||
    !baseProjection.visible ||
    baseProjection.paused ||
    baseProjection.pose !== 'idle' ||
    baseProjection.source !== 'idle'
  ) {
    return fallback;
  }
  const hasSrv = Number.isFinite(data?.server_time);
  const recvMs = Number.isFinite(data?.received_at_ms) ? data.received_at_ms : nowMs;
  const serverSec = hasSrv ? data.server_time + Math.max(0, (nowMs - recvMs) / 1000) : nowMs / 1000;
  const bucket = Math.floor(serverSec / 90);
  const seed = stableHash(data?.actor?.character_id || data?.scene?.place_id || 'cabin');
  const effect = data?.environment?.current?.effect || '';
  const rainy = effect === 'rain' || effect === 'storm';
  const layout = resolveFurnitureLayout(data);

  if (baseProjection.location === 'room') {
    const spots = [
      {id: 'center_stand', position: [...layout.anchors.room.idle], rotationY: 0, pose: 'idle', thought: ''},
      {
        id: 'window_gaze',
        position: [0.08, 0.13, -2.55],
        rotationY: Math.PI,
        pose: 'idle',
        thought: rainy ? '听着北窗外的雨声发呆' : '站在北窗边望了望窗外天光',
      },
      {
        id: 'desk_tea',
        position: [layout.anchors.room.write[0] + 0.35, 0.13, layout.anchors.room.write[2] - 0.85],
        rotationY: layout.facing.room.write ?? Math.PI,
        pose: 'idle',
        thought: '在书桌旁端详刚记下的随笔',
      },
      {
        id: 'cat_check',
        position: [-2.15, 0.13, 1.15],
        rotationY: -Math.PI / 2,
        pose: 'idle',
        thought: '俯身看看小猫今天睡得香不香',
      },
      {
        id: 'shelf_browse',
        position: [-2.45, 0.13, -2.55],
        rotationY: Math.PI,
        pose: 'idle',
        thought: '指尖轻轻拂过书架上的旧书脊',
      },
    ];
    const idx = rainy && (bucket + seed) % 3 === 0 ? 1 : (bucket * 7 + seed) % spots.length;
    const chosen = spots[idx];
    return {active: true, bucket, ...chosen, position: [...chosen.position]};
  }

  if (baseProjection.location === 'garden') {
    const spots = [
      {id: 'pond_koi', position: [-2.35, -0.25, 5.75], rotationY: -0.65, pose: 'idle', thought: '在池塘石边数游过的锦鲤'},
      {id: 'flower_scent', position: [4.85, -0.25, 5.35], rotationY: 1.25, pose: 'idle', thought: '俯身查看花圃与菜畦的新芽'},
      {id: 'gate_look', position: [0.55, -0.25, 6.45], rotationY: 0.15, pose: 'idle', thought: '在拱门信箱旁吹了吹微风'},
      {id: 'garden_stroll', position: [0.8, -0.25, 4.9], rotationY: 0, pose: 'stroll', thought: '沿着花园石板路慢步放空'},
    ];
    const chosen = spots[(bucket * 5 + seed) % spots.length];
    return {active: true, bucket, ...chosen, position: [...chosen.position]};
  }
  return fallback;
}

export function projectJourneyRadar(data, nowMs = Date.now()) {
  const scene = data?.scene;
  const actor = data?.actor;
  const paused = scene?.paused === true || actor?.paused === true;
  const travelling = scene?.phase === 'travelling' || (!scene?.phase && actor?.phase === 'travelling');
  if (travelling) {
    const journey = actor?.journey || {};
    const origin = journey.origin_name || scene?.place_name || actor?.place_name || '小屋';
    const destination = scene?.destination || journey.destination_name || '目的地';
    const jt = sampleProgress(actor?.progress, journey.departed_at, journey.arrives_at, data, nowMs, paused);
    const hasSrv = Number.isFinite(data?.server_time);
    const recvMs = Number.isFinite(data?.received_at_ms) ? data.received_at_ms : nowMs;
    const nowSec = hasSrv ? data.server_time + Math.max(0, (nowMs - recvMs) / 1000) : nowMs / 1000;
    const etaSeconds = Number.isFinite(journey.arrives_at) ? Math.max(0, Math.round(journey.arrives_at - nowSec)) : null;
    let etaLabel = '正在途中';
    if (etaSeconds !== null) {
      if (etaSeconds <= 0) etaLabel = '即将抵达';
      else if (etaSeconds < 60) etaLabel = `约 ${etaSeconds} 秒后抵达`;
      else {
        const m = Math.floor(etaSeconds / 60);
        const s = etaSeconds % 60;
        etaLabel = s > 0 ? `约 ${m} 分 ${s} 秒抵达` : `约 ${m} 分钟抵达`;
      }
    }
    return {
      active: true,
      mode: 'travelling',
      origin,
      destination,
      progress: jt.progress,
      etaSeconds,
      etaLabel,
      catGateWait: true,
    };
  }
  const placeName = scene?.place_name || actor?.place_name || '';
  const roomName = scene?.room_name || '';
  if (scene?.phase === 'located' && placeName) {
    return {
      active: true,
      mode: 'external_place',
      origin: '小屋',
      destination: [placeName, roomName].filter(Boolean).join(' · '),
      progress: 1,
      etaSeconds: null,
      etaLabel: '正在外出驻留 · 小猫在拱门等候',
      catGateWait: true,
    };
  }
  return {active: false, mode: 'home', origin: '', destination: '', progress: 0, etaSeconds: null, etaLabel: '', catGateWait: false};
}
