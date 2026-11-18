/* Dynamic room_design layout, keepsakes, companion cues & smooth cat locomotion. */
import {smoothCornerPathPoint, pathLength} from './world-avatar.js';
import {BED_PLACEMENTS, DESK_PLACEMENTS, furniturePoint} from './cabin-layout.js';

export const SLOT_COORDS = {
  left_wall: [-4.25, .14, .4],
  right_wall: [3.95, .14, .1],
  back_wall: [1.65, .14, -2.95],
  center: [.2, .16, 1.15],
  near_window: [.88, 1.52, -3.24],
  bedside: [-1.95, .14, -.95],
  desk_left: [-1.22, 1.46, -.95],
  desk_right: [1.28, 1.46, -1.18],
  bookshelf: [-1.85, 2.54, -3.28],
  entry_rack: [2.25, .14, 3.15],
};

const SHELF_PLACEMENTS = {
  back_wall: [-2.52, 2.48, -3.37, 0],
  left_wall: [-4.68, 2.42, .45, Math.PI / 2],
  right_wall: [3.62, 2.42, -.25, -Math.PI / 2],
  near_window: [1.68, 2.48, -3.37, 0],
  center: [-2.52, 2.48, -3.37, 0],
};

export const CAT_SPOTS = {
  bed_nap: {pos: [-3.55, 1.058, 1.22], ry: -.35, offset: [3.4, 2.5, 4.3], zone: 'room'},
  window_sun: {pos: [.52, 1.44, -3.26], ry: .18, offset: [2.8, 2.1, 4.8], zone: 'room'},
  pond_watch: {pos: [-2.35, -.21, 6.08], ry: -.75, offset: [3.6, 2.6, 4.4], zone: 'garden'},
  garden_patrol: {pos: [1.52, -.21, 5.25], ry: .45, offset: [3.6, 2.6, 4.5], zone: 'garden'},
  gate_wait: {pos: [.62, -.21, 6.68], ry: .08, offset: [3.4, 2.5, 4.4], zone: 'garden'},
};

export const KEEPSAKE_COORDS = {
  windowsill_vase: [.72, 1.50, -3.24],
  shelf_1: [-3.12, 2.54, -3.28],
  shelf_2: [-2.18, 2.54, -3.28],
  shelf_3: [-1.82, 2.54, -3.28],
  desk_1: [-.68, 1.455, -1.72],
  desk_2: [1.36, 1.455, -1.28],
  table_snack: [3.02, .855, 1.62],
  entry_hook: [2.48, .14, 3.02],
};

function clearDynamicChildren(grp) {
  for (const child of [...grp.children]) grp.remove(child);
}

function buildCatWaypoints(fromPos, fromZone, cfg) {
  const target = [...cfg.pos];
  const pts = [[...fromPos]];
  // Step down to floor if starting elevated (bed / windowsill)
  if (fromPos[1] > 0.35) {
    pts.push([fromPos[0] + (fromPos[0] < -2 ? 1.1 : 0), 0.14, Math.max(-2.3, fromPos[2] + (fromPos[2] < -2 ? 0.85 : 0))]);
  }
  if (fromZone !== cfg.zone) {
    if (fromZone === 'room') {
      pts.push([1.12, 0.14, 3.55], [1.05, -0.21, 4.42]);
    } else {
      pts.push([1.05, -0.21, 4.42], [1.12, 0.14, 3.55]);
    }
  }
  // Hop up at destination if elevated
  if (target[1] > 0.35) {
    pts.push([target[0] + (target[0] < -2 ? 1.1 : 0), 0.14, Math.max(-2.3, target[2] + (target[2] < -2 ? 0.85 : 0))]);
  }
  pts.push(target);
  return pts;
}

