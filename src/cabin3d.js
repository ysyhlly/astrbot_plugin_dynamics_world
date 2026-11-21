/* True, demand-rendered WebGL room orchestrator. Modularized in v0.21.0. */
import {
  ACESFilmicToneMapping, AdditiveBlending, Box3, BoxGeometry, BufferGeometry, CanvasTexture, Color,
  DirectionalLight, DynamicDrawUsage, Euler, Float32BufferAttribute, Fog, Group, HalfFloatType,
  HemisphereLight, InstancedMesh, MathUtils, Matrix4, Mesh, MeshBasicMaterial, MeshStandardMaterial,
  NearestFilter, PCFShadowMap, PerspectiveCamera, PlaneGeometry, PointLight, Quaternion, Raycaster,
  RepeatWrapping, SRGBColorSpace, Scene, Spherical, TextureLoader, Vector2, Vector3, WebGLRenderTarget,
  WebGLRenderer,
} from 'three';
import {EffectComposer} from 'three/examples/jsm/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/examples/jsm/postprocessing/RenderPass.js';
import {UnrealBloomPass} from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import {OutputPass} from 'three/examples/jsm/postprocessing/OutputPass.js';
import {createWorldAvatar} from '../pages/world/world-avatar.js';
import {createPixelPass} from '../pages/world/cabin-pixel-pass.js';
import {installCabinFog} from '../pages/world/cabin-shelter.js';
import {cabinPlan} from '../pages/world/cabin-plans.js';
import {createCabinAtmosphere} from '../pages/world/cabin-atmosphere.js';
import {buildCabinWorld} from '../pages/world/cabin-furniture.js';
import {createCabinRoomState} from '../pages/world/cabin-room-state.js';
import {createCabinCameraController} from '../pages/world/cabin-camera.js';

const THREE = {
  ACESFilmicToneMapping, AdditiveBlending, Box3, BoxGeometry, BufferGeometry, CanvasTexture, Color,
  DirectionalLight, DynamicDrawUsage, Euler, Float32BufferAttribute, Fog, Group, HalfFloatType,
  HemisphereLight, InstancedMesh, MathUtils, Matrix4, Mesh, MeshBasicMaterial, MeshStandardMaterial,
  NearestFilter, PCFShadowMap, PerspectiveCamera, PlaneGeometry, PointLight, Quaternion, Raycaster,
  RepeatWrapping, SRGBColorSpace, Scene, Spherical, TextureLoader, Vector2, Vector3, WebGLRenderTarget,
  WebGLRenderer,
};

