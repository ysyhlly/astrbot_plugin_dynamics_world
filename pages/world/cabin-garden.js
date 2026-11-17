/* Detailed cottage garden; instanced botanical geometry and hand-built outdoor joinery. */
import {createGardenShapes,createGardenSurface} from './garden-craft.js';
export function addCabinGarden(THREE,scene){
 const garden=new THREE.Group();garden.name='Cottage garden';garden.userData.garden=true;scene.add(garden);
 const G=createGardenShapes(),materialCache=new Map(),textures=[];
 const colorMaterial=(color,extra={})=>{const key=JSON.stringify([color,extra]);if(!materialCache.has(key))materialCache.set(key,new THREE.MeshStandardMaterial({color,roughness:.94,...extra}));return materialCache.get(key);};
 const surface=(kind,color)=>{const s=createGardenSurface(THREE,kind,color);textures.push(s.texture);return s.material;};
 const timber=surface('wood',0xffffff),green=surface('ground',0xaabe99),earth=surface('ground',0x84705a),stoneMat=surface('ground',0xffffff),white=colorMaterial(0xffffff),metal=colorMaterial(0x596b61,{roughness:.55});
 const matrix=new THREE.Matrix4(),position=new THREE.Vector3(),rotation=new THREE.Euler(),scale=new THREE.Vector3(1,1,1),idleQuat=new THREE.Quaternion();
 function instances(name,geometry,material,rows,parent=garden,shadow=true){
  if(!rows.length)return null;
  const mesh=new THREE.InstancedMesh(geometry,material,rows.length);mesh.name=name;mesh.castShadow=shadow;mesh.receiveShadow=true;mesh.userData.garden=true;
  rows.forEach((r,i)=>{position.set(r.x,r.y,r.z);rotation.set(r.rx||0,r.ry||0,r.rz||0);scale.set(r.sx??1,r.sy??1,r.sz??1);matrix.compose(position,new THREE.Quaternion().setFromEuler(rotation),scale);mesh.setMatrixAt(i,matrix);if(r.color!==undefined)mesh.setColorAt(i,new THREE.Color(r.color));});
  mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;parent.add(mesh);return mesh;
 }
 const row=(x,y,z,sx,sy,sz,color,extra={})=>({x,y,z,sx,sy,sz,color,...extra});
 const block=(name,x,y,z,sx,sy,sz,mat,shadow=true)=>instances(name,G.timber,mat,[row(x,y,z,sx,sy,sz)],garden,shadow);
 function group(x=0,y=0,z=0,parent=garden){const g=new THREE.Group();g.position.set(x,y,z);g.userData.garden=true;g.userData.keepSeparate=true;parent.add(g);return g;}
 function beam(a,b,width,depth,color){const v=new THREE.Vector3(...b).sub(new THREE.Vector3(...a)),q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),v.clone().normalize()),e=new THREE.Euler().setFromQuaternion(q);return row((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2,width,v.length(),depth,color,{rx:e.x,ry:e.y,rz:e.z});}
 const glowCanvas=(()=>{const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d'),grad=g.createRadialGradient(32,32,1,32,32,32);grad.addColorStop(0,'rgba(255,255,255,1)');grad.addColorStop(.4,'rgba(255,255,255,.55)');grad.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=grad;g.fillRect(0,0,64,64);return new THREE.CanvasTexture(c);})();textures.push(glowCanvas);
 function glowPool(x,y,z,radius,color){const m=new THREE.MeshBasicMaterial({map:glowCanvas,color,transparent:true,opacity:0,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false,fog:false});const mesh=new THREE.Mesh(new THREE.PlaneGeometry(radius*2,radius*2),m);mesh.rotation.x=-Math.PI/2;mesh.position.set(x,y,z);mesh.userData.garden=true;garden.add(mesh);return mesh;}

 // Soft turf edge over a layered earth/stone foundation.
 block('Turf island',0,-.42,1.48,17.9,.32,14.7,green,false);
 block('Garden foundation',0,-.59,1.48,17.97,.17,14.77,colorMaterial(0x8c9378),false);
 const foundation=[];
 for(let i=0;i<26;i++)foundation.push(row(-8.62+i*.69,-.53,8.8,.67,.25,.16,[0xa49b85,0xb3a88e,0x939782][i%3]));
 for(const x of [-8.94,8.94])for(let i=0;i<21;i++)foundation.push(row(x,-.53,-5.52+i*.69,.16,.25,.67,[0xa49b85,0xb3a88e,0x939782][i%3]));
 instances('Foundation stone courses',G.soft,stoneMat,foundation,garden,false);
 const grassRows=[];
 for(let z=-5.35;z<8.4;z+=.55)for(let x=-8.55;x<8.6;x+=.6){
  if(Math.abs(x)<5.15&&z<4.15&&z> -4.1)continue;
  if(Math.abs(x)<1.55&&z>3.9)continue;
  if(Math.abs(Math.abs(x)-6.48)<1.5&&z>-2.6&&z<4.4)continue;
  if(Math.abs(Math.abs(x)-3.5)<1.6&&z>4.6&&z<7.6)continue;
  const i=Math.abs(Math.round(x*137+z*97));if(i%3===0)continue;
  const h=.1+(i%4)*.027;grassRows.push(row(x+Math.sin(i)*.15,-.26+h/2,z+Math.cos(i)*.12,.18,h,.18,[0x8ca37b,0xa6b58b,0x94ad81][i%3],{ry:i*.4}));
 }
 const grassMesh=instances('Individual grass tufts',G.grass,white,grassRows,garden,false);
 block('Stone entrance lower tread',0,-.2,4.13,3.15,.2,.74,colorMaterial(0xbdb49b));
 block('Stone entrance upper tread',0,-.07,3.78,2.72,.17,.58,colorMaterial(0xd9cfb6));
 const pathRows=[];
 for(let z=4.45,r=0;z<8.35;z+=.64,r++)for(let c=-1;c<=1;c++)pathRows.push(row(c*.77+(r%2)*.1,-.22,z,.73,.11,.58,[0xd4c8ae,0xc4bba2,0xded3ba][(r+c+4)%3],{ry:Math.sin(r*3+c)*.06}));
 instances('Dressed limestone path',G.soft,stoneMat,pathRows,garden,false);
 const smallStones=[];for(const side of [-1,1])for(let i=0;i<3;i++)smallStones.push(row(side*(1.91+i*.42),-.22,5.72+i*.23,.48,.1,.38,0xc8bea5,{ry:side*.25+i*.15}));
 instances('Pond and kitchen garden stepping stones',G.stone,stoneMat,smallStones,garden,false);

 // Raised beds with real long boards, end boards and iron fasteners.
 const bedTimber=[],bedNails=[],soilRidges=[];
 for(const cx of [-6.48,6.48]){
  block('Raised bed soil',cx,-.145,.83,2.6,.2,6.4,earth,false);
  for(const x of [cx-1.29,cx+1.29])for(const y of [-.12,.025])bedTimber.push(row(x,y,.83,.13,.135,6.54,0xb89a74));
  for(const z of [.83-3.2,.83+3.2])for(const y of [-.12,.025])bedTimber.push(row(cx,y,z,2.65,.135,.13,0xb89a74));
  for(const x of [cx-1.29,cx+1.29])for(const z of [-2.37,.83,4.03]){
   bedTimber.push(row(x,.035,z,.19,.44,.19,0x9d805e));
   for(const y of [-.08,.075])bedNails.push(row(x+(x<cx?-.1:.1),y,z,.025,.025,.025,0x58665a));
  }
  for(let n=0;n<85;n++){const x=cx+Math.sin(n*17.31)*1.13,z=.83+Math.cos(n*13.73)*3;soilRidges.push(row(x,-.043,z,.035+(n%4)*.017,.022,.045+(n%3)*.02,n%2?0xe5d9c4:0xffffff,{ry:n}));}
 }
 instances('Raised bed joinery',G.timber,timber,bedTimber);
 instances('Bed iron pegs',G.sphere,metal,bedNails,garden,false);
 instances('Loose garden topsoil',G.clod,earth,soilRidges,garden,false);
 const flowerGrowthGroup=group(0,-.04,0),flowerBlossomGroup=group(0,0,0,flowerGrowthGroup);
 const stemRows=[],leafRows=[],petalRows=[],flowerCenters=[],flowerColors=[0xd99e92,0xe6cd8c,0xeee8d4,0xb39db8,0xdcb49a];
 for(const [cx,side] of [[-6.48,0],[6.48,1]])for(let r=0;r<8;r++)for(let c=0;c<3;c++){
  const seed=side*193+r*19+c*7,x=cx+(c-1)*.71+Math.sin(seed*3)*.1,z=.83+(r-3.5)*.68+Math.cos(seed*5)*.12;
  const kind=seed%3,h=.42+(seed%5)*.065+(kind===2?.16:0),lean=Math.sin(seed)*.045;
  stemRows.push(beam([x,0,z],[x+lean,h,z],.027,.027,0x6b8861));
  for(const dir of [-1,1])leafRows.push(row(x+dir*.095,h*.42,z,.25,.045,.105,seed%2?0x87a273:0x779566,{rz:dir*.55,ry:dir*.3}));
  for(let p=0;p<3;p++){const a=p*Math.PI*2/3+seed;leafRows.push(row(x+Math.cos(a)*.055,.06,z+Math.sin(a)*.055,.2,.038,.08,0x8ca375,{ry:-a}));}
  const color=flowerColors[seed%5],hx=x+lean;
  if(kind===0){
   for(let p=0;p<7;p++){const a=p*Math.PI*2/7;petalRows.push(row(hx+Math.cos(a)*.085,h+.025,z+Math.sin(a)*.085,.14,.055,.085,color,{ry:-a,rz:.14*Math.cos(a)}));}
   flowerCenters.push(row(hx,h+.052,z,.09,.055,.09,0xc9a35a));
  }else if(kind===1){
   for(let p=0;p<5;p++){const a=p*Math.PI*2/5;petalRows.push(row(hx+Math.cos(a)*.047,h+.09,z+Math.sin(a)*.047,.085,.18,.07,color,{rx:.18*Math.sin(a),rz:-.18*Math.cos(a),ry:a}));}
  }else{
   for(let k=0;k<6;k++)for(let p=0;p<3;p++){const a=p*2.1+k*1.2;petalRows.push(row(hx+Math.cos(a)*.035,h+k*.052,z+Math.sin(a)*.035,.075-k*.005,.07,.07,0xa899ba,{ry:a}));}
  }
 }
 instances('Slender flower stems',G.stem,white,stemRows,flowerGrowthGroup,false);
 instances('Flower lanceolate leaves',G.leaf,white,leafRows,flowerGrowthGroup,false);
 const petalMesh=instances('Daisies tulips and lavender',G.sphere,white,petalRows,flowerBlossomGroup,false);
 instances('Daisy seed heads',G.sphere,white,flowerCenters,flowerBlossomGroup,false);

 // Natural oval pond: faceted stone bank, oval pads, petalled waterlily and circular ripples.
 const pondX=-3.5,pondZ=6.35;
 block('Pond basin',pondX,-.2,pondZ,2.4,.18,1.6,earth,false);
 const waterMaterial=colorMaterial(0x7fa9a1,{roughness:.28,metalness:.07,emissive:0x3f6f6a,emissiveIntensity:.12});
 instances('Oval pond water',G.cylinder,waterMaterial,[row(pondX,-.095,pondZ,2.35,.08,1.52)],garden,false);
 const rimRows=[];for(let i=0;i<18;i++){const a=i*Math.PI*2/18;rimRows.push(row(pondX+Math.cos(a)*1.2,-.07,pondZ+Math.sin(a)*.8,.38,.22+(i%3)*.025,.34,[0xc8bfa7,0xb4af98,0xd6cab0][i%3],{ry:a+.2,rz:Math.sin(i)*.12}));}
 instances('Natural pond bank stones',G.stone,stoneMat,rimRows);
 const pads=[[-.5,-.2,.34],[.45,.25,.29],[.1,-.35,.25]];
 instances('Notched lily pads',G.pad,white,pads.map(([x,z,s],i)=>row(pondX+x,-.045,pondZ+z,s,.018,s,0x6c916c,{ry:i*1.6})),garden,false);
 const lotus=[];for(let i=0;i<7;i++){const a=i*Math.PI*2/7;lotus.push(row(pondX-.5+Math.cos(a)*.055,.006,pondZ-.2+Math.sin(a)*.055,.12,.055,.065,0xe7b6bd,{ry:-a,rz:.3*Math.cos(a)}));}
 lotus.push(row(pondX-.5,.037,pondZ-.2,.055,.04,.055,0xe9cd8d));instances('Waterlily petals',G.sphere,white,lotus,garden,false);
 instances('Pond surface rings',G.ring,colorMaterial(0xb4d0c5,{roughness:.4}),pads.slice(0,2).map(([x,z,s])=>row(pondX+x,-.05,pondZ+z,s*1.6,s*1.6,.22,undefined,{rx:Math.PI/2})),garden,false);
 const fish=[];for(const [x,z,a,c] of [[.15,.05,.4,0xd5a174],[-.2,.3,-.6,0xc77d6e]]){
  fish.push(row(pondX+x,-.052,pondZ+z,.18,.024,.065,c,{ry:a}),row(pondX+x-.09*Math.cos(a),-.052,pondZ+z+.09*Math.sin(a),.075,.02,.07,0xeee2c9,{ry:a}));
 }
 instances('Pond koi',G.leaf,white,fish,garden,false);
 const reedRows=[],reedHeads=[];for(const [dx,dz,h] of [[0,0,.52],[.12,.08,.44],[-.08,.1,.6]]){
  reedRows.push(row(pondX+1+dx,-.06+h/2,pondZ-.55+dz,.025,h,.025,0x6f8b60));
  reedHeads.push(row(pondX+1+dx,h,pondZ-.55+dz,.055,.17,.055,0x8c7153));
 }
 instances('Pond reeds',G.stem,white,reedRows,garden,false);instances('Reed seed heads',G.sphere,white,reedHeads,garden,false);
 instances('Pond frog',G.sphere,white,[row(pondX+.45,0,pondZ+.25,.15,.09,.12,0x7b9b70),row(pondX+.41,.06,pondZ+.29,.032,.035,.035,0xe9e6ca),row(pondX+.49,.06,pondZ+.29,.032,.035,.035,0xe9e6ca)],garden,false);
 const moonShimmer=instances('Pond moon shimmer',G.sphere,colorMaterial(0xe8e9d0,{emissive:0xe8e9d0,emissiveIntensity:.8}),[row(pondX-.3,-.047,pondZ+.1,.55,.005,.14)],garden,false);moonShimmer.visible=false;

 const vegX=3.5,vegZ=6.35;
 block('Kitchen garden soil',vegX,-.16,vegZ,2.3,.17,1.5,earth,false);
 instances('Kitchen garden timber rim',G.timber,timber,[row(vegX-1.15,-.08,vegZ,.09,.21,1.6,0xb29570),row(vegX+1.15,-.08,vegZ,.09,.21,1.6,0xb29570),row(vegX,-.08,vegZ-.75,2.4,.21,.09,0xb29570),row(vegX,-.08,vegZ+.75,2.4,.21,.09,0xb29570)]);
 const vegGrowthGroup=group(vegX,-.04,vegZ),vegFruitGroup=group(0,0,0,vegGrowthGroup),cropRows=[];
 for(let r=0;r<3;r++)for(let c=0;c<4;c++){
  if(r===2&&c===3)continue;const x=-.75+c*.5,z=-.45+r*.45;
  cropRows.push(row(x,.08,z,.21,.19,.21,0x9eb483));
  for(let p=0;p<6;p++){const a=p*Math.PI/3;cropRows.push(row(x+Math.cos(a)*.07,.06,z+Math.sin(a)*.07,.19,.11,.12,p%2?0x7d9c6c:0x8da778,{ry:-a,rz:.25*Math.cos(a)}));}
 }
 instances('Layered cabbage rosettes',G.leaf,white,cropRows,vegGrowthGroup,false);
 const pumpkins=[];for(let p=0;p<9;p++){const a=p*Math.PI*2/9;pumpkins.push(row(.78+Math.cos(a)*.075,.1,.47+Math.sin(a)*.075,.16,.25,.16,p%2?0xc99562:0xdbac74));}
 instances('Ribbed pumpkin',G.sphere,white,pumpkins,vegFruitGroup);instances('Pumpkin stalk',G.stem,white,[row(.78,.26,.47,.045,.12,.04,0x75845a,{rz:.2})],vegFruitGroup);
 instances('Wood bucket',G.pot,timber,[row(4.9,-.12,5,.25,.25,.25,0xb39770)]);
 instances('Bucket iron bands',G.tubeRing,metal,[row(4.9,-.21,5,.205,.205,.13,undefined,{rx:Math.PI/2}),row(4.9,-.01,5,.26,.26,.13,undefined,{rx:Math.PI/2})]);
 instances('Bucket handle',G.ring,metal,[row(4.9,.08,5,.22,.24,.3)],garden,false);
 const sunStems=[],sunLeaves=[],sunPetals=[],sunHeads=[];
 for(const [x,z,h] of [[7.55,6.75,1.2],[7.85,6.15,1.03]]){
  sunStems.push(row(x,-.26+h/2,z,.038,h,.038,0x6b855d));sunLeaves.push(row(x-.13,h*.45-.26,z,.3,.055,.17,0x87a372,{rz:.45}));
  for(let p=0;p<12;p++){const a=p*Math.PI/6;sunPetals.push(row(x+Math.cos(a)*.14,h-.21+Math.sin(a)*.14,z,.17,.07,.045,0xe4c375,{rz:a}));}
  sunHeads.push(row(x,h-.21,z+.02,.19,.19,.065,0x8b6c4c));
 }
 instances('Sunflower stalks',G.stem,white,sunStems);instances('Sunflower leaves',G.leaf,white,sunLeaves,garden,false);instances('Sunflower petals',G.leaf,white,sunPetals,garden,false);instances('Sunflower seed discs',G.sphere,white,sunHeads,garden,false);

 // Pointed pickets, mortised posts, rail caps, iron fixings; clear central entrance.
 const pickets=[],rails=[],posts=[],postCaps=[],fasteners=[],zPath=7.35;
 function fenceRun(from,to,z){for(let x=from;x<=to;x+=.39){pickets.push(row(x,.205,z,.13,.93,.095,0xe5ddc5));fasteners.push(row(x,.51,z+.06,.025,.025,.018,0x8b927c));}const len=to-from+.14;for(const y of [.51,.12])rails.push(row((from+to)/2,y,z-.065,len,.1,.12,y>.3?0xddd3b8:0xa3ae8b));}
 fenceRun(-8.3,8.3,-5.16);fenceRun(-8.3,-1.55,zPath);fenceRun(1.55,8.3,zPath);
 for(const x of [-8.3,8.3]){
  for(let z=-5.16;z<=7.35;z+=.39)pickets.push(row(x,.205,z,.13,.93,.095,0xe5ddc5,{ry:Math.PI/2}));
  for(const y of [.51,.12])rails.push(row(x,y,1.095,.12,.1,12.65,y>.3?0xddd3b8:0xa3ae8b));
 }
 for(const [x,z] of [[-8.3,-5.16],[8.3,-5.16],[-8.3,7.35],[8.3,7.35],[-4.9,7.35],[4.9,7.35],[-8.3,1.1],[8.3,1.1]]){
  posts.push(row(x,.27,z,.2,1.06,.2,0xd4c5a5));postCaps.push(row(x,.84,z,.29,.13,.29,0xc1a786));
 }
 instances('Pointed garden pickets',G.picket,timber,pickets);instances('Fence horizontal rails',G.timber,timber,rails);instances('Fence posts',G.timber,timber,posts);instances('Chamfered fence post caps',G.cone,timber,postCaps);instances('Fence fixings',G.sphere,metal,fasteners,garden,false);

 // Double-post rose arbor with a segmented curved lintel and side lattice panels.
 const arborWood=[],archRows=[],arborMetal=[];
 for(const x of [-1.52,1.52])for(const z of [6.76,7.08]){
  arborWood.push(row(x,1.2,z,.14,2.92,.14,0xa18563));arborWood.push(row(x,-.15,z,.2,.2,.2,0x7d8269));
  arborMetal.push(row(x,.02,z,.155,.06,.155,0x596b61));
 }
 for(const z of [6.74,7.1])for(let i=0;i<16;i++){
  const x=-1.69+i*3.38/16,xx=x+3.38/16,y=2.67+.36*Math.sin((x+1.69)/3.38*Math.PI),yy=2.67+.36*Math.sin((xx+1.69)/3.38*Math.PI);
  archRows.push(beam([x,y,z],[xx,yy,z],.155,.13,0xb59a73));
 }
 for(let i=0;i<9;i++){const x=-1.65+i*.4125,y=2.73+.36*Math.sin(i/8*Math.PI);arborWood.push(row(x,y,6.92,.1,.09,.68,0xc0a47b));}
 for(const x of [-1.52,1.52]){
  for(let y=.28;y<2.3;y+=.3)arborWood.push(row(x,y,6.92,.075,.045,.54,0xc3ad85));
  for(const z of [6.65,6.92,7.19])arborWood.push(row(x,1.25,z,.05,2.13,.05,0x9b9372));
 }
 instances('Rose arbor oak joinery',G.timber,timber,arborWood);instances('Curved arbor beams',G.timber,timber,archRows);instances('Arbor post shoes',G.soft,metal,arborMetal);
 const vineStems=[],arborVines=[],vineBlossoms=[];
 for(const side of [-1,1]){
  let prev=[side*1.56,-.2,6.75];
  for(let n=0;n<22;n++){
   const t=n/21,x=side*(1.55-.35*Math.max(0,t-.7))+Math.sin(n*.8)*.07,y=.05+t*2.83,z=6.71+Math.cos(n*.75)*.13;
   vineStems.push(beam(prev,[x,y,z],.022,.022,0x76805a));prev=[x,y,z];
   for(const d of [-1,1])arborVines.push(row(x+d*.09,y-.04,z,.25,.065,.14,[0x7c976d,0x92a879,0x6f8a61][n%3],{rz:d*.5,ry:n*.5}));
   if(n%4===1)for(let p=0;p<6;p++){const a=p*Math.PI/3;vineBlossoms.push(row(x+Math.cos(a)*.065,y+Math.sin(a)*.065,z-.035,.115,.09,.075,p%2?0xdbb6a5:0xe6c5b1,{rz:a}));}
  }
 }
 for(let n=0;n<13;n++){const x=-1.25+n*.21,y=2.89+.14*Math.cos(x);arborVines.push(row(x,y,6.89,.29,.09,.18,0x8da579,{ry:n*.4,rz:.2*Math.sin(n)}));}
 instances('Rose climbing stems',G.stem,white,vineStems);instances('Rose leaves',G.leaf,white,arborVines,garden,false);
 const vineBlossomMesh=instances('Layered climbing rose petals',G.sphere,white,vineBlossoms,garden,false);
 const arborLanternMaterial=colorMaterial(0xf0dab0,{emissive:0xffd99e,emissiveIntensity:.15,roughness:.6});
 const lanternFrames=[],lanternCaps=[],lanternGlass=[],lanternFeet=[];
 function lantern(x,y,z,s=1){
  lanternGlass.push(row(x,y,z,.2*s,.24*s,.2*s));
  for(const dx of [-.112,.112])for(const dz of [-.112,.112])lanternFrames.push(row(x+dx*s,y,z+dz*s,.025*s,.29*s,.025*s));
  lanternCaps.push(row(x,y+.205*s,z,.33*s,.15*s,.33*s));lanternFeet.push(row(x,y-.15*s,z,.27*s,.045*s,.27*s));
 }
 lantern(0,2.47,6.92,.9);instances('Arbor lantern chain',G.ring,metal,[row(0,2.82,6.92,.085,.11,.25),row(0,2.88,6.92,.06,.09,.25,undefined,{ry:Math.PI/2})]);
 const arborGlow=glowPool(0,-.13,6.92,1.55,0xffd99e),lanternLights=[];
 for(const x of [-2.08,2.08]){
  lantern(x,.77,5.68);lanternFrames.push(row(x,.15,5.68,.065,.8,.065));lanternFeet.push(row(x,-.22,5.68,.24,.08,.24));
  const light=new THREE.PointLight(0xffd99e,.65,3.4,2);light.position.set(x,.9,5.68);light.userData.garden=true;garden.add(light);lanternLights.push(light);
 }
 instances('Garden lantern glass',G.soft,arborLanternMaterial,lanternGlass);instances('Lantern wrought iron frames',G.timber,metal,lanternFrames);instances('Lantern hipped roofs',G.cone,metal,lanternCaps);instances('Lantern bases',G.soft,metal,lanternFeet);

 // Rounded mail cabinet with its original independent flag pivot.
 const mailboxGroup=group(1.88,-.22,6.96);
 instances('Mailbox oak post',G.timber,timber,[row(0,.42,0,.12,.84,.12,0xa98d68),row(0,.86,0,.29,.055,.4,0xc4aa82)],mailboxGroup);
 instances('Mailbox enamel body',G.soft,colorMaterial(0x819b88,{roughness:.65}),[row(0,1.01,0,.31,.26,.41)],mailboxGroup);
 instances('Mailbox curved lid',G.cylinder,colorMaterial(0x91aa95,{roughness:.6}),[row(0,1.115,0,.31,.42,.22,undefined,{rx:Math.PI/2})],mailboxGroup);
 instances('Mailbox fittings',G.soft,white,[row(0,1.02,.213,.21,.023,.015,0x40564a),row(0,.957,.218,.13,.045,.016,0xdfcba0)],mailboxGroup,false);
 const mailFlagPivot=group(.17,1.02,.04,mailboxGroup);mailFlagPivot.rotation.x=Math.PI/2;
 const mailFlagMat=colorMaterial(0xca7768,{emissive:0xd96b62,emissiveIntensity:.18,roughness:.7});
 instances('Mailbox flag',G.soft,mailFlagMat,[row(0,.09,0,.022,.18,.022),row(0,.16,.035,.025,.07,.09)],mailFlagPivot);
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
   crownRows.push(row(x+dx,top+.18,z+dz,1.15+(b%2)*.2,1.08,1.12,[0x7d9e70,0x91ac7b,0xa1b989,0x708f64][b%4],{ry:a,choice:b%4}));
  }
  crownRows.push(row(x,3.55,z,1.35,1.35,1.3,0x8ea979,{choice:1,ry:n*.8}));
  for(let b=0;b<4;b++){const a=b*Math.PI/2+.6;smallLeaves.push(row(x+Math.cos(a)*1.01,2.86+Math.sin(b)*.3,z+Math.sin(a)*.88,.6,.62,.6,0xadc092,{ry:a}));}
 }
 instances('Tapered tree trunks',G.stem,timber,trunkRows);instances('Orchard tree branches',G.stem,timber,branchRows);
 const crownMesh=instances('Faceted orchard canopy',G.crown,colorMaterial(0xffffff,{flatShading:true}),crownRows),crownHighlightMesh=instances('Orchard canopy tips',G.crown,colorMaterial(0xffffff,{flatShading:true}),smallLeaves);

 // Slatted benches with four legs, bracing and discrete upholstered seat pads.
 const benchWood=[],benchMetal=[],benchCushions=[];
 for(const [x,z] of [[-3.4,5.05],[3.4,5.05]]){
  for(let i=0;i<4;i++)benchWood.push(row(x,.38,z-.22+i*.145,1.63,.075,.12,0xb89a72));
  for(let i=0;i<4;i++)benchWood.push(row(x,.7+i*.16,z-.29,1.63,.115,.08,0xb49870,{rx:-.12}));
  for(const dx of [-.65,.65]){
   for(const dz of [-.2,.2])benchWood.push(beam([x+dx*1.06,-.25,z+dz*1.2],[x+dx,.38,z+dz],.09,.09,0x8c795d));
   benchWood.push(beam([x+dx,.35,z-.23],[x+dx,1.28,z-.33],.085,.085,0x8c795d));
   benchWood.push(row(x+dx,.65,z,.105,.08,.62,0xc4a67c));benchWood.push(row(x+dx,.52,z+.21,.065,.28,.065,0x8c795d));
   for(const yy of [.72,1.18])benchMetal.push(row(x+dx,yy,z-.245,.025,.025,.014,0x5e6c5b));
  }
  benchWood.push(row(x,.04,z,1.35,.07,.08,0x8c795d));
  for(const dx of [-.38,.38])benchCushions.push(row(x+dx,.46,z+.015,.7,.095,.46,x<0?0xaf9da2:0x9eac8b));
 }
 instances('Slatted oak garden benches',G.timber,timber,benchWood);instances('Bench brass screws',G.sphere,metal,benchMetal,garden,false);instances('Outdoor linen seat cushions',G.soft,white,benchCushions);

 const mushroomStems=[],mushroomCaps=[];for(const [x,z] of [[-1.35,4.75],[1.4,5.5],[-1.4,6.6],[1.35,7]]){mushroomStems.push(row(x,-.17,z,.055,.18,.055,0xe6d8bc));mushroomCaps.push(row(x,-.073,z,.21,.1,.21));}
 instances('Mushroom lamp stems',G.stem,white,mushroomStems);
 const mushroomCapMaterial=colorMaterial(0xca9585,{emissive:0xdb9690,emissiveIntensity:.05,roughness:.7});instances('Mushroom lamp caps',G.sphere,mushroomCapMaterial,mushroomCaps);
 const cloverRows=[];for(const [x,z] of [[-4.8,4.7],[-2.6,4.6],[2.5,4.55],[4.9,4.75],[-5.6,5.2],[5.5,5.3],[-2.2,7],[-4.9,7.1],[4.8,7.15],[-7.9,5.5],[7.9,5.6]]){
  for(let p=0;p<5;p++){const a=p*Math.PI*2/5;cloverRows.push(row(x+Math.cos(a)*.035,-.21,z+Math.sin(a)*.035,.07,.025,.04,0xece3ca,{ry:-a}));}
  cloverRows.push(row(x,-.19,z,.025,.022,.025,0xe5c580));
 }
 instances('Wild lawn daisies',G.sphere,white,cloverRows,garden,false);
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

 const rainRipples=group(pondX,-.047,pondZ);rainRipples.visible=false;
 const splashRings=[[-.35,-.12],[.32,.18],[-.05,.28],[.52,-.22]].map(([x,z])=>{
  const g=group(x,0,z,rainRipples);instances('Pond rain ring',G.ring,colorMaterial(0xcfe4e0,{roughness:.3}),[row(0,0,0,.22,.22,.12,undefined,{rx:Math.PI/2})],g,false);return g;
 });
 for(const [x,y,z] of [[3.32,-.115,-.75],[3.66,-.115,.65],[4.28,-.115,-.18],[3.12,-.115,-1.55]]){
  const g=group(x,y,z,rainRipples);instances('Path rain ring',G.ring,colorMaterial(0xbcd1cf,{roughness:.28}),[row(0,0,0,.18,.18,.1,undefined,{rx:Math.PI/2})],g,false);splashRings.push(g);
 }
 const snowGroup=group();snowGroup.visible=false;
 const snowRows=[row(0,.58,-5.16,16.7,.045,.18),row(-4.92,.58,zPath,6.86,.045,.18),row(4.92,.58,zPath,6.86,.045,.18),row(-8.3,.58,1.1,.18,.045,12.65),row(8.3,.58,1.1,.18,.045,12.65),row(-3.4,1.25,4.76,1.6,.055,.1),row(3.4,1.25,4.76,1.6,.055,.1)];
 for(let i=0;i<9;i++){const x=-1.65+i*.4125,y=2.79+.36*Math.sin(i/8*Math.PI);snowRows.push(row(x,y,6.92,.13,.035,.68));}
 instances('Snow resting on joinery',G.soft,colorMaterial(0xf0f3f1),snowRows,snowGroup,false);
 const snowLobes=[];for(const r of crownRows)snowLobes.push(row(r.x,r.y+r.sy*.36,r.z,r.sx*.76,.2,r.sz*.75));
 for(const [x,z,w,d] of [[-5.6,5.9,1.5,1.2],[5.8,6.3,1.6,1.1],[-1.9,4.9,.95,.8],[2.1,6.6,1.1,.85]])snowLobes.push(row(x,-.235,z,w,.05,d));
 instances('Soft canopy snow and lawn drifts',G.sphere,colorMaterial(0xf0f3f1),snowLobes,snowGroup,false);
 garden.updateMatrixWorld(true);
 const bounds={minX:-8.99,maxX:8.99,minY:-.68,maxY:4.24,minZ:-5.88,maxZ:8.86};

 let lanternLevel=0,windLevel=0,weatherKind='clear',seasonKey='spring',unopenedMail=0;
 const SEASON_CROWNS={
  spring:[0x7ca274,0x8fb081,0xa7c492,0x74966c],
  summer:[0x658f61,0x739e6d,0x85ad7c,0x5a8057],
  autumn:[0xc48b57,0xd1a163,0xa67a54,0x8c9668],
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
 return {bounds,
  diagnostics(){return {revision:'garden.1',season:seasonKey,weather:weatherKind,mail:unopenedMail,flagAngle:mailFlagPivot.rotation.x,flowersVisible:flowerBlossomGroup.visible,flowerScale:flowerGrowthGroup.scale.y,fruitVisible:vegFruitGroup.visible,snow:snowGroup.visible,rain:rainRipples.visible,fireflies:fireflies.visible,lantern:lanternLevel,trees:crownRows.length,flowerHeads:48};},
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
    const ac=new THREE.Color(season.accent_hex);
    for(let i=0;i<vineBlossoms.length;i++)vineBlossomMesh.setColorAt(i,ac);
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
    vegGrowthGroup.scale.set(.85,.44,.85);
    vegFruitGroup.visible=false;
   }else if(vgStage==='growing'){
    vegGrowthGroup.scale.set(.94,.76,.94);
    vegFruitGroup.visible=true;
    vegFruitGroup.scale.set(.68,.68,.68);
   }else{
    vegGrowthGroup.scale.set(1.04,1.08,1.04);
    vegFruitGroup.visible=true;
    vegFruitGroup.scale.set(1.06,1.06,1.06);
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
