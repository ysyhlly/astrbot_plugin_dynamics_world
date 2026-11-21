/* Voxel cabin architecture, furniture, portals, floor sunbeam, hinged front door & static batch baker. */
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import {addCabinGarden} from './cabin-garden.js';
import {createCabinJoinery} from './cabin-joinery.js';
import {addWindowLandscape} from './cabin-window.js';
import {createCabinStyles} from './cabin-styles.js';
import {placeObject} from './cabin-plans.js';

import {NearestMipmapLinearFilter} from 'three';
import {surfaceCanvas} from './cabin-surfaces.js';
export {surfaceCanvas};

function createWindowSunbeamTexture(THREE, textures) {
  const c = document.createElement('canvas');
  c.width = c.height = 96;
  const g = c.getContext('2d');
  g.clearRect(0, 0, 96, 96);
  // 2x2 soft mullioned window panes
  for (const [px, py] of [[10, 10], [50, 10], [10, 50], [50, 50]]) {
    const grad = g.createLinearGradient(0, py, 0, py + 36);
    grad.addColorStop(0, 'rgba(255,250,232,0.92)');
    grad.addColorStop(0.75, 'rgba(255,244,212,0.68)');
    grad.addColorStop(1, 'rgba(255,238,196,0.12)');
    g.fillStyle = grad;
    g.fillRect(px, py, 36, 36);
  }
  // Soft outer fade
  const mask = g.createRadialGradient(48, 44, 14, 48, 48, 50);
  mask.addColorStop(0, 'rgba(255,255,255,1)');
  mask.addColorStop(0.82, 'rgba(255,255,255,0.85)');
  mask.addColorStop(1, 'rgba(255,255,255,0)');
  g.globalCompositeOperation = 'destination-in';
  g.fillStyle = mask;
  g.fillRect(0, 0, 96, 96);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  textures.push(tex);
  return tex;
}