export function createCabin3D(host, {onSelect, onHover = () => {}, onInspect = null, onInspectHover = () => {}}) {
  const coarsePointer = matchMedia('(pointer:coarse)').matches, dprCap = coarsePointer ? 1.25 : 1.5;
  const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, dprCap));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .92;
  renderer.info.autoReset = false;

  const canvas = renderer.domElement;
  canvas.className = 'cabin-webgl';
  canvas.tabIndex = 0;
  canvas.setAttribute('role', 'img');
  host.append(canvas);
  host.dataset.renderer = 'webgl';

  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(36, 1, .1, 80);
  camera.position.set(17, 16.3, 24.35);
  scene.fog = new THREE.Fog(0xe9eee0, 30, 72);

  let active = true, disposed = false, hovered = null, hoveredInspect = null, night = false, onScreen = true, shadowAt = 0;
  const quality = {mode: 'auto', level: 0, slow: 0, post: true};
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

  const hemi = new THREE.HemisphereLight(0xf3f5df, 0x76876e, 1.95); scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffe3b0, 3.35); sun.position.set(0, 11.2, 5.6); sun.castShadow = true;
  const shadowSize = innerWidth < 700 ? 512 : 1024;
  sun.shadow.mapSize.set(shadowSize, shadowSize);
  Object.assign(sun.shadow.camera, {left: -12, right: 12, top: 12, bottom: -12, near: .5, far: 42});
  sun.shadow.bias = -.0005; sun.shadow.normalBias = .035; sun.shadow.autoUpdate = false; sun.shadow.needsUpdate = true;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xa9c4d8, .68); fill.position.set(6, 5, -4); scene.add(fill);

  // Click spark particle pool
  const PARTICLES = 160;
  const particleGeo = new THREE.BoxGeometry(1, 1, 1);
  const particleMat = new THREE.MeshBasicMaterial({transparent: true, toneMapped: false, blending: THREE.AdditiveBlending, depthWrite: false});
  const particleMesh = new THREE.InstancedMesh(particleGeo, particleMat, PARTICLES);
  particleMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  particleMesh.frustumCulled = false; particleMesh.castShadow = false; particleMesh.receiveShadow = false;
  const pColor = new THREE.Color(), zeroMatrix = new THREE.Matrix4().makeScale(0, 0, 0);
  for (let i = 0; i < PARTICLES; i++) {particleMesh.setMatrixAt(i, zeroMatrix); particleMesh.setColorAt(i, pColor.set(0xffffff));}
  scene.add(particleMesh);

  const world = buildCabinWorld(THREE, scene, {
    getHovered: () => hovered,
    getNight: () => night,
    particleMesh,
    invalidate:render,
  });

  const detachShelterFog=installCabinFog(scene);

  // Hinged front door angle combiner (character + guest + cat)
  let avatarDoorAngle = 0, catDoorAngle = 0;
  function syncFrontDoor() {
    world.frontDoorPivot.rotation.y = -Math.max(avatarDoorAngle, catDoorAngle);
  }

  // Off-scene raycast hit proxies (including actor / guest & gate signpost!)
  const inspectPresets = {
    actor: {boxes: [[1.5, 1.0, 1.5, .86, 1.85, .86]], anchor: [1.5, 1.35, 1.5], target: [1.5, 1.15, 1.5], offset: [3.4, 2.4, 4.4]},
    gate: {boxes: [[-1.86, .55, 6.92, .94, 1.48, .58]], anchor: [-1.86, .88, 6.92], target: [-1.55, .78, 6.72], offset: [3.6, 2.5, 4.6]},
    cat: {boxes: [[-3.55, 1.18, 1.22, .66, .34, .48]], anchor: [-3.55, 1.18, 1.22], target: [-3.45, 1.12, 1.15], offset: [3.4, 2.5, 4.3]},
    desk: {boxes: [[0, .92, -1.45, 3.2, 1.35, 1.32]], anchor: [.72, 1.38, -1.42], target: [-.1, 1.35, -1.38], offset: [3.5, 2.8, 5.1]},
    shelf: {boxes: [[-2.52, 2.62, -3.35, 1.68, .62, .52]], anchor: [-2.52, 2.62, -3.35], target: [-2.45, 2.45, -3.25], offset: [2.8, 1.8, 4.6]},
    bed: {boxes: [[-3.25, .62, -.05, 2.36, .96, 3.15]], anchor: [-3.25, .96, -.95], target: [-3.15, .92, .05], offset: [4.6, 3.5, 5.4]},
    kitchen: {boxes: [[-4.52, .98, 2.75, .88, 1.7, 1.62], [2.82, .56, 1.84, 1.45, .88, 1.12]], anchor: [-4.52, 1.08, 2.75], target: [-4.2, 1.05, 2.68], offset: [4.6, 3.4, 4.9]},
    window: {boxes: [[.05, 2.24, -3.42, 2.28, 1.68, .42]], anchor: [.05, 2.24, -3.42], target: [.05, 2.15, -3.25], offset: [3.2, 2.2, 5.3]},
    clothesline: {boxes: [[-6.65, .82, 5.7, .55, 1.28, 1.82]], anchor: [-6.65, .88, 5.7], target: [-6.55, .85, 5.7], offset: [4.8, 3.3, 5.4]},
    mailbox: {boxes: [[1.88, .78, 6.96, .58, 1.15, .58]], anchor: [1.88, .88, 6.96], target: [1.65, .85, 6.82], offset: [3.2, 2.3, 4.4]},
    garden_bed: {boxes: [[3.5, .12, 6.35, 2.4, .55, 1.6], [6.48, .25, .83, 2.6, .75, 6.4]], anchor: [3.5, .18, 6.35], target: [3.5, .24, 6.2], offset: [1.75, 4.6, 4.0]},
  };
  const portalPresets = {
    memory: {anchor: [-.6, 1.52, -1.36], target: [-.55, 1.48, -1.32], offset: [2.6, 2.2, 3.8]},
    visual: {anchor: [3.52, 1.65, -1.85], target: [3.35, 1.55, -2.15], offset: [2.8, 2.1, 5.2]},
    learning: {anchor: [-3.1, 1.16, .48], target: [-3.05, 1.14, .48], offset: [3.1, 2.3, 3.9]},
    horizons: {anchor: [-2.52, 2.62, -3.35], target: [-2.45, 2.45, -3.25], offset: [2.8, 1.8, 4.6]},
    chat: {anchor: [3.33, 1.28, 1.75], target: [3.28, 1.22, 1.75], offset: [2.5, 2.0, 3.6]},
  };

  const inspectGroup = new THREE.Group();
  const proxyMap = new Map();
  for (const [w, h, d, x, y, z] of [[10.2, 3.5, .2, 0, 1.85, -3.72], [.2, 3.5, 7.45, -5, 1.85, 0]]) {
    const wallProxy = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), world.occluderMaterial);
    wallProxy.position.set(x, y, z); wallProxy.userData.inspectKey = null; inspectGroup.add(wallProxy);
  }
  for (const [key, cfg] of Object.entries(inspectPresets)) {
    for (const [index,[x, y, z, w, h, d]] of cfg.boxes.entries()) {
      const proxy = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), world.occluderMaterial);
      proxy.position.set(x, y, z); proxy.userData.inspectKey = key; inspectGroup.add(proxy);
      if (!proxyMap.has(key)) proxyMap.set(key, proxy);
      else proxyMap.set(key+':'+index,proxy);
    }
  }
  // Secondary proxy for visiting peer guest so clicking her also opens the actor status card
  const guestProxy = new THREE.Mesh(new THREE.BoxGeometry(.84, 1.78, .84), world.occluderMaterial);
  guestProxy.position.set(0, -50, 0); guestProxy.userData.inspectKey = 'actor';
  inspectGroup.add(guestProxy);
  inspectGroup.updateMatrixWorld(true);

  const lightBase = {hemi: 1.95, sun: 3.35, warm: 3.1, fairy: .3, bulb: .15, star: 0};
  let particleScale = .2, glowFactor = .2, motionFactor = 2, atmosphere = null, effects = true;
  let composer = null, bloom = null, outputPass = null, bloomActive = false, bloomBase = .12, composerFailed = false;
  const pixelPass = createPixelPass(renderer, camera, {pixelSize: 2});
  const frameListeners = new Set();
  let batchDepth = 0, batchDirty = false;
  let inspectPulse = {key: null, start: 0, until: 0};
  const pulseStrength = (now = performance.now()) => now < inspectPulse.until ? Math.sin(Math.min(1, (now - inspectPulse.start) / 650) * Math.PI) : 0;

  function ensureComposer() {
    if (composer || composerFailed) return composer;
    try {
      const samples = Math.min(4, renderer.capabilities.maxSamples || 0);
      const target = new THREE.WebGLRenderTarget(1, 1, {type: THREE.HalfFloatType, samples: samples > 1 ? samples : 0});
      composer = new EffectComposer(renderer, target);
      composer.addPass(new RenderPass(scene, camera));
      bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), bloomBase * glowFactor, .5, .9);
      composer.addPass(bloom);
      outputPass = new OutputPass();
      composer.addPass(outputPass);
      const width = host.clientWidth, height = host.clientHeight;
      if (width > 0 && height > 0) {
        const ratio = renderer.getPixelRatio();
        composer.setPixelRatio(ratio); composer.setSize(width, height);
        bloom.setSize(Math.max(1, Math.round(width * ratio / 2)), Math.max(1, Math.round(height * ratio / 2)));
      }
    } catch {composerFailed = true; composer = null; bloom = null; outputPass = null;}
    return composer;
  }

  function syncActorProxy() {
    const diag = avatar.placement();
    const actorProxy = proxyMap.get('actor');
    const vp = diag?.visual_position;
    if (actorProxy) {
      if (vp && diag?.projection?.visible) {
        const hCenter = diag.projection.pose === 'sleep' ? vp[1] + .35 : vp[1] + .92;
        actorProxy.position.set(vp[0], hCenter, vp[2]);
        inspectPresets.actor.anchor = [vp[0], hCenter + .25, vp[2]];
        inspectPresets.actor.target = [vp[0], hCenter + .05, vp[2]];
        if (diag.projection.pose === 'write' && diag.projection.location === 'room') {
          // Look across the chair from the open aisle, clear of the desk lamp.
          const facingX = Math.sin(diag.projection.rotationY);
          inspectPresets.actor.offset = Math.abs(facingX) > .5
            ? [1.15 * facingX, 2.1, 4.4] : [4.2, 2.1, 2.45];
        } else {
          inspectPresets.actor.offset = [3.4, 2.4, 4.4];
        }
      } else {
        actorProxy.position.set(0, -50, 0);
      }
    }
    const gp = diag?.guest_position;
    if (gp) guestProxy.position.set(gp[0], gp[1] + .88, gp[2]);
    else guestProxy.position.set(0, -50, 0);
    inspectGroup.updateMatrixWorld(true);
  }

  function notifyFrame() {for (const fn of frameListeners) {try {fn();} catch {}}}

  function render() {
    if (disposed || !active || !onScreen) return;
    if (batchDepth > 0) {batchDirty = true; return;}
    syncActorProxy();
    if (world.sleepDetails.visible) world.zzz.position.y = 1.5 + Math.sin(performance.now() / 900) * .05;
    renderer.info.reset();
    if (pixelPass.enabled && pixelPass.render(scene, host.clientWidth, host.clientHeight, atmosphere ? atmosphere.state.nightFactor : (night ? 1 : 0))) {
      notifyFrame();
      return;
    }
    if (bloomActive && quality.post && ensureComposer()) composer.render();
    else renderer.render(scene, camera);
    notifyFrame();
  }

  function batch(fn) {
    batchDepth++;
    try {fn();} finally {batchDepth--; if (batchDepth === 0 && batchDirty) {batchDirty = false; render();}}
  }

  const avatar = createWorldAvatar(THREE, scene, render, {
    onDoorSwing(angle) {avatarDoorAngle = angle; syncFrontDoor();},
    getBedSlot:()=>world.bed.userData.slot || 'left_wall',
    getPlan:()=>cabinPlan(world.styles.id),
  });

  const cam = createCabinCameraController({
    THREE, camera, canvas, host, reducedMotion, inspectPresets, portalPresets, render,
    getStyle:()=>world.styles.id,
    isActive: () => active,
    isDisposed: () => disposed,
  });

  function applyBaseLights() {
    const cDim = roomState ? roomState.curtainDimFactor : 1;
    const lFac = roomState ? roomState.lampFactor : 1;
    hemi.intensity = lightBase.hemi * cDim;
    sun.intensity = lightBase.sun * cDim;
    world.warm.intensity = lightBase.warm * lFac;
    world.readingLight.intensity = Math.max(0, lightBase.fairy - .3) * 2.15;
    world.fairyBulbMaterial.emissiveIntensity = lightBase.fairy;
    world.bulbMaterial.emissiveIntensity = lFac === 0 ? 0 : lightBase.bulb * Math.max(.5, lFac);
    world.starMaterial.emissiveIntensity = lightBase.star;
    if (roomState?.curtainMode === 'closed') world.motes.visible = false;
  }

  const roomState = createCabinRoomState({
    world, inspectPresets, portalPresets, proxyMap, inspectGroup, reducedMotion,
    getAtmosphere: () => atmosphere,
    applyBaseLights,
    onCatDoorAngle(angle) {catDoorAngle = angle; syncFrontDoor();},
  });

  function applyRoomDesign(rd,items,srvTime) {
    const before=world.bed.userData.slot || 'left_wall';
    roomState.applyRoomDesignState(rd,items,srvTime);
    if(world.bed.userData.slot!==before)avatar.refreshLayout();
  }

  function setCabinStyle(style) {
    const plan=cabinPlan(style);
    if(!world.styles.set(plan.id))return plan.id;
    host.dataset.cabinStyle=plan.id;
    batch(()=>{
      roomState.setCabinPlan(plan);
      avatar.refreshLayout();
      atmosphere?.refreshLighting();
      sun.shadow.needsUpdate=true;
      if(cam.inspectedKey)cam.focusTarget(cam.inspectedKey,true);
      render();
    });
    return plan.id;
  }
  host.dataset.cabinStyle='cottage';
  atmosphere = createCabinAtmosphere({
    scene, hemi, sun, fill, warm: world.warm, skyMaterial: world.skyMaterial,
    daySky: world.daySky, nightSky: world.nightSky, sunDisk: world.sunDisk, motes: world.motes,
    screenMaterial: world.screenMaterial, windowGroup: world.windowGroup, windowSunPatch: world.windowSunPatch,
    garden: world.garden, lightBase,
    onBloomUpdate(activeFlag, base) {
      night = atmosphere ? atmosphere.state.night : !!activeFlag;
      bloomActive = !!activeFlag; bloomBase = base;
      if (bloom) bloom.strength = bloomBase * glowFactor;
      applyBaseLights();
    },
  });

  function varyLights(t) {
    const m = motionFactor, p = pulseStrength(), pk = p > 0 ? inspectPulse.key : null;
    const deskBoost = pk === 'desk' ? p * 1.6 : pk === 'bed' ? p * .7 : 0;
    const cDim = roomState.curtainDimFactor, lFac = roomState.lampFactor;
    world.warm.intensity = (lightBase.warm * lFac) * (1 + m * (.05 * Math.sin(t * 2.3) + .025 * Math.sin(t * 5.7 + 1))) + deskBoost;
    world.bulbMaterial.emissiveIntensity = lFac === 0 ? 0 : (lightBase.bulb * Math.max(.5, lFac)) * (1 + m * .08 * Math.sin(t * 2.3)) + (pk === 'desk' ? p * .55 : 0);
    sun.intensity = (lightBase.sun * cDim) * (1 + m * .035 * Math.sin(t * .35));
    hemi.intensity = (lightBase.hemi * cDim) * (1 + m * .02 * Math.sin(t * .22 + 2));
    world.fairyBulbMaterial.emissiveIntensity = lightBase.fairy * (1 - m * .18 * (.5 - .5 * Math.sin(t * 2.1)));
    if (lightBase.star > 0) world.starMaterial.emissiveIntensity = lightBase.star * (1 - m * .2 * (.5 - .5 * Math.sin(t * 3.1)));
    if (world.memoryBookmark.visible) world.memoryBookmarkMat.emissiveIntensity = .45 + .25 * Math.sin(t * 2.8);
    if (world.learningMarker.visible) world.learningMarkerMat.emissiveIntensity = .35 + .2 * Math.sin(t * 2.2 + 1);
    world.garden.tick(t, night, m);
  }

  function idleTick(nowMs, t) {
    const m = motionFactor, p = pulseStrength(nowMs), pk = p > 0 ? inspectPulse.key : null;
    const winBoost = pk === 'window' ? Math.sin(t * 10) * p * .11 : 0;
    const swayScale = roomState.curtainMode === 'closed' ? .35 : 1;
    world.curtains[0].rotation.z = Math.sin(t * 1.2) * .025 * m * swayScale - winBoost;
    world.curtains[1].rotation.z = Math.sin(t * 1.2 + 1.3) * .025 * m * swayScale + winBoost;
    const sa = (t * .6) % 1, sb = (t * .6 + .5) % 1;
    world.steamA.position.y = .33 + sa * .26 + (pk === 'kitchen' ? p * .12 : 0); world.steamA.rotation.z = .15 + Math.sin(t * 2) * .12;
    world.steamB.position.y = .36 + sb * .26 + (pk === 'kitchen' ? p * .12 : 0); world.steamB.rotation.z = -.15 + Math.sin(t * 2 + 1) * .12;
    world.steamMaterial.opacity = .3 * (.6 + .4 * Math.sin(t * 3)) + (pk === 'kitchen' || pk === 'desk' ? p * .34 : 0);
    roomState.tickCat(nowMs, t, m, p, pk);
    world.plant.rotation.z = Math.sin(t * 1.05) * .012 * m;
    if (world.cookFx.visible) {
      world.potSteam.forEach((puff, i) => {
        const k = (t * .7 + i / 3) % 1;
        puff.position.y = 1.24 + k * .38;
        puff.position.x = .12 + (i - 1) * .06 + Math.sin(t * 2 + i) * .03;
      });
      world.burnerMaterial.emissiveIntensity = 1.6 * (1 + .15 * Math.sin(t * 7));
    }
    if (world.washFx.visible) world.stream.scale.x = 1 + .25 * Math.sin(t * 20);
    const chat = world.props.get('chat');
    if (chat && !chat.progress && hovered !== 'chat') {
      const chatGlow = world.getChatCompanionGlow();
      const baseEm = chatGlow ? .22 : (night ? .12 : .03);
      world.screenMaterial.emissiveIntensity = baseEm * (1 + .35 * Math.sin(t * 2.1) * m);
      world.bubble.visible = chatGlow;
      if (chatGlow) world.bubble.position.y = Math.sin(t * 2.4) * .018;
    }
    world.garden.idle(t, night, m + (pk === 'clothesline' ? p * 3.2 : 0));
  }

  // Click spark particles
  const particles = Array.from({length: PARTICLES}, () => ({life: 0, born: 0, max: 1, x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, size: .06}));
  const sparkPalette = [0xfff2cc, 0xffd89b, 0xa2d5ae, 0xeef0cc, 0x8fd0b0, 0xf2d8a0];
  const pMatrix = new THREE.Matrix4();
  let aliveParticles = 0, ambientFrame = 0, lastAmbient = 0;

  function spawnParticles(point) {
    if (!point) return;
    let spawned = 0; const now = performance.now();
    for (let i = 0; i < PARTICLES && spawned < Math.round(40 * particleScale); i++) {
      const p = particles[i]; if (p.life > 0) continue;
      const a = Math.random() * Math.PI * 2, elev = Math.random() * Math.PI * .55, sp = 1.6 + Math.random() * 2.4;
      p.x = point.x + (Math.random() - .5) * .12; p.y = point.y + (Math.random() - .5) * .12; p.z = point.z + (Math.random() - .5) * .12;
      p.vx = Math.cos(a) * Math.cos(elev) * sp; p.vy = Math.sin(elev) * sp + 1.7; p.vz = Math.sin(a) * Math.cos(elev) * sp;
      p.max = .75 + Math.random() * .6; p.life = p.max; p.born = now; p.size = .1 + Math.random() * .16;
      pColor.set(sparkPalette[(Math.random() * sparkPalette.length) | 0]);
      pMatrix.makeScale(p.size, p.size, p.size); pMatrix.setPosition(p.x, p.y, p.z);
      particleMesh.setMatrixAt(i, pMatrix); particleMesh.setColorAt(i, pColor); spawned++;
    }
    if (!spawned) return;
    aliveParticles += spawned;
    particleMesh.instanceMatrix.needsUpdate = true;
    if (particleMesh.instanceColor) particleMesh.instanceColor.needsUpdate = true;
    lastAmbient = 0;
    kickAmbient();
  }

  function updateParticles(now, dt) {
    aliveParticles = 0;
    for (let i = 0; i < PARTICLES; i++) {
      const p = particles[i]; if (p.life <= 0) continue;
      const age = (now - p.born) / 1000;
      if (age >= p.max) {particleMesh.setMatrixAt(i, zeroMatrix); p.life = 0; continue;}
      p.vy -= 3.6 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      const k = 1 - age / p.max, s = p.size * (.4 + .6 * k);
      pMatrix.makeScale(s, s, s); pMatrix.setPosition(p.x, p.y, p.z); particleMesh.setMatrixAt(i, pMatrix);
      aliveParticles++;
    }
    particleMesh.instanceMatrix.needsUpdate = true;
  }

  function ambientInterval() {
    return (aliveParticles > 0 || performance.now() < inspectPulse.until || cam.cozyCam || roomState.catWalking)
      ? 24
      : (effects || atmosphere?.state.precipitating) && !reducedMotion.matches ? 40 : 120;
  }

  function adaptQuality(late) {
    if (quality.mode !== 'auto' || quality.level >= 2) return;
    if (late > 16) quality.slow++; else quality.slow = Math.max(0, quality.slow - 1);
    if (quality.slow > 18) {quality.slow = 0; quality.level++; applyQuality();}
  }

  function applyQuality() {
    quality.post = quality.level < 2;
    const cap = quality.level === 0 ? dprCap : quality.level === 1 ? 1.25 : 1;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, cap));
    resize(); render();
  }

  function setQualityMode(mode) {
    quality.mode = ['auto', 'high', 'low'].includes(mode) ? mode : 'auto';
    quality.slow = 0;
    if (quality.mode === 'high') {quality.level = 0; quality.post = true; renderer.setPixelRatio(Math.min(devicePixelRatio || 1, dprCap));}
    else if (quality.mode === 'low') {quality.level = 2; quality.post = false; renderer.setPixelRatio(1);}
    resize(); render();
  }

  function ambientTick(now) {
    ambientFrame = 0;
    if (disposed || !active || !onScreen || document.hidden) return;
    const interval = ambientInterval();
    if (now - lastAmbient >= interval) {
      const dt = Math.min(.06, (now - lastAmbient) / 1000 || 0), late = now - lastAmbient - interval;
      lastAmbient = now;
      if (now >= inspectPulse.until && !roomState.catWalking && world.cat.position.y !== roomState.catBaseY) {
        world.cat.position.y = roomState.catBaseY;
        world.earR.rotation.z = -.35;
      }
      if ((effects || now < inspectPulse.until || roomState.catWalking) && !reducedMotion.matches) {
        varyLights(now / 1000);
        idleTick(now, now / 1000);
        avatar.animateIdle(now / 1000);
      }
      if (!reducedMotion.matches) {
        atmosphere.tick(now / 1000, motionFactor);
        cam.updateCozyCam(now / 1000, dt, avatar.placement(), world.cat.position);
      }
      updateParticles(now, dt);
      if (now - shadowAt >= 110) {shadowAt = now; sun.shadow.needsUpdate = true;}
      adaptQuality(late);
      render();
    }
    if (((effects || cam.cozyCam || roomState.catWalking || atmosphere.state.precipitating || now < inspectPulse.until) && !reducedMotion.matches) || aliveParticles > 0) {
      ambientFrame = requestAnimationFrame(ambientTick);
    }
  }

  function kickAmbient() {
    if (!ambientFrame && active && !disposed && onScreen && !document.hidden) {
      lastAmbient = performance.now();
      ambientFrame = requestAnimationFrame(ambientTick);
    }
  }

  const onVisibility = () => {
    if (document.hidden) {cancelAnimationFrame(ambientFrame); ambientFrame = 0;}
    else kickAmbient();
  };
  reducedMotion.addEventListener('change', kickAmbient);
  document.addEventListener('visibilitychange', onVisibility);

  // Pointer & raycast hit-testing
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(), pointers = new Map();
  let multi = false, origin = null;
  const hitTargets = [world.walls];
  for (const prop of world.props.values()) hitTargets.push(prop.group);

  function resize() {
    const width = host.clientWidth, height = host.clientHeight;
    if (width < 1 || height < 1) return;
    renderer.setSize(width, height, false);
    pixelPass.resize(width, height);
    if (composer) {
      const ratio = renderer.getPixelRatio();
      composer.setPixelRatio(ratio); composer.setSize(width, height);
      if (bloom) bloom.setSize(Math.max(1, Math.round(width * ratio / 2)), Math.max(1, Math.round(height * ratio / 2)));
    }
    cam.updateFitAspect(width, height);
    render();
  }

  function pickPoint(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    scene.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    const first = raycaster.intersectObjects(scene.children, true).find(
      r => {
        if(!r.object.isMesh || r.object===particleMesh || r.object===world.cornerAO || r.object===world.contactShadows || r.object===world.windowSunPatch)return false;
        for(let node=r.object;node;node=node.parent)if(!node.visible)return false;
        return true;
      },
    );
    return first ? first.point : null;
  }

  function hit(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    scene.updateMatrixWorld();
    raycaster.setFromCamera(pointer, camera);
    const first = raycaster.intersectObjects(hitTargets, true).find(r => r.object.isMesh);
    let node = first?.object;
    while (node) {if (node.userData.portalKey) return node.userData.portalKey; node = node.parent;}
    return null;
  }

  function hitInspect(event) {
    if (!onInspect) return null;
    syncActorProxy();
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const first = raycaster.intersectObjects(inspectGroup.children, false)[0];
    return first?.object?.userData?.inspectKey || null;
  }

  function updateCursor() {canvas.style.cursor = (hovered || hoveredInspect) ? 'pointer' : 'grab';}

  function focus(key) {
    if (hovered === key) return;
    hovered = key;
    if (key && hoveredInspect) {hoveredInspect = null; onInspectHover(null);}
    for (const [id, p] of world.props) {p.group.position.y = p.baseY + (key === id ? p.hoverLift : 0); p.animate(p.progress || 0);}
    updateCursor(); onHover(key); render();
  }

  function focusInspect(key) {
    if (hoveredInspect === key) return;
    hoveredInspect = key;
    updateCursor();
    onInspectHover(key);
  }

  function pulseInspect(key, withSparks = false) {
    const preset = inspectPresets[key]; if (!preset) return false;
    inspectPulse = {key, start: performance.now(), until: performance.now() + 650};
    if (withSparks && effects && preset.anchor) spawnParticles(new THREE.Vector3(...preset.anchor));
    kickAmbient(); render();
    return true;
  }

  function tweenProp(key, target, durationMs, reduced = false) {
    const prop = world.props.get(key); if (!prop) return Promise.resolve();
    prop.cancel?.();
    const from = prop.progress || 0;
    if (Math.abs(target - from) < .001) {prop.progress = target; prop.animate(target); render(); return Promise.resolve();}
    const duration = (reduced || reducedMotion.matches) ? 0 : durationMs;
    return new Promise(resolve => {
      const start = performance.now(); let done = false;
      const finish = () => {if (done) return; done = true; if (prop.frame) {cancelAnimationFrame(prop.frame); prop.frame = 0;} prop.cancel = null; resolve();};
      prop.cancel = finish;
      function tick(now) {
        prop.frame = 0;
        const t = duration ? Math.min(1, (now - start) / duration) : 1, e = 1 - Math.pow(1 - t, 3);
        prop.progress = from + (target - from) * e;
        prop.animate(prop.progress);
        render();
        if (t < 1 && !disposed) prop.frame = requestAnimationFrame(tick);
        else finish();
      }
      tick(start);
    });
  }

  const down = event => {pointers.set(event.pointerId, true); if (pointers.size > 1) multi = true; origin = {id: event.pointerId, x: event.clientX, y: event.clientY};};
  const move = event => {if (!pointers.size) {const pKey = hit(event); focus(pKey); focusInspect(pKey ? null : hitInspect(event));}};
  const up = event => {
    const click = origin?.id === event.pointerId && !multi && Math.hypot(event.clientX - origin.x, event.clientY - origin.y) < 6;
    pointers.delete(event.pointerId);
    if (!pointers.size) {multi = false; origin = null;}
    if (click) {
      const key = hit(event), iKey = key ? null : hitInspect(event);
      if (effects) {
        const pt = pickPoint(event) || (key && portalPresets[key] ? new THREE.Vector3(...portalPresets[key].anchor) : iKey && inspectPresets[iKey] ? new THREE.Vector3(...inspectPresets[iKey].anchor) : null);
        spawnParticles(pt);
      }
      if (key) onSelect(key, {fromCanvas: true});
      else if (onInspect) onInspect(iKey);
    }
  };
  const cancel = () => {pointers.clear(); origin = null; multi = false;};
  canvas.addEventListener('pointerdown', down);
  canvas.addEventListener('pointermove', move);
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', cancel);
  canvas.addEventListener('pointerleave', () => {focus(null); focusInspect(null);});

  const observer = new ResizeObserver(resize); observer.observe(host);
  const inView = new IntersectionObserver(entries => {
    const inside = !!entries[entries.length - 1]?.isIntersecting;
    if (inside === onScreen) return;
    onScreen = inside;
    if (onScreen) {resize(); kickAmbient();}
    else {cancelAnimationFrame(ambientFrame); ambientFrame = 0;}
  }, {threshold: .02});
  inView.observe(host);
  canvas.addEventListener('webglcontextlost', event => {event.preventDefault(); host.dataset.contextLost = 'true';});
  canvas.addEventListener('webglcontextrestored', () => {delete host.dataset.contextLost; render();});

  resize(); kickAmbient();

  return {
    renderer: 'webgl',
    canvas,
    setCabinStyle,
    resetView: cam.resetView,
    zoom: cam.zoom,
    setView: cam.setView,
    setShotPreset: cam.setShotPreset,
    focusTarget: cam.focusTarget,
    clearFocus: cam.clearFocus,
    pulseInspect,
    batch,
    setActive(value) {
      active = value;
      avatar.setActive(value);
      if (active) {resize(); kickAmbient();}
      else {cam.pauseLoops(); cancelAnimationFrame(ambientFrame); ambientFrame = 0;}
    },
    setAvatarModel(model, index) {return avatar.setModel(model, index);},
    setGuestAvatarModel(model, index) {return avatar.setGuestModel(model, index);},
    setActorState(data, selection) {
      avatar.setState(data, selection);
      const p = avatar.placement().projection;
      const indoor = !!(p && p.visible && p.location === 'room');
      world.sleepDetails.visible = indoor && p.pose === 'sleep';
      world.cookFx.visible = indoor && p.pose === 'cook';
      world.washFx.visible = indoor && p.pose === 'wash';
      world.mealSet.visible = indoor && p.pose === 'eat';
      world.restingBroom.visible = !(indoor && p.pose === 'sweep');
      atmosphere.setStudying(indoor && (p.pose === 'write' || p.pose === 'read'));
      if (world.cookFx.visible || world.washFx.visible) kickAmbient();
      render();
    },
    onActorState(callback) {avatar.onState(callback);},
    actorDiagnostics() {return avatar.diagnostics();},
    projectActor() {return avatar.project(camera, host);},
    projectActorHead() {return avatar.projectHead(camera, host);},
    onFrame(fn) {if (typeof fn !== 'function') return () => {}; frameListeners.add(fn); return () => frameListeners.delete(fn);},
    setNight(value) {atmosphere.setNight(!!value); night = atmosphere.state.night; render();},
    setTimeMode(mode) {atmosphere.setTimeMode(mode); night = atmosphere.state.night; kickAmbient(); render();},
    setWeatherOverride(kind) {atmosphere.setWeatherOverride(kind); kickAmbient(); render();},
    setEnvironment(env, srvTime, items) {
      atmosphere.setEnvironment(env, srvTime, items);
      night = atmosphere.state.night;
      if (env?.room_design) applyRoomDesign(env.room_design, items || [], srvTime);
      kickAmbient(); render();
    },
    setRoomDesign(rd, items, srvTime) {applyRoomDesign(rd, items, srvTime); kickAmbient(); render();},
    setKeepsakes(ks) {roomState.applyKeepsakesState(ks); render();},
    setCatState(cs, immediate = false) {roomState.applyCatState(cs, immediate); kickAmbient(); render();},
    setCompanionCues(comp) {roomState.applyCompanionCues(comp); kickAmbient(); render();},
    setSeason(s) {world.garden.setSeason(s);world.styles.weather(night,world.garden.diagnostics().snow);render();},
    setEcology(eco) {world.garden.setEcology(eco); render();},
    setMailbox(mb) {world.garden.setMailbox(mb); kickAmbient(); render();},
    setCozyCam(v) {cam.setCozyCam(v); if (cam.cozyCam) kickAmbient(); render();},
    captureDataURL() {
      const prevOn = onScreen, prevAct = active;
      onScreen = true; active = true;
      render();
      let url = '';
      try {url = canvas.toDataURL('image/png');} catch {url = '';}
      onScreen = prevOn; active = prevAct;
      return url;
    },
    setPixelMode(value) {pixelPass.setEnabled(!!value); host.dataset.pixelMode = pixelPass.enabled ? 'true' : 'false'; render();},
    setAvailability(values) {for (const [key, prop] of world.props) prop.available = !!values.get(key)?.can_open;},
    setBusy(value) {cam.controls.enabled = !value;},
    setEffects(value) {effects = !!value; if (!effects) {applyBaseLights(); world.garden.setNight(night);} kickAmbient();},
    setParticleAmount(v) {particleScale = Math.max(0, Math.min(2, Number(v) || 1));},
    setGlow(v) {glowFactor = Math.max(0, Math.min(2, Number(v) || 1)); if (bloom) bloom.strength = bloomBase * glowFactor; render();},
    setMotion(v) {motionFactor = Math.max(0, Math.min(2, Number(v) || 1));},
    setQualityMode,
    focus,
    animate(key, reduced = false, opts = {}) {
      if (opts.sparks && effects && portalPresets[key]) spawnParticles(new THREE.Vector3(...portalPresets[key].anchor));
      return tweenProp(key, 1, 560, reduced);
    },
    closeProp(key, reduced = false) {return tweenProp(key, 0, 380, reduced);},
    reset(key) {const prop = world.props.get(key); if (prop) {prop.cancel?.(); prop.progress = 0; prop.animate(0);} render();},
    project(key) {
      scene.updateMatrixWorld();
      const point = new THREE.Box3().setFromObject(world.props.get(key).group).getCenter(new THREE.Vector3()).project(camera);
      return {x: (point.x + 1) * host.clientWidth / 2, y: (1 - point.y) * host.clientHeight / 2};
    },
    projectInspect(key) {
      const preset = inspectPresets[key]; if (!preset) return null;
      const a = preset.anchor || preset.boxes[0];
      const point = new THREE.Vector3(a[0], a[1], a[2]).project(camera);
      return {x: (point.x + 1) * host.clientWidth / 2, y: (1 - point.y) * host.clientHeight / 2};
    },
    diagnostics() {
      return {
        renderer: 'webgl',
        bloom: !!composer,
        pixelMode: pixelPass.enabled,
        pixelRes: pixelPass.resolution,
        atmosphere: atmosphere.state,
        cornerAO: world.cornerAO.count,
        inspected: cam.inspectedKey,
        pulse: inspectPulse.until > performance.now() ? inspectPulse.key : null,
        bundleModular: true,
        modelRevision: 'homes.1',
        cabinStyle: world.styles.id,
        portraitStatus:world.styles.portraitStatus,
        gardenModel: world.garden.diagnostics(),
        triangles: renderer.info.render.triangles,
        effects,
        particles: aliveParticles,
        particleScale,
        glowFactor,
        motionFactor,
        curtainMode: roomState.curtainMode,
        lampMode: roomState.lampMode,
        catSpot: roomState.catSpotKey,
        catWalking: roomState.catWalking,
        doorAngle: +(-world.frontDoorPivot.rotation.y).toFixed(3),
        cozyCam: cam.cozyCam,
        idle: {curtain: world.curtains[0].rotation.z, cat: world.catBody.scale.y, steam: world.steamA.position.y},
        attached: {curtain: !!world.curtains[0].parent, cat: !!world.catBody.parent, tail: !!world.tailA.parent, door: !!world.frontDoorPivot.parent},
        cues: {cook: world.cookFx.visible, wash: world.washFx.visible, meal: world.mealSet.visible, broom: world.restingBroom.visible, sleep: world.sleepDetails.visible},
        meshes: scene.children.reduce((count, g) => {g.traverse(o => {if (o.isMesh) count++;}); return count;}, 0),
        camera: camera.position.toArray(),
        active,
        night,
        view: cam.view,
        gardenBounds: world.garden.bounds,
        progress: Object.fromEntries([...world.props].map(([key, value]) => [key, value.progress || 0])),
        draw_calls: renderer.info.render.calls,
        batches: world.bakedBatches.length,
        lights: (() => {let count = 0; scene.traverse(node => {if (node.isLight) count++;}); return count;})(),
        quality: {mode: quality.mode, level: quality.level, dpr: renderer.getPixelRatio(), post: !!(composer && bloomActive && quality.post)},
      };
    },
    dispose() {
      disposed = true;
      frameListeners.clear();
      cam.dispose();
      detachShelterFog();
      avatar.dispose();
      atmosphere.dispose();
      world.styles.dispose();
      world.garden.dispose?.();
      pixelPass.dispose();
      world.picturePixelTex?.dispose?.();
      for (const p of world.props.values()) p.cancel?.();
      cancelAnimationFrame(ambientFrame);
      reducedMotion.removeEventListener('change', kickAmbient);
      document.removeEventListener('visibilitychange', onVisibility);
      observer.disconnect();
      inView.disconnect();
      inspectGroup.traverse(node => {if (node.isMesh) node.geometry.dispose();});
      scene.traverse(node => {
        if (node.isMesh) {
          node.geometry.dispose();
          if (Array.isArray(node.material)) node.material.forEach(m => m.dispose());
          else node.material.dispose();
        }
      });
      for (const t of world.textures) t.dispose();
      for (const geometry of world.geometries.values()) geometry.dispose();
      particleGeo.dispose(); particleMat.dispose();
      world.occluderMaterial.dispose();
      bloom?.dispose?.(); outputPass?.dispose?.(); composer?.dispose?.();
      renderer.dispose();
      canvas.remove();
    },
  };
}