export function createCabinRoomState({
  world, inspectPresets, portalPresets, proxyMap, inspectGroup, reducedMotion,
  getAtmosphere, applyBaseLights, onCatDoorAngle,
}) {
  let curtainMode = 'open', lampMode = 'warm', lampFactor = 1, curtainDimFactor = 1;
  let roomDesignSig = '', keepsakesSig = '', companionsSig = '';
  let catBaseY = 1.058, catSpotKey = 'bed_nap', catZone = 'room', catHydrated = false, catTransit = null;
  let bedPlacement = BED_PLACEMENTS.left_wall;

  function syncInspectBox(key, x, y, z, yaw = 0) {
    const proxy = proxyMap.get(key);
    if (proxy) {
      proxy.position.set(x, y, z);
      proxy.rotation.y = yaw;
      inspectGroup.updateMatrixWorld(true);
    }
  }

  function applyMainFurnitureTransforms(furniture) {
    const deskItem = furniture.find(f => f?.kind === 'desk' && f.movable && DESK_PLACEMENTS[f.position]);
    const deskSlot = deskItem ? deskItem.position : 'near_window';
    const dCfg = DESK_PLACEMENTS[deskSlot] || DESK_PLACEMENTS.near_window;
    world.desk.position.set(dCfg.desk[0], dCfg.desk[1], dCfg.desk[2]);
    world.desk.rotation.y = dCfg.desk[3];
    world.chair.position.set(dCfg.chair[0], dCfg.chair[1], dCfg.chair[2]);
    world.chair.rotation.y = dCfg.chair[3];
    world.warm.position.set(...furniturePoint(dCfg.desk, 1.13, 1.88, -.17));
    inspectPresets.desk.anchor = furniturePoint(dCfg.desk, .45, 1.38, 0);
    inspectPresets.desk.target = [dCfg.desk[0], 1.35, dCfg.desk[2]];
    portalPresets.memory.anchor = furniturePoint(dCfg.desk, -.5, 1.52, .1);
    portalPresets.memory.target = furniturePoint(dCfg.desk, -.45, 1.48, .1);
    syncInspectBox('desk', dCfg.desk[0], .92, dCfg.desk[2], dCfg.desk[3]);

    const bedItem = furniture.find(f => f?.kind === 'bed' && f.movable && BED_PLACEMENTS[f.position]);
    const bedSlot = bedItem ? bedItem.position : 'left_wall';
    const bCfg = BED_PLACEMENTS[bedSlot] || BED_PLACEMENTS.left_wall;
    world.bed.position.set(bCfg[0], bCfg[1], bCfg[2]);
    world.bed.rotation.y = bCfg[3];
    if (bedPlacement !== bCfg) {
      bedPlacement = bCfg;
      if (catSpotKey === 'bed_nap') placeCatImmediate(catSpotKey);
    }
    inspectPresets.bed.anchor = furniturePoint(bCfg, 0, .96, -.6);
    inspectPresets.bed.target = [bCfg[0], .92, bCfg[2]];
    portalPresets.learning.anchor = furniturePoint(bCfg, .15, 1.16, .43);
    portalPresets.learning.target = furniturePoint(bCfg, .15, 1.14, .43);
    syncInspectBox('bed', bCfg[0], .62, bCfg[2], bCfg[3]);
    world.syncFurnitureShadows();

    const shelfItem = furniture.find(f => f?.kind === 'bookcase' && f.movable && SHELF_PLACEMENTS[f.position]);
    const shelfSlot = shelfItem ? shelfItem.position : 'back_wall';
    const sCfg = SHELF_PLACEMENTS[shelfSlot] || SHELF_PLACEMENTS.back_wall;
    world.shelf.position.set(sCfg[0], sCfg[1], sCfg[2]);
    world.shelf.rotation.y = sCfg[3];
    inspectPresets.shelf.anchor = [sCfg[0], sCfg[1] + .14, sCfg[2]];
    inspectPresets.shelf.target = [sCfg[0], sCfg[1], sCfg[2]];
    syncInspectBox('shelf', sCfg[0], sCfg[1] + .14, sCfg[2], sCfg[3]);
  }

  function applyRoomDesignState(roomDesign = {}, items = [], srvTime = Date.now() / 1000) {
    const rd = Array.isArray(roomDesign) ? (roomDesign[0] || {}) : (roomDesign || {});
    const nextCurtain = ['open', 'half', 'closed'].includes(rd?.curtains) ? rd.curtains : 'open';
    const rawLamp = rd?.lighting || rd?.desk_lamp;
    const nextLamp = ['bright', 'warm', 'dim', 'off'].includes(rawLamp) ? rawLamp : 'warm';
    const noteId = String(rd?.displayed_note_id || '').trim() ||
      (Array.isArray(items) ? (items.find(it => it?.displayed_note_id)?.displayed_note_id || '') : '');
    const itemPlacements = Array.isArray(items)
      ? items.filter(it => !it.carried && (it.arranged_position || it.slot || it.kind === 'umbrella')).map(it => {
          const s = it.arranged_position || it.slot;
          return {
            id: it.id,
            kind: it.kind,
            slot: SLOT_COORDS[s] ? s : (it.kind === 'umbrella' ? 'entry_rack' : ''),
            wet: Number(it.wet_until) > srvTime || !!it.wet,
          };
        }).filter(it => it.slot)
      : [];
    const rawFurniture = Array.isArray(rd?.furniture) ? rd.furniture : [];
    const movedAux = rawFurniture
      .filter(f => f?.movable && SLOT_COORDS[f.position] && !['desk', 'bed', 'bookcase', 'chair'].includes(f.kind))
      .map(f => ({id: f.id, kind: f.kind, slot: f.position}));
    const mainSlots = rawFurniture
      .filter(f => f?.movable && ['desk', 'bed', 'bookcase'].includes(f.kind))
      .map(f => [f.kind, f.position]);

    const sig = JSON.stringify([nextCurtain, nextLamp, noteId, itemPlacements, movedAux, mainSlots]);
    if (sig === roomDesignSig) return;
    roomDesignSig = sig;
    curtainMode = nextCurtain;
    lampMode = nextLamp;

    if (curtainMode === 'closed') {
      world.curtains[0].position.x = -.49; world.curtains[1].position.x = .49;
      world.curtains[0].scale.x = 3.12; world.curtains[1].scale.x = 3.12;
      curtainDimFactor = .76;
      world.motes.visible = false;
    } else if (curtainMode === 'half') {
      world.curtains[0].position.x = -.78; world.curtains[1].position.x = .78;
      world.curtains[0].scale.x = 1.88; world.curtains[1].scale.x = 1.88;
      curtainDimFactor = .90;
    } else {
      world.curtains[0].position.x = -1.06; world.curtains[1].position.x = 1.06;
      world.curtains[0].scale.x = 1; world.curtains[1].scale.x = 1;
      curtainDimFactor = 1;
    }
    getAtmosphere()?.setCurtainFactor?.(curtainMode);

    if (lampMode === 'bright') {lampFactor = 1.38; world.warm.color.set(0xfff0cc);}
    else if (lampMode === 'dim') {lampFactor = .42; world.warm.color.set(0xffb978);}
    else if (lampMode === 'off') {lampFactor = 0; world.warm.color.set(0xffd89b);}
    else {lampFactor = 1; world.warm.color.set(0xffd89b);}

    applyMainFurnitureTransforms(rawFurniture);

    world.displayNoteGroup.visible = Boolean(noteId);
    clearDynamicChildren(world.roomSlotsGroup);
    for (const pl of itemPlacements.slice(0, 6)) {
      const [sx, sy, sz] = SLOT_COORDS[pl.slot];
      const g = world.sub(world.roomSlotsGroup, sx, sy, sz); g.userData.keepSeparate = true;
      if (pl.kind === 'umbrella') {
        world.box(g, .035, .68, .035, 0, .34, 0, 0x58736a, {castShadow: false});
        world.box(g, .11, .46, .11, 0, .28, 0, 0x6d8e84);
        world.box(g, .09, .035, .035, .03, .68, 0, 0xa68968, {castShadow: false});
        if (pl.wet) world.box(g, .32, .008, .28, 0, .005, .02, 0x9fc4bc, {material: world.waterMaterial, castShadow: false});
      } else if (pl.kind === 'water') {
        world.box(g, .16, .18, .16, 0, .09, 0, 0xc49f80);
        world.box(g, .06, .03, .06, 0, .19, 0, 0x8a7358, {castShadow: false});
      } else if (pl.kind === 'book' || pl.kind === 'notebook') {
        world.box(g, .24, .045, .18, 0, .025, 0, pl.kind === 'book' ? 0xb58b89 : 0x6f929b);
      }
    }
    for (const mf of movedAux.slice(0, 4)) {
      if ((mf.kind === 'lamp' && (mf.slot === 'desk_right' || mf.slot === 'desk_left')) || mf.kind === 'chair') continue;
      const [fx, fy, fz] = SLOT_COORDS[mf.slot];
      const g = world.sub(world.roomSlotsGroup, fx + .24, fy, fz); g.userData.keepSeparate = true;
      if (mf.kind === 'lamp') {
        world.box(g, .12, .03, .12, 0, .015, 0, 0x8c6d46);
        world.box(g, .03, .24, .03, 0, .14, 0, 0xb5915f, {castShadow: false});
        world.box(g, .18, .12, .18, 0, .26, 0, 0xf5e5bc);
      } else if (mf.kind === 'chair') {
        world.box(g, .36, .05, .36, 0, .36, 0, 0xb6936c);
        world.box(g, .36, .34, .05, 0, .55, -.15, 0xa4825c);
        for (const [lx, lz] of [[-.14, -.14], [.14, -.14], [-.14, .14], [.14, .14]]) {
          world.box(g, .045, .34, .045, lx, .17, lz, 0x8f6f4d, {castShadow: false});
        }
      } else {
        world.box(g, .42, .28, .28, 0, .14, 0, 0xa88763);
      }
    }
    applyBaseLights();
  }

  function applyKeepsakesState(keepsakes = {}) {
    const vols = Array.isArray(keepsakes?.bookshelf_volumes) ? keepsakes.bookshelf_volumes.slice(0, 12) : [];
    const slots = keepsakes?.slots && typeof keepsakes.slots === 'object' ? keepsakes.slots : {};
    const sig = JSON.stringify([vols.map(v => [v.id, v.spine_color]), Object.entries(slots).map(([k, v]) => [k, v?.id, v?.color])]);
    if (sig === keepsakesSig) return;
    keepsakesSig = sig;
    clearDynamicChildren(world.shelfVolumesGroup);
    vols.forEach((vol, idx) => {
      const h = .34 + (idx % 3) * .06;
      const x = .02 + (idx % 6) * .085 - (idx >= 6 ? .42 : 0);
      const y = idx >= 6 ? .52 : 0;
      const col = vol.spine_color || '#7b9a84';
      const spine = world.box(world.shelfVolumesGroup, .072, h, .22, x, y + h / 2 + .06, .04, col);
      spine.userData.keepSeparate = true;
    });
    clearDynamicChildren(world.keepsakesGroup);
    for (const [slotName, coord] of Object.entries(KEEPSAKE_COORDS)) {
      const item = slots[slotName];
      if (!item) continue;
      const g = world.sub(world.keepsakesGroup, coord[0], coord[1], coord[2]); g.userData.keepSeparate = true;
      const col = item.color || '#d8b27c';
      if (slotName === 'windowsill_vase') {
        world.box(g, .11, .14, .11, 0, .07, 0, 0xe6dfd0);
        world.box(g, .03, .12, .03, 0, .16, 0, 0x70916b, {castShadow: false});
        world.box(g, .09, .08, .09, 0, .22, 0, col, {castShadow: false});
      } else if (slotName === 'table_snack') {
        world.box(g, .24, .02, .24, 0, .01, 0, 0xf4efdc);
        world.box(g, .08, .05, .08, -.04, .04, 0, col);
        world.box(g, .07, .045, .07, .05, .038, .03, 0xdfad8b);
      } else {
        world.box(g, .12, .11, .12, 0, .055, 0, col);
        world.box(g, .08, .03, .08, 0, .12, 0, 0xf2ecd6, {castShadow: false});
      }
    }
  }

  function catDestination(spot) {
    const cfg = CAT_SPOTS[spot] || CAT_SPOTS.bed_nap;
    return cfg === CAT_SPOTS.bed_nap
      ? {...cfg, pos: furniturePoint(bedPlacement, -.30, 1.058, 1.17), ry: cfg.ry + bedPlacement[3]}
      : cfg;
  }

  function placeCatImmediate(spot) {
    const cfg = catDestination(spot);
    catTransit = null;
    catBaseY = cfg.pos[1];
    catZone = cfg.zone;
    world.cat.position.set(cfg.pos[0], cfg.pos[1], cfg.pos[2]);
    world.cat.rotation.y = cfg.ry;
    inspectPresets.cat.anchor = [cfg.pos[0], cfg.pos[1] + .12, cfg.pos[2]];
    inspectPresets.cat.target = [cfg.pos[0], cfg.pos[1] + .06, cfg.pos[2]];
    inspectPresets.cat.offset = [...cfg.offset];
    syncInspectBox('cat', cfg.pos[0], cfg.pos[1] + .12, cfg.pos[2]);
    onCatDoorAngle?.(0);
  }

  function applyCatState(catState = {}, immediate = false) {
    const spot = CAT_SPOTS[catState?.spot] ? catState.spot : 'bed_nap';
    if (!catHydrated || immediate || reducedMotion.matches) {
      catSpotKey = spot;
      catHydrated = true;
      placeCatImmediate(spot);
      return;
    }
    if (spot === catSpotKey) return;
    const fromPos = [world.cat.position.x, world.cat.position.y, world.cat.position.z];
    const waypoints = buildCatWaypoints(fromPos, catZone, catDestination(spot));
    const len = pathLength(waypoints);
    catSpotKey = spot;
    if (len < 0.25) {
      placeCatImmediate(spot);
      return;
    }
    catTransit = {
      path: waypoints,
      targetSpot: spot,
      startMs: performance.now(),
      durationMs: Math.max(800, Math.min(4800, (len / 1.35) * 1000)),
    };
  }

  function tickCat(nowMs, t, m, pulseAmt, pulseKey) {
    const isCatPulse = pulseKey === 'cat' ? pulseAmt : 0;
    if (catTransit) {
      const prog = Math.min(1, (nowMs - catTransit.startMs) / catTransit.durationMs);
      const prevSample = smoothCornerPathPoint(catTransit.path, Math.max(0, prog - 0.02), true, 0.35);
      const curSample = smoothCornerPathPoint(catTransit.path, prog, true, 0.35);
      const dx = curSample.point[0] - prevSample.point[0];
      const dz = curSample.point[2] - prevSample.point[2];
      const strideBob = Math.abs(Math.sin(t * 14)) * 0.045;
      catBaseY = curSample.point[1];
      world.cat.position.set(curSample.point[0], catBaseY + strideBob, curSample.point[2]);
      if (Math.hypot(dx, dz) > 1e-4) {
        world.cat.rotation.y = Math.atan2(dz, -dx);
      }
      world.catBody.scale.y = .2 * (1 + Math.sin(t * 14) * .08);
      world.tailA.rotation.y = .3 + Math.sin(t * 9) * .34;
      world.tailB.rotation.y = 1.2 + Math.sin(t * 9 + .7) * .42;
      inspectPresets.cat.anchor = [curSample.point[0], catBaseY + .12, curSample.point[2]];
      inspectPresets.cat.target = [curSample.point[0], catBaseY + .06, curSample.point[2]];
      syncInspectBox('cat', curSample.point[0], catBaseY + .12, curSample.point[2]);
      const nearDoor = Math.hypot(curSample.point[0] - 1.12, curSample.point[2] - 3.74) < 1.15;
      onCatDoorAngle?.(nearDoor ? 0.62 : 0);
      if (prog >= 1) {
        placeCatImmediate(catTransit.targetSpot);
      }
      return true;
    }
    world.cat.position.y = catBaseY + isCatPulse * .085;
    world.catBody.scale.y = .2 * (1 + Math.sin(t * 2.2) * .05 * m + isCatPulse * .16);
    world.tailA.rotation.y = .3 + Math.sin(t * 1.6) * .18 * m + (isCatPulse ? Math.sin(t * 15) * isCatPulse * .32 : 0);
    world.tailB.rotation.y = 1.2 + Math.sin(t * 1.6 + .6) * .22 * m + (isCatPulse ? Math.sin(t * 15 + .8) * isCatPulse * .38 : 0);
    world.earL.rotation.z = .35 + Math.max(0, Math.sin(t * .9)) * .14 * m + isCatPulse * .26;
    world.earR.rotation.z = -.35 - isCatPulse * .26;
    return false;
  }

  function applyCompanionCues(companions = {}) {
    const grid = companions?.visual?.frame_pixel_grid;
    const memGlow = Boolean(companions?.memory?.bookmark_glow || (Number(companions?.memory?.conflicts) > 0));
    const learnGlow = Boolean((Number(companions?.learning?.applied) > 0) || (Number(companions?.learning?.pending) > 0));
    const chatGlow = Boolean(companions?.chat?.glow || (Number(companions?.chat?.pending_outreach) > 0));
    const sig = JSON.stringify([grid, memGlow, learnGlow, chatGlow]);
    if (sig === companionsSig) return;
    companionsSig = sig;
    world.memoryBookmark.visible = memGlow;
    world.learningMarker.visible = learnGlow;
    world.setChatCompanionGlow(chatGlow);
    if (Array.isArray(grid) && grid.length > 0 && Array.isArray(grid[0])) {
      const ctx = world.picturePixelCanvas.getContext('2d');
      const rows = Math.min(12, grid.length);
      const cols = Math.min(16, grid[0].length || 16);
      ctx.fillStyle = '#f0e9cf'; ctx.fillRect(0, 0, 16, 12);
      for (let y = 0; y < rows; y++) {
        const row = grid[y] || [];
        for (let x = 0; x < cols; x++) {
          ctx.fillStyle = row[x] || '#f0e9cf';
          ctx.fillRect(x, y, 1, 1);
        }
      }
      world.picturePixelTex.needsUpdate = true;
      world.picturePixelMesh.visible = true;
      world.pictureDefaultArt.visible = false;
    } else {
      world.picturePixelMesh.visible = false;
      world.pictureDefaultArt.visible = true;
    }
  }

  return {
    applyRoomDesignState,
    applyKeepsakesState,
    applyCatState,
    tickCat,
    applyCompanionCues,
    get curtainMode() {return curtainMode;},
    get lampMode() {return lampMode;},
    get lampFactor() {return lampFactor;},
    get curtainDimFactor() {return curtainDimFactor;},
    get catSpotKey() {return catSpotKey;},
    get catBaseY() {return catBaseY;},
    get catWalking() {return Boolean(catTransit);},
  };
}
