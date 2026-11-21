/* Camera controller, OrbitControls damping, Cozy Cam & Auto-Director shot presets. */
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';

const SHOT_PRESETS = {
  garden: {target: [0, 1.0, 1.2], offset: [17, 15.3, 23.15], view: 'garden'},
  room: {target: [0, 1.72, 0], offset: [9.8, 8.5, 14.4], view: 'room'},
  room_center: {target: [-0.2, 1.05, 0.2], offset: [9.4, 7.6, 11.4], view: 'room'},
  desk: {target: [-0.1, 1.32, -1.25], offset: [5.2, 3.8, 6.8], view: 'room'},
  kitchen: {target: [-3.4, 1.02, 2.35], offset: [6.4, 4.5, 6.8], view: 'room'},
  bed: {target: [-2.85, 0.96, 0.25], offset: [6.0, 4.2, 6.6], view: 'room'},
  gate: {target: [0.35, 0.68, 6.35], offset: [5.4, 3.8, 6.8], view: 'garden'},
};

export function createCabinCameraController({
  THREE, camera, canvas, host, reducedMotion, inspectPresets, portalPresets, render, isActive, isDisposed, getStyle=()=> 'cottage',
}) {
  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 1, 1.2);
  controls.enablePan = false;
  controls.enableDamping = true;
  controls.dampingFactor = .08;
  controls.minDistance = 10;
  controls.maxDistance = 52;
  controls.minPolarAngle = .38;
  controls.maxPolarAngle = 1.28;
  controls.minAzimuthAngle = -1.1;
  controls.maxAzimuthAngle = 1.1;
  controls.rotateSpeed = .65;
  controls.zoomSpeed = .8;
  controls.update();

  let fitFactor = 1, fitLimit = Infinity, view = 'garden', cozyCam = false, inspectedKey = null;
  let glideFrame = 0, dampingFrame = 0, interacting = false, dampingUntil = 0;
  const cozyTarget = new THREE.Vector3(), cozyDesiredPos = new THREE.Vector3();

  // Widen the lens to fit narrow screens. Moving the camera backwards would
  // add artificial atmospheric fog to a clear day and clip the garden at maxDistance.
  function frameLens(limit) {
    fitLimit=limit;
    camera.zoom=1/Math.min(fitFactor,fitLimit);
    camera.updateProjectionMatrix();
  }
  function stopGlide() {
    if (glideFrame) {cancelAnimationFrame(glideFrame); glideFrame = 0;}
  }

  function dampingTick(now) {
    dampingFrame = 0;
    if (isDisposed() || !isActive()) return;
    controls.update();
    render();
    if (interacting || now < dampingUntil) dampingFrame = requestAnimationFrame(dampingTick);
  }

  function kickDamping() {
    if (!dampingFrame) dampingFrame = requestAnimationFrame(dampingTick);
  }

  controls.addEventListener('start', () => {stopGlide(); interacting = true; kickDamping();});
  controls.addEventListener('end', () => {interacting = false; dampingUntil = performance.now() + 700; kickDamping();});

  function glideCamera(toTarget, toPos, reduced = false) {
    stopGlide();
    if (reduced || reducedMotion.matches) {
      controls.target.copy(toTarget);
      camera.position.copy(toPos);
      controls.update();
      render();
      return;
    }
    const fromTarget = controls.target.clone(), fromPos = camera.position.clone(), start = performance.now(), duration = 520;
    function stepGlide(now) {
      glideFrame = 0;
      if (isDisposed() || !isActive()) return;
      const t = Math.min(1, (now - start) / duration), e = 1 - Math.pow(1 - t, 3);
      controls.target.lerpVectors(fromTarget, toTarget, e);
      camera.position.lerpVectors(fromPos, toPos, e);
      controls.update();
      render();
      if (t < 1) glideFrame = requestAnimationFrame(stepGlide);
    }
    glideFrame = requestAnimationFrame(stepGlide);
  }

  function focusTarget(key, reduced = false) {
    const preset = inspectPresets[key] || portalPresets[key];
    if (!preset) return false;
    inspectedKey = key;
    frameLens(1.22);
    controls.minDistance = 3.6;
    const tgt = new THREE.Vector3(...preset.target);
    const pos = new THREE.Vector3(...preset.offset).add(tgt);
    glideCamera(tgt, pos, reduced);
    return true;
  }

  function clearFocus(reduced = false) {
    inspectedKey = null;
    controls.minDistance = 10;
    const preset=SHOT_PRESETS[view];
    const tgt = new THREE.Vector3(...preset.target);
    frameLens(Infinity);
    const pos = new THREE.Vector3(...preset.offset).add(tgt);
    glideCamera(tgt, pos, reduced);
  }

  function resetView() {
    stopGlide();
    inspectedKey = null;
    controls.minDistance = 10;
    const preset=SHOT_PRESETS[view];
    controls.target.set(...preset.target);
    frameLens(Infinity);
    camera.position.set(...preset.offset).add(controls.target);
    controls.update();
    render();
  }

  function setView(next) {
    if (!['garden', 'room'].includes(next)) return;
    view = next;
    resetView();
  }

  function setShotPreset(shotPlan, immediate = true) {
    const mode = typeof shotPlan === 'string' ? shotPlan : (shotPlan?.shot_mode || 'garden');
    const focus = typeof shotPlan === 'object' && shotPlan?.focus ? shotPlan.focus : mode;
    const preset = SHOT_PRESETS[focus] || SHOT_PRESETS[mode] || SHOT_PRESETS.garden;
    view = preset.view;
    inspectedKey = null;
    controls.minDistance = 3.6;
    const tgt = new THREE.Vector3(...preset.target);
    if(getStyle()!=='cottage' && ['desk','kitchen','bed'].includes(focus))tgt.set(...inspectPresets[focus].target);
    frameLens(1.24);
    const pos = new THREE.Vector3(...preset.offset).add(tgt);
    glideCamera(tgt, pos, immediate);
    return {shot_mode: mode, focus};
  }

  function zoom(factor) {
    const delta = camera.position.clone().sub(controls.target);
    delta.setLength(THREE.MathUtils.clamp(delta.length() * factor, controls.minDistance, 52));
    camera.position.copy(controls.target).add(delta);
    controls.update();
    render();
  }

  function updateFitAspect(width, height) {
    camera.aspect = width / height;
    fitFactor = Math.min(1.78, Math.max(1, 1.25 / camera.aspect));
    frameLens(fitLimit);
    controls.update();
  }

  function updateCozyCam(seconds, dt, avatarDiag, catPos) {
    if (!cozyCam || interacting || inspectedKey || glideFrame) return;
    const vp = avatarDiag?.visual_position;
    if (vp && avatarDiag?.projection?.visible) {
      cozyTarget.set(vp[0], vp[1] + 1.05, vp[2]);
    } else {
      cozyTarget.set(catPos.x, catPos.y + .35, catPos.z);
    }
    const sway = Math.sin(seconds * .085) * .38;
    const distScale = avatarDiag?.projection?.location === 'room' ? 11.2 : 14.8;
    cozyDesiredPos.set(
      cozyTarget.x + Math.sin(.52 + sway) * distScale * .82,
      cozyTarget.y + distScale * .56 + Math.sin(seconds * .13) * .35,
      cozyTarget.z + Math.cos(.52 + sway) * distScale * .92,
    );
    const k = Math.min(1, dt * 1.6);
    controls.target.lerp(cozyTarget, k);
    camera.position.lerp(cozyDesiredPos, k);
    controls.update();
  }

  const onKeyDown = event => {
    if (['+', '=', '-', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) {
      event.preventDefault();
      if (event.key === 'Home') return resetView();
      if (['+', '=', '-'].includes(event.key)) return zoom(event.key === '-' ? 1.12 : .89);
      const spherical = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
      spherical.theta = THREE.MathUtils.clamp(spherical.theta + (event.key === 'ArrowLeft' ? -.12 : event.key === 'ArrowRight' ? .12 : 0), -1.1, 1.1);
      spherical.phi = THREE.MathUtils.clamp(spherical.phi + (event.key === 'ArrowUp' ? -.1 : event.key === 'ArrowDown' ? .1 : 0), .38, 1.28);
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
      controls.update();
      render();
    }
  };
  canvas.addEventListener('keydown', onKeyDown);

  return {
    controls,
    stopGlide,
    glideCamera,
    focusTarget,
    clearFocus,
    resetView,
    setView,
    setShotPreset,
    zoom,
    updateFitAspect,
    updateCozyCam,
    setCozyCam(v) {cozyCam = Boolean(v); if (cozyCam) {inspectedKey = null; frameLens(1.25); stopGlide();} else frameLens(inspectedKey ? 1.22 : Infinity);},
    get cozyCam() {return cozyCam;},
    get view() {return view;},
    get inspectedKey() {return inspectedKey;},
    get fitFactor() {return fitFactor;},
    pauseLoops() {stopGlide(); cancelAnimationFrame(dampingFrame); dampingFrame = 0; interacting = false;},
    dispose() {
      stopGlide();
      cancelAnimationFrame(dampingFrame);
      canvas.removeEventListener('keydown', onKeyDown);
      controls.dispose();
    },
  };
}