export function buildCabinWorld(THREE, scene, {getHovered, getNight, particleMesh,invalidate}) {
  const props = new Map(), materials = new Map(), geometries = new Map(), textures = [];
  let chatCompanionGlow = false;
  const material = (color, roughness = .9) => {
    const key = color + ':' + roughness;
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({color, roughness}));
    return materials.get(key);
  };
  const surfaceCache = new Map(), texturedMaterials = new Map();
  const tex = (kind, color, roughness = .9, rx = 1, ry = 1) => {
    const key = [kind,color,roughness,rx,ry].join('/');
    if (texturedMaterials.has(key)) return texturedMaterials.get(key);
    if (!surfaceCache.has(kind)) surfaceCache.set(kind, surfaceCanvas(kind));
    const map = new THREE.CanvasTexture(surfaceCache.get(kind));
    map.userData.cabinSurface=kind;
    map.wrapS = map.wrapT = THREE.RepeatWrapping;
    map.repeat.set(rx, ry);
    map.colorSpace = THREE.SRGBColorSpace;
    map.magFilter = THREE.NearestFilter;
    map.minFilter = NearestMipmapLinearFilter;
    textures.push(map);
    const surface = new THREE.MeshStandardMaterial({color, roughness, map});
    texturedMaterials.set(key,surface);
    return surface;
  };
  const box = (parent, w, h, d, x, y, z, color, extra = {}) => {
    const key = [w, h, d].join(',');
    if (!geometries.has(key)) geometries.set(key, new THREE.BoxGeometry(w, h, d));
    const mesh = new THREE.Mesh(geometries.get(key), extra.material || material(color));
    mesh.position.set(x, y, z);
    mesh.castShadow = extra.castShadow !== false;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  };
  const group = (x = 0, y = 0, z = 0) => {const g = new THREE.Group(); g.position.set(x, y, z); scene.add(g); return g;};
  const sub = (parent, x = 0, y = 0, z = 0) => {const g = new THREE.Group(); g.position.set(x, y, z); parent.add(g); return g;};

  const joinery=createCabinJoinery(THREE,{box,sub,tex,geometries});

  // Floor & planks
  const floor = group();
  joinery.foundation(floor);
  // Staggered oak boards with continuous perimeter border. One instanced draw.
  const plankGeometry=new THREE.BoxGeometry(1,.035,.385),plankMaterial=tex('wood',0xffffff,.91,1,1);
  geometries.set('__plank',plankGeometry);
  const rows=[];
  for(let z=0;z<18;z++){
    const lo=-4.79,hi=4.79,start=lo-(z%3)*.51;
    for(let x=start;x<hi;x+=1.59){const l=Math.max(lo,x),r=Math.min(hi,x+1.578);if(r>l)rows.push([(l+r)/2,r-l,-3.37+z*.394]);}
  }
  const planks=new THREE.InstancedMesh(plankGeometry,plankMaterial,rows.length),matrix=new THREE.Matrix4(),q=new THREE.Quaternion();
  rows.forEach(([x,w,z],i)=>{
    matrix.compose(new THREE.Vector3(x,.115,z),q,new THREE.Vector3(w,1,1));planks.setMatrixAt(i,matrix);
    planks.setColorAt(i,new THREE.Color([0xc18d64,0xb78059,0xd39d6a,0xcc9261][(i*13+Math.floor(i/7))%4]));
  });
  planks.receiveShadow=true;scene.add(planks);
  const walls = group();
  const doorwayFrame = group(1.29, .132, 3.38);
  const frontDoorPivot = group(.59, .15, 3.72);
  frontDoorPivot.userData.keepSeparate = true;
  joinery.entry(doorwayFrame,frontDoorPivot);

  // North window & sky
  const windowGroup = group(.05, 2.25, -3.51);
  box(windowGroup, 2.15, 1.7, .12, 0, 0, 0, 0x4c3c42);
  const skyMaterial = new THREE.MeshStandardMaterial({color: 0xa7cbca, emissive: 0x739f9c, emissiveIntensity: .3, roughness: 1});
  box(windowGroup, 1.96, 1.49, .035, 0, 0, .09, 0xbddbd3, {material: skyMaterial, castShadow: false}).receiveShadow = false;
  const daySky = sub(windowGroup), nightSky = sub(windowGroup);
  nightSky.visible = false;
  const valley=sub(windowGroup);
  valley.userData.keepSeparate=true;
  const sunDisk = addWindowLandscape(THREE, valley, daySky, nightSky, skyMaterial.color, textures);
  const starMaterial = new THREE.MeshStandardMaterial({color: 0xe6eef5, emissive: 0xe6eef5, emissiveIntensity: 2.2, roughness: 1});
  const starPositions = [[-.8, .55], [-.5, .28], [-.2, .62], [.08, .4], [-.85, .1], [.2, .12], [.45, .68], [-.35, .45], [.85, .6], [.75, .15], [-.05, .2]];
  const starGeo = new THREE.BoxGeometry(.035, .035, .002);
  geometries.set('__star', starGeo);
  const stars = new THREE.InstancedMesh(starGeo, starMaterial, starPositions.length), starMatrix = new THREE.Matrix4();
  starPositions.forEach(([x, y], i) => {starMatrix.makeTranslation(x, y, .112); stars.setMatrixAt(i, starMatrix);});
  stars.castShadow = false;
  nightSky.add(stars);
  const glassMaterial = new THREE.MeshStandardMaterial({color: 0xe8f2ec, transparent: true, opacity: .07, roughness: .23, depthWrite: false});
  box(windowGroup, 1.96, 1.49, .012, 0, 0, .15, 0xffffff, {material: glassMaterial, castShadow: false});
  box(windowGroup, .07, 1.5, .1, 0, 0, .17, 0xf8cf91);
  box(windowGroup, 1.98, .07, .1, 0, 0, .17, 0xf8cf91);
  const curtains = [];
  for (const x of [-1.06, 1.06]) {
    const panel = sub(windowGroup, x, .03, .32);
    panel.userData.keepSeparate = true;
    joinery.curtain(panel);
    curtains.push(panel);
  }
  box(windowGroup, .15, .13, .15, -.72, -.74, .27, 0xc49f80);
  box(windowGroup, .12, .025, .12, -.72, -.67, .27, 0x846f58, {castShadow: false});
  for (const [lx, ly, lz] of [[-.72, -.61, .27], [-.78, -.64, .22], [-.66, -.64, .31]]) {
    box(windowGroup, .065, .085, .065, lx, ly, lz, 0x8eaf82, {castShadow: false});
  }

  const cottageShell=group(), cottageTrim=sub(windowGroup);
  cottageTrim.userData.keepSeparate=true;
  joinery.architecture(cottageShell,cottageTrim);

  // Indoor north-window floor sunbeam patch (slides smoothly with continuous solar azimuth)
  const sunbeamGeo = new THREE.PlaneGeometry(2.15, 1.95);
  geometries.set('__sunbeam', sunbeamGeo);
  const sunbeamMat = new THREE.MeshBasicMaterial({
    map: createWindowSunbeamTexture(THREE, textures),
    color: 0xfff1c4,
    transparent: true,
    opacity: .22,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  });
  const windowSunPatch = new THREE.Mesh(sunbeamGeo, sunbeamMat);
  windowSunPatch.rotation.x = -Math.PI / 2;
  windowSunPatch.position.set(.05, .142, -2.28);
  windowSunPatch.renderOrder = 2;
  windowSunPatch.castShadow = false;
  windowSunPatch.receiveShadow = false;
  windowSunPatch.userData.keepSeparate = true;
  scene.add(windowSunPatch);

  // Dust motes
  const moteMaterial = new THREE.MeshStandardMaterial({color: 0xfff2cc, emissive: 0xfff2cc, emissiveIntensity: .6, transparent: true, opacity: .5, roughness: 1, depthWrite: false});
  const motes = group();
  for (const [mx, my, mz] of [[.4, 1.6, -2.2], [1, 2.1, -1.4], [.2, 1.2, -.6], [1.4, 1.8, -2.6], [.8, 2.4, -1], [1.8, 1.3, -1.8], [-.2, 2, -2]]) {
    box(motes, .022, .022, .022, mx, my, mz, 0xfff2cc, {material: moteMaterial, castShadow: false});
  }

  // Bed (localRoot so movable room_design slots can relocate the whole bed group!)
  const bed = group(-3.25, 0, .05);
  bed.userData.keepSeparate = true;
  joinery.bed(bed);
  const sleepDetails = sub(bed, 0, 0, 0);
  sleepDetails.visible = false;
  box(sleepDetails, 2.28, .07, .23, 0, 1.08, -.53, 0xf4d6a2, {castShadow: false});
  const zzz = sub(sleepDetails, .47, 1.5, -1.0);
  const zMaterial = new THREE.MeshStandardMaterial({color: 0xeef0cc, emissive: 0xeef0cc, emissiveIntensity: .5, transparent: true, opacity: .85, roughness: 1, depthWrite: false});
  const makeZ = (size, x, y) => {
    const g = sub(zzz, x, y, 0);
    box(g, size, .022, .022, 0, size / 2, 0, 0xeef0cc, {material: zMaterial, castShadow: false});
    box(g, size, .022, .022, 0, -size / 2, 0, 0xeef0cc, {material: zMaterial, castShadow: false});
    const d = box(g, size * 1.15, .022, .022, 0, 0, 0, 0xeef0cc, {material: zMaterial, castShadow: false});
    d.rotation.z = -.62;
  };
  makeZ(.16, 0, 0); makeZ(.12, .2, .26); makeZ(.09, .36, .48);
  for (const [sx, sz, ry] of [[1.55, .5, .35], [1.81, .69, .5]]) {
    const slipper = sub(bed, sx, .13, sz);
    slipper.rotation.y = ry;
    box(slipper, .15, .05, .34, 0, 0, 0, 0xc9b8a0);
    box(slipper, .15, .075, .13, 0, .035, -.1, 0xd8c8b2);
  }

  // Desk & Chair (localRoots so movable room_design slots can relocate them smoothly!)
  const desk = group(0, 0, -1.48);
  desk.userData.keepSeparate = true;
  const chair = group(0,0,.18);
  chair.userData.keepSeparate=true;
  joinery.desk(desk,chair);

  // The working page and the hinged memory journal occupy separate desk spaces.
  const sheet = sub(desk, .10, 1.434, .18);
  sheet.rotation.y = -.13;
  box(sheet,.48,.015,.54,0,0,0,0xffdfad);
  for (const z of [-.12,-.035,.05]) box(sheet,.26,.006,.018,-.025,.012,z,0xa98464,{castShadow:false});
  const pencil = sub(desk,.43,1.449,.24);
  pencil.rotation.y=.48;
  box(pencil,.35,.031,.031,0,0,0,0xd49a49);
  box(pencil,.04,.022,.022,.193,0,0,0x4c4145);
  const mug = sub(desk, .62, 1.43, -.38);
  joinery.mug(mug);
  const steamMaterial = new THREE.MeshStandardMaterial({color: 0xf4f2e8, transparent: true, opacity: .32, roughness: 1, depthWrite: false});
  const steamA = box(mug, .03, .09, .03, -.04, .33, 0, 0xf4f2e8, {material: steamMaterial, castShadow: false}); steamA.rotation.z = .15; steamA.userData.keepSeparate = true;
  const steamB = box(mug, .03, .08, .03, .05, .36, 0, 0xf4f2e8, {material: steamMaterial, castShadow: false}); steamB.rotation.z = -.15; steamB.userData.keepSeparate = true;
  const alarm = sub(desk, -1.28, 1.43, -.4);
  box(alarm, .26, .24, .09, 0, .14, 0, 0x87997c);
  box(alarm, .2, .2, .02, 0, .14, .05, 0xf2ecd6, {castShadow: false});
  box(alarm, .018, .08, .012, -.02, .17, .065, 0x6d7a63, {castShadow: false});
  box(alarm, .014, .1, .012, .03, .16, .065, 0x6d7a63, {castShadow: false});
  for (const bx of [-.08, .08]) box(alarm, .05, .04, .05, bx, .28, 0, 0xa88d6f, {castShadow: false});
  box(desk,.13,.12,.12,-.99,1.49,-.29,0x375660);
  const quill=box(desk,.027,.24,.027,-.95,1.63,-.29,0xeec895);
  quill.rotation.z=-.31;

  // Desk Lamp (child of desk so it travels if desk relocates!)
  const lamp = sub(desk, 1.13, 1.43, -.24);
  lamp.userData.keepSeparate = true;
  const bulbMaterial = new THREE.MeshStandardMaterial({color:0xffd18b, emissive:0xffbd61, emissiveIntensity:.15, roughness:.78});
  joinery.lamp(lamp,bulbMaterial);
  const warm = new THREE.PointLight(0xffd89b, 3.1, 4, 2);
  warm.position.set(1.13, 1.88, -1.65);
  scene.add(warm);

  // Rug
  const rug = group(0,.15,1.12);
  joinery.rug(rug);

  const shelf=group(-2.52,2.48,-3.37);
  shelf.userData.keepSeparate=true;
  joinery.shelf(shelf);
  const shelfStand=sub(shelf);
  shelfStand.userData.keepSeparate=true;
  joinery.shelfStand(shelfStand);
  shelfStand.visible=false;
  const shelfVolumesGroup = sub(shelf, 0, 0, 0);
  shelfVolumesGroup.userData.keepSeparate = true;

  const picture = group(-4.05, 2.23, -3.53);
  box(picture, .9, 1, .09, 0, 0, 0, 0x849779);
  box(picture, .76, .86, .04, 0, 0, .07, 0xf0e9cf);
  const pictureDefaultArt = sub(picture, 0, 0, 0);
  pictureDefaultArt.userData.keepSeparate = true;
  box(pictureDefaultArt, .23, .22, .035, .17, .21, .11, 0xddcc91);
  box(pictureDefaultArt, .65, .25, .03, 0, -.23, .11, 0xa2b89a);
  box(pictureDefaultArt, .26, .17, .03, -.16, -.04, .11, 0x8ca88b);
  const picturePixelCanvas = document.createElement('canvas'); picturePixelCanvas.width = 16; picturePixelCanvas.height = 12;
  const picturePixelTex = new THREE.CanvasTexture(picturePixelCanvas);
  picturePixelTex.colorSpace = THREE.SRGBColorSpace;
  picturePixelTex.magFilter = THREE.NearestFilter;
  picturePixelTex.minFilter = THREE.NearestFilter;
  picturePixelTex.generateMipmaps = false;
  textures.push(picturePixelTex);
  const picturePixelMat = new THREE.MeshBasicMaterial({map: picturePixelTex, toneMapped: false});
  const picPlaneGeo = new THREE.PlaneGeometry(.72, .80);
  geometries.set('__picPlane', picPlaneGeo);
  const picturePixelMesh = new THREE.Mesh(picPlaneGeo, picturePixelMat);
  picturePixelMesh.position.set(0, 0, .115); picturePixelMesh.visible = false; picturePixelMesh.userData.keepSeparate = true;
  picture.add(picturePixelMesh);

  const postcard = group(-4.05, 1.42, -3.53);
  box(postcard, .56, .38, .03, 0, 0, 0, 0xf0e9cf);
  box(postcard, .06, .1, .04, 0, .2, .01, 0x87997c);
  box(postcard, .4, .05, .015, 0, -.06, .025, 0xa2b89a, {castShadow: false});
  box(postcard, .3, .04, .015, -.04, -.13, .025, 0xddcc91, {castShadow: false});
  const wallClock = group(-1.43, 2.78, -3.55);
  box(wallClock, .42, .42, .07, 0, 0, 0, 0x87997c);
  box(wallClock, .34, .34, .03, 0, 0, .045, 0xf2ecd6, {castShadow: false});
  const hand = (length, width, angle) => {
    const pivot = sub(wallClock, 0, 0, .065);
    box(pivot, width, length, .012, 0, length / 2 - .02, 0, 0x6d7a63, {castShadow: false});
    pivot.rotation.z = -angle;
  };
  hand(.13, .026, (10 + 10 / 60) / 12 * Math.PI * 2);
  hand(.19, .02, 10 / 60 * Math.PI * 2);
  box(wallClock, .035, .035, .015, 0, 0, .07, 0xa88d6f, {castShadow: false});

  const fairyPoints = [], fairyN = 15;
  for (let i = 0; i <= fairyN; i++) {const t = i / fairyN; fairyPoints.push(new THREE.Vector3(-4.55 + t * 9.4, 3.34 - Math.sin(t * Math.PI) * .34, -3.56));}
  const wireGeometry = new THREE.BoxGeometry(1, .018, .018), wireMaterial = material(0x6f7d66);
  geometries.set('__wire', wireGeometry);
  for (let i = 0; i < fairyN; i++) {
    const a = fairyPoints[i], b = fairyPoints[i + 1];
    const wire = new THREE.Mesh(wireGeometry, wireMaterial);
    wire.position.copy(a).add(b).multiplyScalar(.5); wire.scale.x = a.distanceTo(b); wire.rotation.z = Math.atan2(b.y - a.y, b.x - a.x); wire.castShadow = false;
    walls.add(wire);
  }
  const bulbGeometry = new THREE.BoxGeometry(.075, .095, .075);
  geometries.set('__fbulb', bulbGeometry);
  const fairyBulbMaterial = new THREE.MeshStandardMaterial({color: 0xf2d8a0, emissive: 0xf2d8a0, emissiveIntensity: .3, roughness: .6});
  const fairyBulbs = new THREE.InstancedMesh(bulbGeometry, fairyBulbMaterial, fairyN - 1), bulbMatrix = new THREE.Matrix4();
  for (let i = 1; i < fairyN; i++) {bulbMatrix.makeTranslation(fairyPoints[i].x, fairyPoints[i].y - .075, fairyPoints[i].z); fairyBulbs.setMatrixAt(i - 1, bulbMatrix);}
  fairyBulbs.castShadow = false;
  walls.add(fairyBulbs);
  const readingLight=joinery.wallLantern(walls,fairyBulbMaterial);
  box(walls, .04, .18, .12, -4.88, 1.3, 2.9, 0xf0ead2);
  box(walls, .025, .06, .045, -4.86, 1.32, 2.9, 0xd8d2ba, {castShadow: false});
  box(walls, .16, .16, .025, 1.9, .3, -3.6, 0xf0ead2, {castShadow: false});
  for (const hx of [-.04, .04]) box(walls, .02, .05, .012, 1.9 + hx, .3, -3.585, 0x8a8f7a, {castShadow: false});

  // Portals: Wardrobe, Memory & Learning Books, Phone
  const wardrobe = group(3.52, 0, -2.38); wardrobe.userData.portalKey = 'visual';
  const leftDoor = sub(wardrobe,-.87,.36,.57);
  const rightDoor = sub(wardrobe,.87,.36,.57);
  joinery.wardrobe(wardrobe,leftDoor,rightDoor);
  props.set('visual', {
    group: wardrobe, baseY: wardrobe.position.y, hoverLift: 0, progress: 0, frame: 0, cancel: null,
    animate: t => {const o = Math.max(t * 1.8, getHovered() === 'visual' ? .16 : 0); leftDoor.rotation.y = -o; rightDoor.rotation.y = o;},
  });

  const makeBook = (key, parent, x, y, z, color, scale = 1) => {
    const g = sub(parent, x, y, z);
    g.scale.setScalar(scale); g.userData.portalKey = key; g.userData.keepSeparate = true;
    box(g, .74, .075, .51, 0, .04, 0, 0xefe7c8);
    box(g, .77, .025, .54, 0, 0, 0, color);
    for (let n = 0; n < 3; n++) box(g, .49, .005, .018, .04, .08, -.14 + n * .1, 0xb9b18d, {castShadow: false});
    const hinge = new THREE.Group(); hinge.position.set(-.385, .09, 0); g.add(hinge);
    box(hinge, .77, .035, .54, .385, 0, 0, color);
    box(hinge,.26,.012,.22,.43,.025,-.018,0xf3d391);
    box(hinge,.155,.006,.12,.43,.034,-.018,color,{castShadow:false});
    box(hinge,.065,.009,.066,.43,.039,-.018,0xf3d391,{castShadow:false});
    box(hinge, .04, .013, .5, .09, .024, 0, 0x9eb3ad);
    props.set(key, {
      group: g, baseY: g.position.y, hoverLift: .035, progress: 0, frame: 0, cancel: null,
      animate: t => {hinge.rotation.z = Math.max(t * 2.75, getHovered() === key ? .2 : 0);},
    });
    return g;
  };
  const memoryProp = makeBook('memory', desk, -.6, 1.436, .12, 0x396271, 1.12);
  const book = makeBook('learning', bed, .15, 1.055, .43, 0xaa574e, 1.14); book.rotation.y = -.18;
  const memoryBookmarkMat = new THREE.MeshStandardMaterial({color: 0xf2b872, emissive: 0xf2b872, emissiveIntensity: .55, roughness: .7});
  const memoryBookmark = sub(memoryProp, .28, .06, .30); memoryBookmark.visible = false; memoryBookmark.userData.keepSeparate = true;
  box(memoryBookmark, .08, .014, .16, 0, 0, 0, 0xf2b872, {material: memoryBookmarkMat, castShadow: false});
  const learningMarkerMat = new THREE.MeshStandardMaterial({color: 0xa8d5a2, emissive: 0xa8d5a2, emissiveIntensity: .45, roughness: .7});
  const learningMarker = sub(book, .30, .06, -.24); learningMarker.visible = false; learningMarker.userData.keepSeparate = true;
  box(learningMarker, .07, .014, .15, 0, 0, 0, 0xa8d5a2, {material: learningMarkerMat, castShadow: false});

  const table = group(3.33, 0, 1.8);
  const phone = sub(table,0,.91,-.05); phone.rotation.x = -.28; phone.userData.portalKey = 'chat';
  box(phone, .44, .81, .065, 0, .405, 0, 0x3f6258);
  const screenMaterial = new THREE.MeshStandardMaterial({color: 0x789e99, emissive: 0x82beac, emissiveIntensity: .03, roughness: .4});
  box(phone, .36, .66, .012, 0, .42, .04, 0x789e99, {material: screenMaterial});
  box(phone, .1, .025, .012, 0, .765, .04, 0x284c40);
  box(phone, .02, .1, .03, .225, .55, 0, 0x284c40, {castShadow: false});
  for (const [x,y,w,tint] of [[-.045,.58,.205,0xc2d3b0],[.06,.495,.16,0xefd096],[-.045,.30,.19,0xc2d3b0]]) {
    box(phone,w,.051,.012,x,y,.053,tint,{castShadow:false});
  }
  const bubble = new THREE.Group(); phone.add(bubble);
  box(bubble, .24, .16, .015, 0, .47, .055, 0xeef0cc);
  box(bubble, .05, .07, .015, -.09, .37, .055, 0xeef0cc);
  for (const x of [-.06, .06]) box(bubble, .025, .025, .012, x, .48, .068, 0x7da58e);
  bubble.visible = false;
  props.set('chat', {
    group: phone, baseY: phone.position.y, hoverLift: .035, progress: 0, frame: 0, cancel: null,
    animate: t => {
      const h = getHovered() === 'chat' ? .18 : 0;
      screenMaterial.emissiveIntensity = (getNight() ? .12 : .03) + Math.max(t * .85, h, chatCompanionGlow ? .22 : 0);
      bubble.visible = t > .35 || chatCompanionGlow;
      bubble.position.y = t > .35 ? (1 - t) * -.1 : 0;
      phone.rotation.z = Math.sin(t * Math.PI * 4) * .045;
    },
  });

  // Plant & Cat
  const plant = group(4.07, 0, 2.65);
  joinery.plant(plant);
  const cat = sub(scene, -3.55, 1.058, 1.22); cat.rotation.y = -.35;
  const catBody = box(cat, .52, 1, .34, 0, .1, 0, 0xad795a);
  catBody.scale.y = .20;
  box(cat, .24, .2, .22, -.26, .12, .08, 0x9a928a);
  box(cat, .2, .1, .16, -.2, .06, .16, 0xe8e0d0, {castShadow: false});
  const earL = box(cat, .06, .09, .045, -.33, .26, .05, 0x9a928a); earL.rotation.z = .35;
  const earR = box(cat, .06, .09, .045, -.2, .26, .12, 0x9a928a); earR.rotation.z = -.35;
  box(cat, .05, .012, .012, -.33, .14, .185, 0x5a544e, {castShadow: false});
  box(cat, .05, .012, .012, -.22, .14, .195, 0x5a544e, {castShadow: false});
  box(cat, .03, .02, .012, -.275, .1, .2, 0xd8a0a0, {castShadow: false});
  const tailA = box(cat, .3, .07, .07, .28, .06, .14, 0x9a928a); tailA.rotation.y = .3;
  const tailB = box(cat, .2, .07, .07, .42, .06, -.02, 0x9a928a); tailB.rotation.y = 1.2;
  box(cat, .12, .06, .07, .36, .06, -.16, 0xe8e0d0);

  // Dynamic room_design & keepsake layers
  const keepsakesGroup = group(0, 0, 0); keepsakesGroup.userData.keepSeparate = true;
  const displayNoteGroup = sub(desk, .48, 1.456, .30); displayNoteGroup.visible = false; displayNoteGroup.userData.keepSeparate = true;
  box(displayNoteGroup, .34, .012, .26, 0, 0, 0, 0xf9f3de, {castShadow: false});
  box(displayNoteGroup, .22, .005, .014, 0, .008, -.05, 0x988f76, {castShadow: false});
  box(displayNoteGroup, .18, .005, .014, -.02, .008, .02, 0x988f76, {castShadow: false});
  box(displayNoteGroup, .045, .016, .045, .11, .01, -.08, 0xd97d73, {castShadow: false});
  const roomSlotsGroup = group(0, 0, 0); roomSlotsGroup.userData.keepSeparate = true;
  for (const mesh of [catBody, earL, earR, tailA, tailB, ...curtains]) mesh.userData.keepSeparate = true;

  // Boot tray beside the doorway, outside the threshold and the rug.
  const bootTray=group(2.60,.145,3.21);
  box(bootTray,.65,.046,.48,0,.023,0,0x4f5557);
  for (const bx of [-.145,.12]) {
    box(bootTray,.16,.22,.16,bx,.16,-.075,0x835543);
    box(bootTray,.16,.09,.27,bx,.085,.01,0xb07952);
  }

  // Kitchen & Washstand
  const kitchen = group(-4.55, 0, 2.75);
  joinery.range(kitchen);
  const pot = sub(kitchen, .12, 1.03, -.3);
  const kettle=sub(kitchen,-.08,1.03,-.55);
  joinery.cookware(pot,kettle);
  box(kitchen,.32,.027,.44,.06,1.035,.32,0xc39367);
  for (const [x,z] of [[.10,.22],[.06,.30],[.12,.37]]) box(kitchen,.06,.045,.06,x,1.073,z,0xc56953);
  const burnerMaterial = new THREE.MeshStandardMaterial({color: 0xff9a5a, emissive: 0xff8a3d, emissiveIntensity: 1.6, roughness: .6});
  const cookFx = sub(kitchen, 0, 0, 0); cookFx.visible = false;
  box(cookFx, .15, .008, .15, .08, 1.048, -.2, 0xff9a5a, {material: burnerMaterial, castShadow: false});
  const potSteam = [0, 1, 2].map(i => {
    const puff = box(cookFx, .05, .1, .05, .12 + (i - 1) * .06, 1.25, -.3, 0xf4f2e8, {material: steamMaterial, castShadow: false});
    puff.userData.keepSeparate = true;
    return puff;
  });

  const washstand = group(-4.6, 0, -2.7);
  joinery.basin(washstand);
  const waterMaterial = new THREE.MeshStandardMaterial({color: 0xbfe0e4, transparent: true, opacity: .6, roughness: .2, depthWrite: false});
  const washFx = sub(washstand, 0, 0, 0); washFx.visible = false;
  const stream = box(washFx, .025, .12, .025, -.1, 1.0, 0, 0xbfe0e4, {material: waterMaterial, castShadow: false});
  stream.userData.keepSeparate = true;
  box(washFx, .3, .01, .38, .05, .95, 0, 0xbfe0e4, {material: waterMaterial, castShadow: false});

  const stool = sub(table,-1.23,0,.05);
  joinery.sideTable(table,stool);
  box(table, .42,.008,.34,-.53,.853,.08,0x739188,{castShadow:false});
  const mealSet=sub(table,-.53,.857,.08);mealSet.visible=false;mealSet.userData.keepSeparate=true;
  box(mealSet, .28, .02, .28, 0, .01, 0, 0xf4efdc);
  box(mealSet, .12, .03, .08, -.04, .035, -.03, 0xddcc91);
  box(mealSet, .08, .04, .08, .06, .04, .05, 0xdb9690);
  box(mealSet, .1, .12, .1, .02, .06, -.24, 0xefe7c8);
  box(mealSet, .08, .012, .08, .02, .115, -.24, 0x6b5b4a, {castShadow: false});
  const restingBroom = group(-4.12, .13, 3.68); restingBroom.rotation.z = .18;
  box(restingBroom, .034, 1.1, .034, 0, .62, 0, 0xa88d6f);
  box(restingBroom, .25, .04, .08, 0, .13, 0, 0x8a7a63);
  box(restingBroom, .27, .16, .07, 0, .06, 0, 0xddcc91);

  const garden = addCabinGarden({
    AdditiveBlending: THREE.AdditiveBlending, BoxGeometry: THREE.BoxGeometry, CanvasTexture: THREE.CanvasTexture,
    Color: THREE.Color, Euler: THREE.Euler, Group: THREE.Group, InstancedMesh: THREE.InstancedMesh,
    Matrix4: THREE.Matrix4, Mesh: THREE.Mesh, MeshBasicMaterial: THREE.MeshBasicMaterial,
    MeshStandardMaterial: THREE.MeshStandardMaterial, PlaneGeometry: THREE.PlaneGeometry,
    PointLight: THREE.PointLight, Quaternion: THREE.Quaternion, Vector3: THREE.Vector3,
  }, scene);

  // Soft contact shadows & corner AO
  const radialShadowTexture = () => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 64; const context = canvas.getContext('2d');
    const gradient = context.createRadialGradient(32, 32, 1, 32, 32, 32);
    gradient.addColorStop(0, 'rgba(255,255,255,1)'); gradient.addColorStop(.45, 'rgba(255,255,255,.5)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
    context.fillStyle = gradient; context.fillRect(0, 0, 64, 64);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture); return texture;
  };
  const linearAOTexture = () => {
    const canvas = document.createElement('canvas'); canvas.width = 16; canvas.height = 64; const context = canvas.getContext('2d');
    const gradient = context.createLinearGradient(0, 64, 0, 0);
    gradient.addColorStop(0, 'rgba(255,255,255,1)'); gradient.addColorStop(.42, 'rgba(255,255,255,.42)'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
    context.fillStyle = gradient; context.fillRect(0, 0, 16, 64);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture); return texture;
  };
  const shadowGeo = new THREE.PlaneGeometry(1, 1);
  geometries.set('__cshadow', shadowGeo);
  const fixedShadows = [[3.33,.145,1.8,2.6,1.9], [3.52,.145,-2.38,2.8,2], [4.07,.145,2.65,1.4,1.3],
    [2.60,.143,3.21,.84,.64], [-4.55,.145,2.75,1.3,2.1], [-4.6,.145,-2.7,1.1,1.3], [2.1,.145,1.85,.8,.8]];
  const movableShadows = [[bed,3.3,4.2], [desk,4.3,2.4], [chair,1.5,1.5]];
  const contactShadows = new THREE.InstancedMesh(shadowGeo, new THREE.MeshBasicMaterial({
    map: radialShadowTexture(), color: 0x2f3d2f, transparent: true, opacity: .5, depthWrite: false, toneMapped: false,
  }), fixedShadows.length + movableShadows.length);
  function setShadow(index, x, y, z, width, depth, yaw = 0) {
    const pose = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(-Math.PI / 2, yaw, 0, 'YXZ'));
    pose.scale(new THREE.Vector3(width, depth, 1)).setPosition(x, y, z);
    contactShadows.setMatrixAt(index, pose);
  }
  function syncFurnitureShadows() {
    movableShadows.forEach(([object, width, depth], i) => {
      setShadow(fixedShadows.length + i, object.position.x, .145, object.position.z, width, depth, object.rotation.y);
    });
    contactShadows.instanceMatrix.needsUpdate = true;
  }
  fixedShadows.forEach((row, i) => setShadow(i, ...row));
  syncFurnitureShadows();
  contactShadows.renderOrder = 1;
  contactShadows.frustumCulled = false;
  contactShadows.userData.keepSeparate = true;
  scene.add(contactShadows);
  const aoGeo = new THREE.PlaneGeometry(1, 1);
  geometries.set('__ao', aoGeo);
  const cornerAO = (() => {
    const seams = [
      [.05, .53, -3.612, 0, 0, 0, 9.85, .38], [.05, 3.4, -3.612, 0, 0, Math.PI, 9.85, .32],
      [-4.892, .53, .05, 0, Math.PI / 2, 0, 7.25, .38], [-4.892, 3.4, .05, 0, Math.PI / 2, Math.PI, 7.25, .32],
      [.05, .138, -3.22, -Math.PI / 2, 0, Math.PI, 9.85, .48], [-4.52, .138, .05, -Math.PI / 2, 0, -Math.PI / 2, 7.25, .48],
      [-4.65, 1.95, -3.61, 0, 0, -Math.PI / 2, 3.22, .48], [-4.89, 1.95, -3.37, 0, Math.PI / 2, Math.PI / 2, 3.22, .48],
      [.05, 1.21, -3.608, 0, 0, Math.PI, 2.36, .22], [-2.52, 2.31, -3.608, 0, 0, Math.PI, 1.62, .22],
    ];
    const mat = new THREE.MeshBasicMaterial({map: linearAOTexture(), color: 0x263327, transparent: true, opacity: .36, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, toneMapped: false});
    const mesh = new THREE.InstancedMesh(aoGeo, mat, seams.length);
    const euler = new THREE.Euler(), quat = new THREE.Quaternion(), pos = new THREE.Vector3(), scale = new THREE.Vector3(), m4 = new THREE.Matrix4();
    seams.forEach(([x, y, z, rx, ry, rz, sx, sy], idx) => {pos.set(x, y, z); euler.set(rx, ry, rz); quat.setFromEuler(euler); scale.set(sx, sy, 1); m4.compose(pos, quat, scale); mesh.setMatrixAt(idx, m4);});
    mesh.renderOrder = 1; mesh.castShadow = false; mesh.receiveShadow = false; mesh.frustumCulled = false; mesh.userData.keepSeparate = true; scene.add(mesh); return mesh;
  })();

  // Static batch baker (keeps movable furniture & animated doors/props in localRoots)
  const bakedBatches = [];
  const occluderMaterial = new THREE.MeshBasicMaterial({visible: false});
  function mergeLocalGroup(root) {
    for (const child of [...root.children]) if (child.isGroup && !child.userData.portalKey && !child.userData.keepSeparate) mergeLocalGroup(child);
    const buckets = new Map();
    for (const child of root.children) {
      if (!child.isMesh || child.isInstancedMesh || child.userData.keepSeparate) continue;
      const mat = child.material;
      if (!mat || Array.isArray(mat) || mat.transparent) continue;
      const key = mat.uuid + '|' + child.castShadow + '|' + child.receiveShadow;
      if (!buckets.has(key)) buckets.set(key, {material: mat, castShadow: child.castShadow, receiveShadow: child.receiveShadow, items: []});
      buckets.get(key).items.push(child);
    }
    for (const bucket of buckets.values()) {
      if (bucket.items.length < 2) continue;
      const parts = bucket.items.map(mesh => {mesh.updateMatrix(); return (mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry.clone()).applyMatrix4(mesh.matrix);});
      const merged = mergeGeometries(parts, false);
      for (const part of parts) part.dispose();
      if (!merged) continue;
      merged.computeBoundingSphere();
      const mesh = new THREE.Mesh(merged, bucket.material);
      mesh.castShadow = bucket.castShadow; mesh.receiveShadow = bucket.receiveShadow; mesh.userData.keepSeparate = true;
      for (const item of bucket.items) root.remove(item);
      root.add(mesh); bakedBatches.push(mesh);
    }
  }
  function bakeStatic() {
    const localRoots = [
      daySky, nightSky, motes, bed, desk, chair, lamp, sleepDetails, plant, cookFx, washFx,
      mealSet, restingBroom, cat, shelf, shelfStand, pictureDefaultArt, keepsakesGroup, displayNoteGroup,
      roomSlotsGroup, frontDoorPivot, cottageShell, cottageTrim, valley, windowGroup, kitchen, washstand, table, stool, rug, ...curtains,
    ];
    for (const prop of props.values()) localRoots.push(prop.group);
    const gardenRoot = scene.children.find(node => node.userData && node.userData.garden === true);
    for (const root of localRoots) mergeLocalGroup(root);
    const protectedRoots = [
      ...localRoots, windowSunPatch, picturePixelMesh, shelfVolumesGroup,
      memoryBookmark, learningMarker, particleMesh, contactShadows, cornerAO, gardenRoot,
    ].filter(Boolean);
    const skip = new Set();
    for (const root of protectedRoots) root.traverse(node => skip.add(node));
    const addOccluder = (w, h, d, x, y, z) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), occluderMaterial);
      mesh.position.set(x, y, z); mesh.visible = false; mesh.castShadow = false; mesh.receiveShadow = false; mesh.userData.keepSeparate = true;
      walls.add(mesh);
    };
    addOccluder(10.2, 3.5, .2, 0, 1.85, -3.72);
    addOccluder(.2, 3.5, 7.45, -5, 1.85, 0);
    scene.updateMatrixWorld(true);
    const buckets = new Map();
    scene.traverse(node => {
      if (!node.isMesh || node.isInstancedMesh || skip.has(node) || node.userData.keepSeparate) return;
      if (node.parent && node.parent.userData && node.parent.userData.worldAvatar) return;
      const mat = node.material;
      if (!mat || Array.isArray(mat) || mat.transparent || mat.visible === false) return;
      const key = mat.uuid + '|' + node.castShadow + '|' + node.receiveShadow;
      if (!buckets.has(key)) buckets.set(key, {material: mat, castShadow: node.castShadow, receiveShadow: node.receiveShadow, items: []});
      buckets.get(key).items.push(node);
    });
    for (const bucket of buckets.values()) {
      if (bucket.items.length < 2) continue;
      const parts = bucket.items.map(mesh => (mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry.clone()).applyMatrix4(mesh.matrixWorld));
      const merged = mergeGeometries(parts, false);
      for (const part of parts) part.dispose();
      if (!merged) continue;
      merged.computeBoundingSphere();
      const mesh = new THREE.Mesh(merged, bucket.material);
      mesh.castShadow = bucket.castShadow; mesh.receiveShadow = bucket.receiveShadow; mesh.matrixAutoUpdate = false; mesh.userData.keepSeparate = true;
      for (const item of bucket.items) if (item.parent) item.parent.remove(item);
      scene.add(mesh); bakedBatches.push(mesh);
    }
  }
  bakeStatic();
  const styles=createCabinStyles(THREE,scene,{cottageRoots:[cottageShell,cottageTrim,valley,garden.setting],
    anchors:{desk,window:windowGroup,sky:skyMaterial},paint:joinery.paint,planks,materials,textures,invalidate});
  garden.styleWeather=styles.weather;
  function placeFixedFurniture(plan) {
    for(const [object,transform] of [[kitchen,plan.kitchen],[washstand,plan.washstand],[table,plan.table],
      [wardrobe,plan.wardrobe],[plant,plan.plant],[rug,plan.rug],[windowGroup,plan.window]]) placeObject(object,transform);
    scene.updateMatrixWorld(true);
    const stoolPoint=stool.getWorldPosition(new THREE.Vector3());
    const positions=[plan.table,plan.wardrobe,plan.plant,null,plan.kitchen,plan.washstand,[stoolPoint.x,0,stoolPoint.z,plan.table[3]]];
    positions.forEach((tr,i)=>{if(tr){const [,y,,width,depth]=fixedShadows[i];setShadow(i,tr[0],y,tr[2],width,depth,tr[3]);}});
    contactShadows.instanceMatrix.needsUpdate=true;
  }

  return {
    styles,placeFixedFurniture,
    walls, windowGroup, windowSunPatch, daySky, nightSky, sunDisk, skyMaterial, starMaterial,
    curtains, motes, bed, sleepDetails, zzz, desk, chair, steamA, steamB, steamMaterial,
    lamp, bulbMaterial, warm, readingLight, fairyBulbMaterial, shelf, shelfStand, shelfVolumesGroup,
    pictureDefaultArt, picturePixelCanvas, picturePixelTex, picturePixelMesh,
    memoryBookmark, memoryBookmarkMat, learningMarker, learningMarkerMat,
    phone, screenMaterial, bubble, plant, cat, catBody, earL, earR, tailA, tailB,
    keepsakesGroup, displayNoteGroup, roomSlotsGroup, frontDoorPivot,
    kitchen, cookFx, potSteam, burnerMaterial, washstand, washFx, stream, waterMaterial,
    mealSet, restingBroom, garden, props, bakedBatches, contactShadows, syncFurnitureShadows, cornerAO,
    occluderMaterial, box, sub, materials, geometries, textures,
    getChatCompanionGlow: () => chatCompanionGlow,
    setChatCompanionGlow: v => {chatCompanionGlow = Boolean(v);},
  };
}
