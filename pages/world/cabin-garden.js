/* Detailed cottage garden; instanced botanical geometry and hand-built outdoor joinery. */
import {createGardenShapes,createGardenSurface} from './garden-craft.js';
import {buildGardenLandscape} from './garden-landscape.js';
export function addCabinGarden(THREE,scene){
 const garden=new THREE.Group();garden.name='Cottage garden';garden.userData.garden=true;scene.add(garden);
 const setting=new THREE.Group();setting.name='Cottage landscape';garden.add(setting);
 const G=createGardenShapes(),materialCache=new Map(),textures=[];
 const colorMaterial=(color,extra={})=>{const key=JSON.stringify([color,extra]);if(!materialCache.has(key))materialCache.set(key,new THREE.MeshStandardMaterial({color,roughness:.94,...extra}));return materialCache.get(key);};
 const surface=(kind,color)=>{const s=createGardenSurface(THREE,kind,color);textures.push(s.texture);return s.material;};
 const timber=surface('wood',0xffffff),green=surface('ground',0x84a075),earth=surface('ground',0x80634c),stoneMat=surface('ground',0xffffff),white=colorMaterial(0xffffff),metal=colorMaterial(0x596b61,{roughness:.55});
 green.map.repeat.set(9,7);
 const matrix=new THREE.Matrix4(),position=new THREE.Vector3(),rotation=new THREE.Euler(),scale=new THREE.Vector3(1,1,1),idleQuat=new THREE.Quaternion();
 function instances(name,geometry,material,rows,parent=garden,shadow=true){
  if(!rows.length)return null;
  const mesh=new THREE.InstancedMesh(geometry,material,rows.length);mesh.name=name;mesh.castShadow=shadow;mesh.receiveShadow=true;mesh.userData.garden=true;
  rows.forEach((r,i)=>{position.set(r.x,r.y,r.z);rotation.set(r.rx||0,r.ry||0,r.rz||0);scale.set(r.sx??1,r.sy??1,r.sz??1);matrix.compose(position,new THREE.Quaternion().setFromEuler(rotation),scale);mesh.setMatrixAt(i,matrix);if(r.color!==undefined)mesh.setColorAt(i,new THREE.Color(r.color));});
  mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;parent.add(mesh);return mesh;
 }
 const settingMesh=(name,geo,mat,rows,shadow=true)=>instances(name,geo,mat,rows,setting,shadow);
 const row=(x,y,z,sx,sy,sz,color,extra={})=>({x,y,z,sx,sy,sz,color,...extra});
 const block=(name,x,y,z,sx,sy,sz,mat,shadow=true,parent=garden)=>instances(name,G.timber,mat,[row(x,y,z,sx,sy,sz)],parent,shadow);
 function group(x=0,y=0,z=0,parent=garden){const g=new THREE.Group();g.position.set(x,y,z);g.userData.garden=true;g.userData.keepSeparate=true;parent.add(g);return g;}
 function beam(a,b,width,depth,color){const v=new THREE.Vector3(...b).sub(new THREE.Vector3(...a)),q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),v.clone().normalize()),e=new THREE.Euler().setFromQuaternion(q);return row((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2,width,v.length(),depth,color,{rx:e.x,ry:e.y,rz:e.z});}
 const glowCanvas=(()=>{const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d'),grad=g.createRadialGradient(32,32,1,32,32,32);grad.addColorStop(0,'rgba(255,255,255,1)');grad.addColorStop(.4,'rgba(255,255,255,.55)');grad.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=grad;g.fillRect(0,0,64,64);return new THREE.CanvasTexture(c);})();textures.push(glowCanvas);
 function glowPool(x,y,z,radius,color){const m=new THREE.MeshBasicMaterial({map:glowCanvas,color,transparent:true,opacity:0,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,fog:false});const mesh=new THREE.Mesh(new THREE.PlaneGeometry(radius*2,radius*2),m);mesh.rotation.x=-Math.PI/2;mesh.position.set(x,y,z);mesh.userData.garden=true;garden.add(mesh);return mesh;}

 // A sod lip and offset stone courses frame the cut earth along the two visible sides.
 block('Turf island',0,-.42,1.48,17.9,.32,14.7,green,false,setting);
 block('Garden subsoil',0,-.575,1.48,17.98,.22,14.78,colorMaterial(0x857b68),false,setting);
 const foundation=[];
 for(let level=0;level<2;level++){
  const y=-.64+level*.145;
  for(const [front,length] of [[true,17.94],[false,14.73]]) {
   const lo=-length/2,hi=length/2;
   for(let edge=lo-level*.31,i=0;edge<hi;edge+=.67,i++){
    const left=Math.max(edge,lo),right=Math.min(edge+.64,hi),span=right-left;
    if(span<=0)continue;
    const mid=(left+right)/2,color=[0x998c80,0xad9b88,0x9b9687,0xb3a38e][(i+level)%4];
    if(front) foundation.push(row(mid,y,8.85,span,.127,.15,color));
    else for(const sign of [-1,1]) foundation.push(row(sign*8.96,y,mid+1.48,.15,.127,span,color));
   }
  }
 }
 settingMesh('Cut garden masonry',G.voxel,stoneMat,foundation,false);
 const grassRows=[];
 for(let z=-5.35;z<8.4;z+=.55)for(let x=-8.55;x<8.6;x+=.6){
  if(Math.abs(x)<5.15&&z<4.15&&z> -4.1)continue;
  if(Math.abs(x)<1.55&&z>3.9)continue;
  if(Math.abs(Math.abs(x)-6.48)<1.5&&z>-2.6&&z<4.4)continue;
  if(Math.abs(Math.abs(x)-3.5)<1.6&&z>4.6&&z<7.6)continue;
  const i=Math.abs(Math.round(x*137+z*97));if(i%3===0)continue;
  const h=.1+(i%4)*.027;grassRows.push(row(x+Math.sin(i)*.15,-.26+h/2,z+Math.cos(i)*.12,.18,h,.18,[0x8ca37b,0xa6b58b,0x94ad81][i%3],{ry:i*.4}));
 }
 const grassMesh=settingMesh('Individual grass tufts',G.grass,white,grassRows,false);
 const {flowerGrowthGroup,flowerBlossomGroup,flowerHeads,vegGrowthGroup,vegFruitGroup,
  pondX,pondZ,waterMaterial,moonShimmer,moveFish}=buildGardenLandscape({G,instances,row,group,beam,garden,white,colorMaterial,earth});
 const sunStems=[],sunLeaves=[],sunPetals=[],sunHeads=[];
 for(const [x,z,h] of [[7.55,6.75,1.2],[7.85,6.15,1.03]]){
  sunStems.push(row(x,-.26+h/2,z,.038,h,.038,0x6b855d));sunLeaves.push(row(x-.13,h*.45-.26,z,.3,.055,.17,0x87a372,{rz:.45}));
  for(let p=0;p<12;p++){const a=p*Math.PI/6;sunPetals.push(row(x+Math.cos(a)*.14,h-.21+Math.sin(a)*.14,z,.17,.07,.045,0xe4c375,{rz:a}));}
  sunHeads.push(row(x,h-.21,z+.02,.19,.19,.065,0x8b6c4c));
 }
 instances('Sunflower stalks',G.stem,white,sunStems);instances('Sunflower leaves',G.leaf,white,sunLeaves,garden,false);instances('Sunflower petals',G.leaf,white,sunPetals,garden,false);instances('Sunflower seed discs',G.sphere,white,sunHeads,garden,false);

 // Pointed pickets, mortised posts, rail caps, iron fixings; clear central entrance.
 const pickets=[],rails=[],posts=[],postCaps=[],fasteners=[],frontSnow=[],zPath=7.35;
 function fenceRun(from,to,z,low=false) {
  const height=low?.45:.93,railY=low?.075:.51;
  for(let x=from+.08;x<=to;x+=.39){
   pickets.push(row(x,-.26+height/2,z,.13,height,.095,0xddcbb0));
   fasteners.push(row(x,railY,z+.055,.026,.026,.019,0x8b927c));
  }
  const len=to-from;
  rails.push(row((from+to)/2,railY,z-.065,len,.087,.12,low?0xbe9a75:0xd8c7a6),
    row((from+to)/2,low?-.15:.12,z-.065,len,.075,.12,0x8d9a7c));
  if(z===zPath)frontSnow.push(row((from+to)/2,railY+.061,z-.065,len,.034,.13));
 }
 fenceRun(-8.3,8.3,-5.16);
 for(const side of [-1,1]){
  for(const [inner,outer,low] of [[1.55,2.18,false],[2.18,5.55,true],[5.55,8.30,false]]){
   fenceRun(Math.min(side*inner,side*outer),Math.max(side*inner,side*outer),zPath,low);
  }
 }
 for(const x of [-8.3,8.3]){
  for(let z=-5.16;z<=7.35;z+=.39)pickets.push(row(x,.205,z,.13,.93,.095,0xddcbb0,{ry:Math.PI/2}));
  for(const y of [.51,.12])rails.push(row(x,y,1.095,.12,.1,12.65,y>.3?0xddd3b8:0xa3ae8b));
 }
 for(const [x,z] of [[-8.3,-5.16],[8.3,-5.16],[-8.3,7.35],[8.3,7.35],[-5.55,7.35],[5.55,7.35],[-8.3,1.1],[8.3,1.1]]){
  posts.push(row(x,.27,z,.2,1.06,.2,0xd4c5a5));postCaps.push(row(x,.84,z,.29,.13,.29,0x628680));
 }
 settingMesh('Pointed garden pickets',G.picket,timber,pickets);settingMesh('Fence horizontal rails',G.timber,timber,rails);settingMesh('Fence posts',G.timber,timber,posts);settingMesh('Painted fence post caps',G.voxel,timber,postCaps);settingMesh('Fence fixings',G.sphere,metal,fasteners,false);

 // Rose arbor: a stepped timber header, slate cap and a trellis on either side.
 const arborWood=[],archRows=[],arborMetal=[];
 for(const x of [-1.52,1.52])for(const z of [6.76,7.08]){
  arborWood.push(row(x,1.2,z,.14,2.92,.14,0xa18563));arborWood.push(row(x,-.15,z,.2,.2,.2,0x7d8269));
  arborMetal.push(row(x,.02,z,.155,.06,.155,0x596b61));
 }
 for(const z of [6.74,7.10]){
  archRows.push(row(0,2.67,z,3.42,.17,.15,0x835748));
  for(const side of [-1,1]) archRows.push(beam([side*1.48,2.23,z],[side*1.05,2.65,z],.12,.13,0xab7856));
 }
 // Open rafters leave the pond visible from the indoor camera; outer cheeks
 // carry slate and the wisteria, the middle rafter carries the lantern.
 for(let i=0;i<7;i++){
  const x=(i-3)*.48,lift=(3-Math.abs(i-3))*.105;
  arborWood.push(row(x,2.81+lift,6.92,.12,.15,.88,0xad7952));
  if(i<2||i>4) archRows.push(row(x,2.89+lift,6.92,.33,.09,.80,i%2?0x496b77:0x617f83));
 }
 for(const sign of [-1,1]){
  archRows.push(beam([sign*1.60,2.76,6.72],[0,3.14,6.72],.10,.13,0x855648));
  archRows.push(beam([sign*1.60,2.76,7.10],[0,3.14,7.10],.10,.13,0x855648));
 }
 for(const x of [-1.52,1.52]){
  for(let y=.28;y<2.3;y+=.3)arborWood.push(row(x,y,6.92,.075,.045,.54,0xc3ad85));
  for(const z of [6.65,6.92,7.19])arborWood.push(row(x,1.25,z,.05,2.13,.05,0x9b9372));
 }
 settingMesh('Rose arbor oak joinery',G.timber,timber,arborWood);settingMesh('Arbor braces and slate cap',G.timber,timber,archRows);settingMesh('Arbor post shoes',G.soft,metal,arborMetal);
 const vineStems=[],arborVines=[],vineBlossoms=[];
 for(const side of [-1,1]){
  let prev=[side*1.56,-.20,6.69];
  for(let i=0;i<18;i++){
   const t=i/17,x=side*(1.53-.04*Math.sin(i*.85)),y=-.10+t*2.86,z=6.73+.06*Math.cos(i);
   vineStems.push(beam(prev,[x,y,z],.047,.047,0x675d49));
   prev=[x,y,z];
   for(const dir of [-1,1])arborVines.push(row(x+dir*.078,y+.04,z,.17,.12,.115,i%3?0x688b65:0x8b9c71));
  }
  for(let i=0;i<6;i++){
   const x=side*(1.44-i*.215),y=2.91+i*.047,z=i%2?7.09:6.74;
   arborVines.push(row(x,y+.04,z,.37,.115,.25,i%3?0x6a885f:0x839c6d));
   if(i===5)continue;
   const count=i%2?3:4;
   for(let j=0;j<count;j++){
    const w=.18-.035*j;
    vineBlossoms.push(row(x+.018*Math.sin(j),y-.08-j*.103,z+.09,w,.135,w*.82,[0x8a719e,0xa185ab,0xbea1c3,0xd2b3ca][j]));
   }
  }
 }
 settingMesh('Wisteria woody vines',G.timber,white,vineStems);
 settingMesh('Wisteria leaves',G.voxel,white,arborVines,false);
 const vineBlossomMesh=settingMesh('Hanging wisteria racemes',G.voxel,white,vineBlossoms,false);
 const arborLanternMaterial=colorMaterial(0xf0dab0,{emissive:0xffd99e,emissiveIntensity:.15,roughness:.6});
 const lanternFrames=[],lanternCaps=[],lanternGlass=[],lanternFeet=[];
 function lantern(x,y,z,s=1){
  lanternGlass.push(row(x,y,z,.2*s,.24*s,.2*s));
  for(const dx of [-.112,.112])for(const dz of [-.112,.112])lanternFrames.push(row(x+dx*s,y,z+dz*s,.025*s,.29*s,.025*s));
  lanternCaps.push(row(x,y+.205*s,z,.33*s,.15*s,.33*s));lanternFeet.push(row(x,y-.15*s,z,.27*s,.045*s,.27*s));
 }
 lantern(0,2.54,6.92,1.15);instances('Arbor lantern hanger',G.voxel,metal,[row(0,2.94,6.92,.034,.39,.034)]);
 const arborGlow=glowPool(0,-.13,6.92,1.55,0xffd99e),lanternLights=[];
 for(const x of [-2.08,2.08]){
  lantern(x,.77,5.68);lanternFrames.push(row(x,.15,5.68,.065,.8,.065));lanternFeet.push(row(x,-.22,5.68,.24,.08,.24));
  const light=new THREE.PointLight(0xffd99e,.65,3.4,2);light.position.set(x,.9,5.68);light.userData.garden=true;garden.add(light);lanternLights.push(light);
 }
 instances('Garden lantern glass',G.soft,arborLanternMaterial,lanternGlass);instances('Lantern wrought iron frames',G.timber,metal,lanternFrames);instances('Lantern hipped roofs',G.cone,metal,lanternCaps);instances('Lantern bases',G.soft,metal,lanternFeet);

 // The letterbox keeps its independently animated flag outside the painted case.
 const mailboxGroup=group(1.88,-.22,6.96);
 instances('Letterbox post and footing',G.voxel,white,[
  row(0,.43,0,.15,.88,.15,0x91664b),row(0,.085,0,.29,.17,.27,0xa99c85),
  row(0,.86,0,.48,.075,.49,0xc19360),row(0,.75,.06,.11,.18,.23,0x805746)],mailboxGroup);
 instances('Painted postbox, stepped cap and envelope brasswork',G.voxel,white,[
  row(0,1.064,0,.42,.34,.43,0x356b70),row(0,1.26,0,.50,.075,.51,0x3c5266),
  row(0,1.32,0,.38,.065,.42,0x597b80),row(0,1.37,0,.26,.050,.35,0x6c8a82),
  row(0,1.15,.226,.30,.041,.025,0x393a40),row(0,1.182,.23,.32,.027,.032,0xd2ac72),
  row(0,.99,.226,.18,.083,.025,0xe4c895),row(0,1.008,.242,.104,.018,.012,0x987150)],mailboxGroup);
 const mailFlagPivot=group(.241,1.05,.04,mailboxGroup);mailFlagPivot.rotation.x=Math.PI/2;
 const mailFlagMat=colorMaterial(0xcb7056,{emissive:0xdf7557,emissiveIntensity:.18,roughness:.7});
 instances('Mailbox flag',G.voxel,mailFlagMat,[row(0,.12,0,.034,.24,.035),row(0,.216,.058,.039,.106,.145)],mailFlagPivot);
 const gateSignpost=group(-1.86,-.22,6.92);
 instances('Wayfinding oak post',G.timber,timber,[row(0,.66,0,.11,1.32,.11,0x9c805c),row(0,1.34,0,.16,.07,.16,0xc0a47a),row(.18,1.14,.03,.57,.16,.06,0xc4a47a,{ry:.12}),row(-.17,.92,-.02,.53,.15,.06,0x8fa189,{ry:-.18})],gateSignpost);
 instances('Wayfinding arrow points',G.picket,timber,[row(.49,1.14,.07,.15,.15,.05,0xc4a47a,{rz:-Math.PI/2,ry:.12}),row(-.46,.92,-.065,.14,.14,.05,0x8fa189,{rz:Math.PI/2,ry:-.18})],gateSignpost);
 instances('Wayfinding carved marks',G.timber,white,[row(.18,1.14,.075,.19,.016,.008,0xe9dbc1),row(-.17,.92,.02,.16,.016,.008,0xe5ddbf)],gateSignpost,false);

 // Branching orchard trees, irregular faceted crown lobes, smaller exposed tips.
 const trunkRows=[],branchRows=[],crownRows=[],smallLeaves=[];
 for(const [n,x,z] of [[0,-7.36,-3.88],[1,7.36,-3.84]]){
  trunkRows.push(row(x,1.0,z,.31,2.52,.31,n?0x927456:0xa28465,{rz:n?.035:-.035}));
  for(let b=0;b<6;b++){
   const a=b*Math.PI/3+.3*n,dx=Math.cos(a)*.69,dz=Math.sin(a)*.58,top=2.7+(b%2)*.3;
   branchRows.push(beam([x,1.45,z],[x+dx,top,z+dz],.13,.13,0x9a7c5c));
   crownRows.push(row(x+dx,top+.18,z+dz,1.15+(b%2)*.2,1.08,1.12,[0x7d9e70,0x91ac7b,0xa1b989,0x708f64][b%4],{ry:(b%4)*Math.PI/2,choice:b%4}));
  }
  crownRows.push(row(x,3.55,z,1.35,1.35,1.3,0x8ea979,{choice:1,ry:n*Math.PI/2}));
  for(let b=0;b<4;b++){const a=b*Math.PI/2+.6;smallLeaves.push(row(x+Math.cos(a)*1.01,2.86+Math.sin(b)*.3,z+Math.sin(a)*.88,.6,.62,.6,0xadc092,{ry:b*Math.PI/2}));}
 }
 settingMesh('Tapered tree trunks',G.stem,timber,trunkRows);settingMesh('Orchard tree branches',G.stem,timber,branchRows);
 const springFlowers=group(0,0,0,setting),orchardFruit=group(0,0,0,setting),fallenLeaves=group(0,0,0,setting);
 const blossomRows=[],fruitRows=[],fallenRows=[];
 for(const [n,x,z] of [[0,-7.36,-3.88],[1,7.36,-3.84]]){
  for(let i=0;i<14;i++){
   const a=i*Math.PI*2/14+n*.35,rx=x+Math.cos(a)*(1.21+(i%3)*.05),rz=z+Math.sin(a)*(1.17+(i%2)*.06);
   const y=2.84+.14*(i%4);
   for(const [dx,dz] of [[-.07,0],[.07,0],[0,-.07],[0,.07]])
    blossomRows.push(row(rx+dx,y,rz+dz,.145,.095,.145,i%3?0xf6c8aa:0xedb2b4));
   blossomRows.push(row(rx,y+.045,rz,.056,.055,.056,0xeab879));
   fruitRows.push(row(rx,y-.18,rz,.19,.17,.18,i%3?0xc46a4f:0xe1984e));
   fruitRows.push(row(rx+.02,y-.07,rz,.037,.065,.034,0x825947));
   fallenRows.push(row(x+Math.sin(i*2.3)*1.08,-.24,z+Math.cos(i*1.5)*.83,.15,.028,.085,i%2?0xb08454:0xc8955a,{ry:i*.5}));
  }
 }
 instances('Spring orchard blossom',G.voxel,white,blossomRows,springFlowers,false);
 instances('Orchard apples',G.voxel,white,fruitRows,orchardFruit,false);
 instances('Fallen orchard leaves',G.voxel,white,fallenRows,fallenLeaves,false);
 orchardFruit.visible=fallenLeaves.visible=false;
 const crownMesh=settingMesh('Faceted orchard canopy',G.crown,colorMaterial(0xffffff,{flatShading:true}),crownRows),crownHighlightMesh=settingMesh('Orchard canopy tips',G.crown,colorMaterial(0xffffff,{flatShading:true}),smallLeaves);

 // Slatted benches with four legs, bracing and discrete upholstered seat pads.
 const benchWood=[],benchMetal=[],benchCushions=[];
 for(const [x,z] of [[-3.4,5.05],[3.4,5.05]]){
  for(let i=0;i<4;i++)benchWood.push(row(x,.38,z-.22+i*.145,1.63,.075,.12,0xb37d54));
  for(let i=0;i<4;i++)benchWood.push(row(x,.7+i*.16,z-.29,1.63,.115,.08,0x5c8076,{rx:-.12}));
  for(const dx of [-.65,.65]){
   for(const dz of [-.2,.2])benchWood.push(beam([x+dx*1.06,-.25,z+dz*1.2],[x+dx,.38,z+dz],.09,.09,0x8c795d));
   benchWood.push(beam([x+dx,.35,z-.23],[x+dx,1.28,z-.33],.085,.085,0x8c795d));
   benchWood.push(row(x+dx,.65,z,.105,.08,.62,0xc4a67c));benchWood.push(row(x+dx,.52,z+.21,.065,.28,.065,0x8c795d));
   for(const yy of [.72,1.18])benchMetal.push(row(x+dx,yy,z-.245,.025,.025,.014,0x5e6c5b));
  }
  benchWood.push(row(x,.04,z,1.35,.07,.08,0x8c795d));
  for(const dx of [-.38,.38])benchCushions.push(row(x+dx,.46,z+.015,.7,.095,.46,x<0?0xbd7768:0x77a097));
 }
 for(const [x,z] of [[-3.4,5.05],[3.4,5.05]]){
  benchWood.push(row(x,1.22,z-.28,1.72,.077,.13,0xd3a577));
  for(const side of [-1,1])benchCushions.push(row(x+side*.38,.514,z+.10,.69,.012,.052,0xe2c493));
 }
 instances('Slatted oak garden benches',G.timber,timber,benchWood);instances('Bench brass screws',G.sphere,metal,benchMetal,garden,false);instances('Outdoor linen seat cushions',G.soft,white,benchCushions);

 const mushroomStems=[],mushroomCaps=[];for(const [x,z] of [[-1.35,4.75],[1.4,5.5],[-1.4,6.6],[1.35,7]]){mushroomStems.push(row(x,-.17,z,.055,.18,.055,0xe6d8bc));mushroomCaps.push(row(x,-.073,z,.21,.1,.21));}
 settingMesh('Mushroom lamp stems',G.stem,white,mushroomStems);
 const mushroomCapMaterial=colorMaterial(0xca9585,{emissive:0xdb9690,emissiveIntensity:.05,roughness:.7});settingMesh('Mushroom lamp caps',G.sphere,mushroomCapMaterial,mushroomCaps);
 const cloverRows=[];for(const [x,z] of [[-4.8,4.7],[-2.6,4.6],[2.5,4.55],[4.9,4.75],[-5.6,5.2],[5.5,5.3],[-2.2,7],[-4.9,7.1],[4.8,7.15],[-7.9,5.5],[7.9,5.6]]){
  for(let p=0;p<5;p++){const a=p*Math.PI*2/5;cloverRows.push(row(x+Math.cos(a)*.035,-.21,z+Math.sin(a)*.035,.07,.025,.04,0xece3ca,{ry:-a}));}
  cloverRows.push(row(x,-.19,z,.025,.022,.025,0xe5c580));
 }
 settingMesh('Wild lawn daisies',G.sphere,white,cloverRows,false);
 instances('Watering can body',G.pot,colorMaterial(0x8da58a,{roughness:.65}),[row(-6,-.11,4.35,.29,.26,.23)]);
 instances('Watering can spout',G.stem,colorMaterial(0x8da58a,{roughness:.65}),[beam([-6.1,-.1,4.35],[-6.35,.08,4.35],.055,.055,0xffffff)]);
 instances('Watering can handle',G.tubeRing,metal,[row(-5.87,-.055,4.35,.2,.23,.22)],garden,false);
 instances('Watering can rose',G.cylinder,metal,[row(-6.36,.09,4.35,.12,.035,.12,undefined,{rz:1})]);
 const butterflies=group(),butterflyRows=[];
 for(const [x,y,z,c] of [[-6.3,.95,1.5,0xe7e3d0],[6.5,.9,2.2,0xe4b7a6],[-3.2,.85,6,0xf0d3da]]){
  butterflyRows.push(row(x-.045,y,z,.1,.02,.11,c,{rz:.5}),row(x+.045,y,z,.1,.02,.11,c,{rz:-.5}),row(x,y,z,.025,.025,.12,0x806848));
 }
 instances('Garden butterflies',G.leaf,white,butterflyRows,butterflies,false);
 const fireflies=group();fireflies.visible=false;const fireflyRows=[];
 for(const [x,y,z] of [[-6.2,.7,2.4],[-6.8,.9,.2],[-5.9,.6,-1.4],[6.3,.8,1.8],[6.9,.6,-.6],[5.8,.9,3],[-3.1,.7,6.1],[-4.2,.9,6.6],[3.4,.7,6.2],[4.3,.9,6.7],[.8,.8,5.2],[-1.2,.9,6.9]])fireflyRows.push(row(x,y,z,.038,.038,.038));
 const fireflyMesh=instances('Garden fireflies',G.sphere,colorMaterial(0xf2d8a0,{emissive:0xf2d8a0,emissiveIntensity:2.4,roughness:.6}),fireflyRows,fireflies,false);

 // T-post clothesline with curved linens, clothespins and a woven hamper.
 const lineX=-6.65,lineZ1=4.85,lineZ2=6.55,lineY=1.24,lineMid=(lineZ1+lineZ2)/2;
 instances('Clothesline oak posts',G.timber,timber,[row(lineX,.52,lineZ1,.1,1.56,.1,0xa78c68),row(lineX,.52,lineZ2,.1,1.56,.1,0xa78c68),row(lineX,1.29,lineZ1,.4,.07,.1,0xc4a77e),row(lineX,1.29,lineZ2,.4,.07,.1,0xc4a77e)]);
 instances('Clothesline rope',G.stem,white,[beam([lineX,lineY,lineZ1],[lineX,lineY,lineZ2],.014,.014,0xd8d3bb)],garden,false);
 const laundryHanger=group(lineX,lineY,lineMid);
 instances('Breeze folded linens',G.cloth,white,[row(0,-.25,-.48,.4,.48,.6,0xede4cd,{ry:Math.PI/2}),row(0,-.22,.05,.31,.42,.6,0x9db399,{ry:Math.PI/2}),row(0,-.18,.53,.28,.34,.6,0xd6ada0,{ry:Math.PI/2})],laundryHanger);
 instances('Linen hems',G.timber,white,[row(0,-.47,-.48,.04,.025,.4,0xcac5ad),row(0,-.39,.05,.04,.025,.31,0xe9dfc4)],laundryHanger,false);
 instances('Wood clothespins',G.timber,timber,[-.62,-.34,-.05,.15,.44,.62].map(z=>row(0,.015,z,.045,.09,.025,0xbc9d73)),laundryHanger,false);
 instances('Laundry hamper',G.pot,timber,[row(lineX+.4,-.13,lineZ1+.1,.42,.27,.34,0xbb9d75)]);
 const weave=[];for(let n=0;n<5;n++)weave.push(row(lineX+.4,-.23+n*.05,lineZ1+.1,.36+n*.015,.29+n*.012,.16,0x927957,{rx:Math.PI/2}));
 instances('Hamper woven bands',G.tubeRing,timber,weave,garden,false);
 instances('Hamper folded linen',G.soft,colorMaterial(0xe6dec8),[row(lineX+.4,.014,lineZ1+.1,.34,.055,.26)]);

 const rainRipples=group(pondX,-.170,pondZ);rainRipples.visible=false;
 const splashRings=[[-.35,-.12],[.32,.18],[-.05,.28],[.52,-.22]].map(([x,z])=>{
  const g=group(x,0,z,rainRipples);instances('Pond rain ring',G.ring,colorMaterial(0xcfe4e0,{roughness:.3}),[row(0,0,0,.22,.22,.12,undefined,{rx:Math.PI/2})],g,false);return g;
 });
 for(const [x,y,z] of [[3.32,.012,-.75],[3.66,.012,.65],[4.28,.012,-.18],[4.10,.012,-1.65]]){
  const g=group(x,y,z,rainRipples);instances('Path rain ring',G.ring,colorMaterial(0xbcd1cf,{roughness:.28}),[row(0,0,0,.18,.18,.1,undefined,{rx:Math.PI/2})],g,false);splashRings.push(g);
 }
 const snowGroup=group(0,0,0,setting);snowGroup.visible=false;
 const snowRows=[row(0,.58,-5.16,16.7,.045,.18),...frontSnow,row(-8.3,.58,1.1,.18,.045,12.65),row(8.3,.58,1.1,.18,.045,12.65),row(-3.4,1.25,4.76,1.6,.055,.1),row(3.4,1.25,4.76,1.6,.055,.1)];
 for(let i=0;i<7;i++){
  const x=(i-3)*.48,lift=(3-Math.abs(i-3))*.105,covered=i<2||i>4;
  snowRows.push(row(x,(covered?2.955:2.902)+lift,6.92,covered?.31:.115,.038,covered?.79:.86));
 }
 snowRows.push(row(1.88,1.182,6.96,.25,.034,.34),row(7.15,.532,5.43,.70,.03,1.55));
 instances('Snow resting on joinery',G.soft,colorMaterial(0xf0f3f1),snowRows,snowGroup,false);
 const snowLobes=[];for(const r of crownRows)snowLobes.push(row(r.x,r.y+r.sy*.36,r.z,r.sx*.76,.2,r.sz*.75));
 for(const [x,z,w,d] of [[-5.6,5.9,1.5,1.2],[5.8,6.3,1.6,1.1],[-1.9,4.9,.95,.8],[2.1,6.6,1.1,.85]])snowLobes.push(row(x,-.235,z,w,.05,d));
 instances('Soft canopy snow and lawn drifts',G.sphere,colorMaterial(0xf0f3f1),snowLobes,snowGroup,false);
 garden.updateMatrixWorld(true);
 const bounds={minX:-8.99,maxX:8.99,minY:-.68,maxY:4.24,minZ:-5.88,maxZ:8.86};

 let lanternLevel=0,windLevel=0,weatherKind='clear',seasonKey='spring',unopenedMail=0;
 const SEASON_CROWNS={
  spring:[0x588569,0x729c70,0x95b17b,0x467767],
  summer:[0x477960,0x5d9166,0x83a56b,0x38685a],
  autumn:[0xc07846,0xd4964f,0xa55f45,0x898851],
  winter:[0x7e9485,0x8da193,0x9fb0a3,0x6e8375],
 };
 function applyAtmosphere(nightFlag,lantern,firefly,butterfly){
  lanternLevel=lantern;
  for(let i=0;i<lanternLights.length;i++)lanternLights[i].intensity=.5+1.7*lantern;
  arborGlow.material.opacity=.7*lantern;
  arborLanternMaterial.emissiveIntensity=.15+1.45*lantern;
  mushroomCapMaterial.emissiveIntensity=.05+.75*lantern;
  waterMaterial.emissive.set(nightFlag?0x2c4a63:0x3f6f6a);waterMaterial.emissiveIntensity=.12+.18*lantern;
  moonShimmer.visible=nightFlag&&weatherKind!=='rain'&&weatherKind!=='snow';
  fireflies.visible=(firefly||seasonKey==='summer'&&nightFlag)&&weatherKind!=='rain'&&weatherKind!=='snow';
  butterflies.visible=butterfly&&weatherKind!=='rain'&&weatherKind!=='snow'&&seasonKey!=='winter';
  rainRipples.visible=weatherKind==='rain';
  snowGroup.visible=weatherKind==='snow'||seasonKey==='winter'&&weatherKind==='fog';
 }
 return {bounds,setting,
  diagnostics(){return {revision:'cottage-garden.2',season:seasonKey,weather:weatherKind,mail:unopenedMail,flagAngle:mailFlagPivot.rotation.x,flowersVisible:flowerBlossomGroup.visible,flowerScale:flowerGrowthGroup.scale.y,fruitVisible:vegFruitGroup.visible,snow:snowGroup.visible,rain:rainRipples.visible,fireflies:fireflies.visible,lantern:lanternLevel,trees:crownRows.length,flowerHeads,koi:2,orchardBlossoms:springFlowers.visible,orchardFruit:orchardFruit.visible};},
  dispose(){for(const geometry of new Set(Object.values(G)))geometry.dispose();for(const texture of textures)texture.dispose();},
  setNight(value){const night=!!value;applyAtmosphere(night,night?1:0,night,!night);},
  setAtmosphere(state={}){
   const night=!!state.night;
   weatherKind=state.weather||'clear';
   windLevel=Math.max(0,Math.min(2,Number(state.wind)||0));
   const lantern=Number.isFinite(state.lantern)?Math.max(0,Math.min(1,state.lantern)):(night?1:0);
   const firefly=state.firefly!==undefined?!!state.firefly:night;
   const butterfly=state.butterfly!==undefined?!!state.butterfly:!night;
   applyAtmosphere(night,lantern,firefly,butterfly);
  },
  setSeason(season={}){
   const nextKey=season?.season||seasonKey;
   if(!['spring','summer','autumn','winter'].includes(nextKey))return;
   seasonKey=nextKey;
   springFlowers.visible=seasonKey==='spring';
   orchardFruit.visible=seasonKey==='summer'||seasonKey==='autumn';
   fallenLeaves.visible=seasonKey==='autumn';
   vineBlossomMesh.visible=seasonKey!=='winter';
   if(season.lawn_hex)green.color.set(season.lawn_hex);
   const shades=SEASON_CROWNS[seasonKey]||SEASON_CROWNS.spring;
   if(crownMesh){
    const tmp=new THREE.Color();
    crownRows.forEach((r,idx)=>{crownMesh.setColorAt(idx,tmp.set(shades[r.choice%shades.length]));});
    if(crownMesh.instanceColor)crownMesh.instanceColor.needsUpdate=true;
   }
   if(crownHighlightMesh){
    const hi=new THREE.Color(season.foliage_hex||shades[2]);
    for(let i=0;i<smallLeaves.length;i++)crownHighlightMesh.setColorAt(i,hi);
    if(crownHighlightMesh.instanceColor)crownHighlightMesh.instanceColor.needsUpdate=true;
   }
   if(vineBlossomMesh&&season.accent_hex){
    const ac=new THREE.Color(season.accent_hex),base=new THREE.Color();
    for(let i=0;i<vineBlossoms.length;i++)vineBlossomMesh.setColorAt(i,base.set(vineBlossoms[i].color).lerp(ac,.35));
    if(vineBlossomMesh.instanceColor)vineBlossomMesh.instanceColor.needsUpdate=true;
   }
   if(grassMesh){
    const gc=new THREE.Color(seasonKey==='autumn'?0xb7b382:seasonKey==='winter'?0xa3b3a2:0x9fb996);
    for(let i=0;i<grassRows.length;i++)if(i%2===0)grassMesh.setColorAt(i,gc);
    if(grassMesh.instanceColor)grassMesh.instanceColor.needsUpdate=true;
   }
  },
  setEcology(eco={}){
   const flStage=eco?.flowerbed?.stage||'blooming';
   if(flStage==='seedling'){
    flowerGrowthGroup.scale.set(1,.46,1);
    flowerBlossomGroup.visible=false;
   }else if(flStage==='growing'){
    flowerGrowthGroup.scale.set(1,.78,1);
    flowerBlossomGroup.visible=true;
    flowerBlossomGroup.scale.set(1,1,1);
   }else{
    flowerGrowthGroup.scale.set(1,1.06,1);
    flowerBlossomGroup.visible=true;
    flowerBlossomGroup.scale.set(1,1,1);
   }
   const vgStage=eco?.veg_patch?.stage||eco?.vegetable_patch?.stage||'ripe';
   if(vgStage==='seedling'){
    vegGrowthGroup.scale.set(1,.44,1);
    vegFruitGroup.visible=false;
   }else if(vgStage==='growing'){
    vegGrowthGroup.scale.set(1,.76,1);
    vegFruitGroup.visible=true;
    vegFruitGroup.scale.set(1,1,1);
   }else{
    vegGrowthGroup.scale.set(1,1.08,1);
    vegFruitGroup.visible=true;
    vegFruitGroup.scale.set(1,1,1);
   }
  },
  setMailbox(mailbox={}){
   unopenedMail=Math.max(0,Number(mailbox?.unopened_count)||0);
   mailFlagPivot.rotation.x=unopenedMail>0?0:Math.PI/2;
   mailFlagMat.emissiveIntensity=unopenedMail>0?.48:.1;
  },
  tick(t,night,m=1){
   const base=.5+1.7*lanternLevel;
   for(let i=0;i<lanternLights.length;i++)lanternLights[i].intensity=base*(1+m*.12*Math.sin(t*2.7+i*1.7));
   arborGlow.material.opacity=(.7*lanternLevel)*(1+m*.14*Math.sin(t*2.2));
   mushroomCapMaterial.emissiveIntensity=(.05+.75*lanternLevel)*(1+m*.15*Math.sin(t*2.5+1));
  },
  idle(t,night,m=1){
   moveFish(t,Math.min(1,m));
   if(butterflies.visible){butterflies.position.y=Math.sin(t*1.4)*.08*m;butterflies.position.x=Math.sin(t*.6)*.15*m;}
   if(fireflies.visible&&fireflyMesh){for(let i=0;i<fireflyRows.length;i++){const r=fireflyRows[i];position.set(r.x+Math.sin(t*.7+i)*.25*m,r.y+Math.sin(t*1.1+i*1.7)*.18*m,r.z+Math.cos(t*.5+i)*.25*m);scale.set(r.sx,r.sy,r.sz);matrix.compose(position,idleQuat,scale);fireflyMesh.setMatrixAt(i,matrix);}fireflyMesh.instanceMatrix.needsUpdate=true;}
   const breeze=(1+windLevel*.75)*m;
   laundryHanger.rotation.z=Math.sin(t*1.35)*.055*breeze+Math.sin(t*2.9+.7)*.018*breeze;
   if(unopenedMail>0)mailFlagPivot.rotation.z=Math.sin(t*4.2)*.09*m;
   else mailFlagPivot.rotation.z=0;
   if(rainRipples.visible){for(let i=0;i<splashRings.length;i++){const phase=(t*1.6+i*.27)%1;const s=.45+phase*1.15;splashRings[i].scale.set(s,1,s);}}
   waterMaterial.emissiveIntensity=(.12+.18*lanternLevel)*(1+.25*Math.sin(t*1.7)*m);
  }};
}
