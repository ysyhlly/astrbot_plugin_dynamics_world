/* Continuous solar-arc lighting, indoor floor sunbeam, live weather and rainy-day doorway umbrella. */
import {BoxGeometry,Color,DynamicDrawUsage,Euler,Group,InstancedMesh,Matrix4,Mesh,MeshBasicMaterial,MeshStandardMaterial,Quaternion,Vector3} from 'three';

import {SHELTER} from './cabin-shelter.js';

const PHASES={
 night:{
  sunPos:[-5.5,8.5,4.5],sunColor:0xa8c2e0,sun:1.2,
  hemiSky:0x6e859c,hemiGround:0x324339,hemi:1.0,
  fillColor:0x6d8cab,fill:.42,
  warm:5.0,bulb:1.6,fairy:2.4,star:2.2,
  sky:0x526f85,skyEmissive:0x2c4a63,skyEmissiveInt:.18,
  fog:0x1d2b23,lantern:1.0,night:1,
 },
 dawn:{
  sunPos:[7.6,5.3,5.8],sunColor:0xffcfa6,sun:2.45,
  hemiSky:0xf6e2d2,hemiGround:0x7a8a73,hemi:1.58,
  fillColor:0xb8cde0,fill:.62,
  warm:3.55,bulb:.48,fairy:.85,star:0,
  sky:0xe8cfc0,skyEmissive:0xc99682,skyEmissiveInt:.28,
  fog:0xebe3d8,lantern:.35,night:0,
 },
 day:{
  sunPos:[0,11.2,5.6],sunColor:0xffe3b0,sun:3.35,
  hemiSky:0xf3f5df,hemiGround:0x76876e,hemi:1.95,
  fillColor:0xa9c4d8,fill:.68,
  warm:3.1,bulb:.15,fairy:.3,star:0,
  sky:0xbddbd3,skyEmissive:0x739f9c,skyEmissiveInt:.3,
  fog:0xe9eee0,lantern:0,night:0,
 },
 dusk:{
  sunPos:[-9.2,4.7,5.4],sunColor:0xff9d5c,sun:2.75,
  hemiSky:0xf2c59e,hemiGround:0x6c6d5a,hemi:1.42,
  fillColor:0x8ea4c8,fill:.55,
  warm:4.45,bulb:1.08,fairy:1.6,star:.45,
  sky:0xdf9f7e,skyEmissive:0xb86f58,skyEmissiveInt:.34,
  fog:0xdfd0c0,lantern:.68,night:0,
 },
};

const DAY_MORNING={...PHASES.day,sunPos:[5.8,7.9,6.0],sunColor:0xffddaa,sun:3.12};
const DAY_AFTERNOON={...PHASES.day,sunPos:[-6.6,7.8,5.4],sunColor:0xffd89e,sun:3.18};

const WEATHER_SET=new Set(['clear','cloud','fog','rain','snow']);
const cA=new Color(),cB=new Color();
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=t=>t*t*(3-2*t);
function lerpHex(hexA,hexB,t,target){
 cA.setHex(hexA);cB.setHex(hexB);
 return target.copy(cA).lerp(cB,t);
}
function blendProfile(a,b,rawT){
 const t=smooth(Math.max(0,Math.min(1,rawT)));
 return {
  sunPos:[lerp(a.sunPos[0],b.sunPos[0],t),lerp(a.sunPos[1],b.sunPos[1],t),lerp(a.sunPos[2],b.sunPos[2],t)],
  sunColor:lerpHex(a.sunColor,b.sunColor,t,new Color()).getHex(),
  sun:lerp(a.sun,b.sun,t),
  hemiSky:lerpHex(a.hemiSky,b.hemiSky,t,new Color()).getHex(),
  hemiGround:lerpHex(a.hemiGround,b.hemiGround,t,new Color()).getHex(),
  hemi:lerp(a.hemi,b.hemi,t),
  fillColor:lerpHex(a.fillColor,b.fillColor,t,new Color()).getHex(),
  fill:lerp(a.fill,b.fill,t),
  warm:lerp(a.warm,b.warm,t),
  bulb:lerp(a.bulb,b.bulb,t),
  fairy:lerp(a.fairy,b.fairy,t),
  star:lerp(a.star,b.star,t),
  sky:lerpHex(a.sky,b.sky,t,new Color()).getHex(),
  skyEmissive:lerpHex(a.skyEmissive,b.skyEmissive,t,new Color()).getHex(),
  skyEmissiveInt:lerp(a.skyEmissiveInt,b.skyEmissiveInt,t),
  fog:lerpHex(a.fog,b.fog,t,new Color()).getHex(),
  lantern:lerp(a.lantern,b.lantern,t),
  night:lerp(a.night,b.night,t),
 };
}

function localHourOf(epochSec,timezone){
 const ms=Number.isFinite(epochSec)?epochSec*1000:Date.now();
 const date=new Date(ms);
 if(timezone&&typeof timezone==='string'){
  try{
   const parts=new Intl.DateTimeFormat('en-US',{timeZone:timezone,hour12:false,hour:'2-digit',minute:'2-digit'}).formatToParts(date);
   const h=Number(parts.find(p=>p.type==='hour')?.value);
   const m=Number(parts.find(p=>p.type==='minute')?.value);
   if(Number.isFinite(h)&&Number.isFinite(m))return (h%24)+m/60;
  }catch{}
 }
 return date.getHours()+date.getMinutes()/60;
}

export function profileForHour(hour,sunriseHour=6.2,sunsetHour=18.2){
 const h=((hour%24)+24)%24;
 const dawnStart=Math.max(3.5,sunriseHour-1.2),dawnPeak=sunriseHour+.15,dayStart=sunriseHour+1.5;
 const duskStart=sunsetHour-1.3,duskPeak=sunsetHour+.1,nightStart=Math.min(22.5,sunsetHour+1.45);
 const daySpan=Math.max(.5,sunsetHour-sunriseHour);
 const solarArc=(h>=dawnStart&&h<nightStart)?Math.max(0,Math.min(1,(h-sunriseHour)/daySpan)):-1;
 if(h<dawnStart||h>=nightStart)return {phase:'night',solarArc:-1,profile:{...PHASES.night}};
 if(h<dawnPeak)return {phase:h<(dawnStart+dawnPeak)/2?'night':'dawn',solarArc:Math.max(0,solarArc),profile:blendProfile(PHASES.night,PHASES.dawn,(h-dawnStart)/(dawnPeak-dawnStart))};
 if(h<dayStart)return {phase:'dawn',solarArc:Math.max(0,solarArc),profile:blendProfile(PHASES.dawn,DAY_MORNING,(h-dawnPeak)/(dayStart-dawnPeak))};
 if(h<duskStart){
  // Continuous solar trajectory across daytime instead of a static noon plateau.
  const u=Math.max(0,Math.min(1,(h-dayStart)/Math.max(.5,duskStart-dayStart)));
  const base=u<.5?blendProfile(DAY_MORNING,PHASES.day,u*2):blendProfile(PHASES.day,DAY_AFTERNOON,(u-.5)*2);
  const elev=Math.sin(u*Math.PI);
  base.sunPos=[
   lerp(5.8,-6.6,u),
   7.85+elev*3.55,
   6.0-u*.6-elev*.22,
  ];
  base.sun=3.12+elev*.28;
  return {phase:'day',solarArc,profile:base};
 }
 if(h<duskPeak)return {phase:'dusk',solarArc:Math.min(1,Math.max(0,solarArc)),profile:blendProfile(DAY_AFTERNOON,PHASES.dusk,(h-duskStart)/(duskPeak-duskStart))};
 return {phase:h<(duskPeak+nightStart)/2?'dusk':'night',solarArc:Math.min(1,Math.max(0,solarArc)),profile:blendProfile(PHASES.dusk,PHASES.night,(h-duskPeak)/(nightStart-duskPeak))};
}

function randomOutdoorPoint(index){
 let seed=(index*2654435761+97)>>>0;
 const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
 const band=index%10;
 let x,z,maxY;
 // Use independent bands outside the eaves. Their margins accommodate the
 // largest sideways drift and the radius of a flake throughout its fall.
 if(band<4){
  x=-8.68+rnd()*(8.68-SHELTER.halfWidth-1.00);z=-5.25+rnd()*13.30;maxY=5.65;
 }else if(band<7){
  x=-8.64+rnd()*17.28;z=SHELTER.back-.40-rnd()*1.06;maxY=5.75;
 }else if(band<9){
  x=-6.45+rnd()*13.1;z=SHELTER.front+.55+rnd()*3.92;maxY=1.46;
 }else{
  x=SHELTER.halfWidth+.43+rnd()*2.62;z=-4.00+rnd()*9.30;maxY=1.48;
 }
 return {x,y:rnd()*maxY,z,maxY,phase:rnd()*Math.PI*2,speed:.82+rnd()*0.38};
}

export function createCabinAtmosphere({
 scene,hemi,sun,fill,warm,skyMaterial,daySky,nightSky,sunDisk,motes,
 screenMaterial,windowGroup,windowSunPatch,garden,lightBase,onBloomUpdate
}){
 const PRECIP_COUNT=132;
 const precipGeo=new BoxGeometry(1,1,1);
 const precipMat=new MeshBasicMaterial({color:0xd8e8f2,transparent:true,opacity:.68,depthWrite:false,toneMapped:false});
 const precipMesh=new InstancedMesh(precipGeo,precipMat,PRECIP_COUNT);
 precipMesh.instanceMatrix.setUsage(DynamicDrawUsage);
 precipMesh.frustumCulled=false;precipMesh.castShadow=false;precipMesh.receiveShadow=false;
 precipMesh.visible=false;precipMesh.userData.keepSeparate=true;
 scene.add(precipMesh);
 precipMesh.name='Outdoor precipitation';
 const slots=Array.from({length:PRECIP_COUNT},(_,i)=>randomOutdoorPoint(i));
 const pMat=new Matrix4(),pPos=new Vector3(),pScale=new Vector3(),pQuat=new Quaternion(),pEuler=new Euler();

 // These cloud banks belong to the distant sky. Drawing the opaque colour
 // before the diorama, without writing depth, also keeps orbiting views clear.
 const cloudGeo=new BoxGeometry(1,1,1);
 const cloudMat=new MeshBasicMaterial({color:0xffffff,depthWrite:false,depthTest:false,fog:false,toneMapped:false});
 const cloudBlocks=[];
 // Offset the tops and undersides of each lobe. A broad rainbank, a wisp
 // and a smaller trailing bank retain different silhouettes from every orbit.
 const banks=[
  [-5.45,6.94,-9.20,[[-1.30,0,1.24,.36],[-.68,.16,1.53,.67],[.12,.26,1.65,.86],[1.02,.10,1.35,.57],[1.69,-.02,.88,.29]]],
  [-.18,7.75,-10.38,[[-.71,.02,1.12,.32],[.00,.13,1.29,.53],[.76,-.01,.98,.25]]],
  [5.22,7.03,-8.54,[[-1.05,.02,1.15,.37],[-.46,.21,1.46,.70],[.27,.28,1.27,.82],[1.03,.11,1.15,.47]]],
 ];
 for(const [cx,cy,cz,lobes] of banks){
  for(const [i,[dx,dy,w,h]] of lobes.entries()){
   const x=cx+dx,y=cy+dy,z=cz+Math.sin(i*1.7)*.21;
   cloudBlocks.push([x,y-.12,z,w,.23,.66,0x97a7ae],
    [x,y+h*.21,z+.06,w*.91,h*.67,.84,0xb5c1c3],
    [x-.09,y+h*.56,z-.04,w*.61,h*.24,.62,0xd0d5ce]);
  }
 }
 const cloudBank=new InstancedMesh(cloudGeo,cloudMat,cloudBlocks.length);
 cloudBank.name='Cloud banks beyond the roof';
 cloudBank.renderOrder=-1000;cloudBank.visible=false;cloudBank.userData.keepSeparate=true;
 cloudBlocks.forEach(([x,y,z,w,h,d,tint],i)=>{
  pMat.makeScale(w,h,d).setPosition(x,y,z);cloudBank.setMatrixAt(i,pMat);cloudBank.setColorAt(i,new Color(tint));
 });
 scene.add(cloudBank);
 // The same overcast horizon is seen through the upper glass, behind the
 // landscape, sash, raindrops and curtains.
 const windowCloudMat=new MeshBasicMaterial({color:0xa9b8be,fog:false});
 const windowCloud=new InstancedMesh(cloudGeo,windowCloudMat,3);
 windowCloud.name='Overcast outside the window';windowCloud.visible=false;windowCloud.userData.keepSeparate=true;
 for(const [i,[x,y,w,h]] of [[-.45,.57,1.05,.12],[.48,.62,.96,.13],[.21,.51,.83,.086]].entries()){
  pMat.makeScale(w,h,.002).setPosition(x,y,.115);windowCloud.setMatrixAt(i,pMat);
 }
 windowGroup.add(windowCloud);
 const DROP_COUNT=18;
 const dropGeo=new BoxGeometry(.024,.065,.01);
 const dropMat=new MeshStandardMaterial({color:0xd4ebf2,emissive:0x7da6b5,emissiveIntensity:.22,transparent:true,opacity:.72,roughness:.15,depthWrite:false});
 const windowDrops=new InstancedMesh(dropGeo,dropMat,DROP_COUNT);
 windowDrops.instanceMatrix.setUsage(DynamicDrawUsage);
 windowDrops.castShadow=false;windowDrops.receiveShadow=false;windowDrops.visible=false;windowDrops.userData.keepSeparate=true;
 windowDrops.name='Rain on the outside of the glass';
 windowGroup.add(windowDrops);
 const dropSlots=Array.from({length:DROP_COUNT},(_,i)=>({
  x:-.84+((i*37)%17)/16*1.68,
  y:-.62+((i*53)%13)/12*1.24,
  speed:.18+(i%5)*.05,
 }));

 const wetUmbrella=new Group();
 wetUmbrella.position.set(3.16,.13,3.42);
 wetUmbrella.visible=false;wetUmbrella.userData.keepSeparate=true;
 scene.add(wetUmbrella);
 const uTrayMat=new MeshStandardMaterial({color:0x8e8372,roughness:.9});
 const uPuddleMat=new MeshStandardMaterial({color:0x7ea6b0,transparent:true,opacity:.52,roughness:.16,depthWrite:false});
 const uClothMat=new MeshStandardMaterial({color:0x587c86,roughness:.55});
 const uWoodMat=new MeshStandardMaterial({color:0x9e7d5c,roughness:.82});
 const uTipMat=new MeshStandardMaterial({color:0xc9b98a,roughness:.5});
 const addUBox=(parent,w,h,d,x,y,z,mat)=>{
  const g=new BoxGeometry(w,h,d);const m=new Mesh(g,mat);
  m.position.set(x,y,z);m.castShadow=mat!==uPuddleMat;m.receiveShadow=true;m.userData.keepSeparate=true;
  parent.add(m);return m;
 };
 addUBox(wetUmbrella,.32,.03,.32,0,.015,0,uTrayMat);
 addUBox(wetUmbrella,.42,.008,.38,.02,.006,.02,uPuddleMat);
 const uStick=new Group();uStick.rotation.z=-.18;uStick.rotation.x=.08;wetUmbrella.add(uStick);
 addUBox(uStick,.03,.78,.03,0,.4,0,uWoodMat);
 addUBox(uStick,.09,.03,.03,-.03,.79,0,uWoodMat);
 addUBox(uStick,.03,.08,.03,-.065,.76,0,uWoodMat);
 addUBox(uStick,.13,.46,.13,0,.35,0,uClothMat);
 addUBox(uStick,.15,.035,.15,0,.38,0,uTipMat);
 addUBox(uStick,.018,.07,.018,0,.04,0,uTipMat);

 let timeMode='day';
 let weatherOverride=null;
 let envData=null,serverTime=null,sceneItems=[],studying=false,curtainSunFactor=1;
 let currentPhase='day',currentWeather='clear',nightFactor=0,hourValue=12.5,solarArcValue=.5,umbrellaWet=false;
 let sunbeamState={visible:true,offsetX:.05,lengthScale:.92,opacity:.22};

 function resolveState(){
  const current=envData?.current||{};
  const rawEffect=typeof current.effect==='string'?current.effect.toLowerCase():'clear';
  const weather=weatherOverride||(WEATHER_SET.has(rawEffect)?rawEffect:'clear');
  let phase='day',profile,hour=12.5,solarArc=.5;
  if(timeMode!=='auto'&&PHASES[timeMode]){
   phase=timeMode;
   profile={...PHASES[timeMode]};
   hour=phase==='dawn'?6.2:phase==='day'?12.5:phase==='dusk'?18.2:0;
   solarArc=phase==='dawn'?.08:phase==='day'?.5:phase==='dusk'?.92:-1;
  }else{
   const tz=envData?.timezone||'';
   const nowSec=Number.isFinite(serverTime)?serverTime:Date.now()/1000;
   hour=localHourOf(nowSec,tz);
   const sr=Number.isFinite(envData?.sunrise)?localHourOf(envData.sunrise,tz):6.2;
   const ss=Number.isFinite(envData?.sunset)?localHourOf(envData.sunset,tz):18.2;
   if(!envData?.available&&current.is_day===false){
    phase='night';profile={...PHASES.night};hour=0;solarArc=-1;
   }else{
    const solved=profileForHour(hour,sr,ss);
    phase=solved.phase;profile=solved.profile;solarArc=solved.solarArc;
   }
  }
  const nowSec=Number.isFinite(serverTime)?serverTime:Date.now()/1000;
  const itemWet=Array.isArray(sceneItems)&&sceneItems.some(it=>it&&it.kind==='umbrella'&&!it.carried&&Number(it.wet_until)>nowSec);
  return {phase,profile,weather,hour,solarArc,umbrella:weather==='rain'||itemWet,wind:Number(current.wind_speed)||0};
 }

 function syncSunbeam(){
  if(!windowSunPatch)return;
  const isDaylight=nightFactor<.78&&solarArcValue>=0&&(currentWeather==='clear'||currentWeather==='cloud');
  const wxFactor=currentWeather==='clear'?1:(currentWeather==='cloud'?.38:0);
  const elev=Math.sin(Math.max(.08,Math.min(.92,solarArcValue))*Math.PI);
  const opacity=+(0.24*wxFactor*(1-nightFactor)*(.55+.45*elev)*curtainSunFactor).toFixed(3);
  const offsetX=+(windowGroup.position.x+(solarArcValue-.5)*2.15).toFixed(3);
  const lengthScale=+(1.34-elev*.46).toFixed(3);
  const rotZ=+((.5-solarArcValue)*.34).toFixed(3);
  sunbeamState={visible:isDaylight&&opacity>.015,offsetX,lengthScale,opacity};
  windowSunPatch.visible=sunbeamState.visible;
  if(windowSunPatch.visible){
   windowSunPatch.position.set(offsetX,.142,-2.28-(1-lengthScale)*.42);
   windowSunPatch.scale.set(curtainSunFactor<.6?.68:1,lengthScale,1);
   windowSunPatch.rotation.z=rotZ;
   if(windowSunPatch.material){
    windowSunPatch.material.opacity=opacity;
    windowSunPatch.material.color.setHex(currentPhase==='dusk'?0xffbe7d:currentPhase==='dawn'?0xffdcb0:0xfff1c4);
   }
  }
 }

 function apply(){
  const {phase,profile,weather,hour,solarArc,umbrella,wind}=resolveState();
  currentPhase=phase;currentWeather=weather;hourValue=hour;solarArcValue=solarArc;nightFactor=profile.night;umbrellaWet=umbrella;
  const isNight=phase==='night';
  const duskOrNight=phase==='night'||phase==='dusk';

  let sunScale=1,hemiScale=1,fogNear=30,fogFar=72;
  const fogCol=new Color(profile.fog);
  const skyCol=new Color(profile.sky);
  const skyEm=new Color(profile.skyEmissive);
  const hemiGroundCol=new Color(profile.hemiGround);
  if(weather==='cloud'){
   sunScale=.7;hemiScale=.92;fogNear=27;fogFar=66;
   skyCol.lerp(new Color(isNight?0x3e4d59:0xaab8b8),.45);
   fogCol.lerp(new Color(isNight?0x232f2b:0xd8ded8),.4);
  }else if(weather==='fog'){
   sunScale=.54;hemiScale=.9;fogNear=19;fogFar=59;
   skyCol.lerp(new Color(isNight?0x3a4a48:0xcfd8d2),.65);
   fogCol.lerp(new Color(isNight?0x263530:0xd7dfd7),.7);
  }else if(weather==='rain'){
   sunScale=.56;hemiScale=.86;fogNear=26;fogFar=71;
   skyCol.lerp(new Color(isNight?0x2b3c4a:0x869da6),.6);
   skyEm.lerp(new Color(0x4c6874),.5);
   fogCol.lerp(new Color(isNight?0x1b282c:0xc4d0cf),.58);
  }else if(weather==='snow'){
   sunScale=.74;hemiScale=1.04;fogNear=24;fogFar=60;
   hemiGroundCol.lerp(new Color(0xc7d2d4),.45);
   skyCol.lerp(new Color(isNight?0x46586b:0xd6e1e6),.55);
   fogCol.lerp(new Color(isNight?0x26333d:0xe4eaec),.6);
  }

  sun.position.set(profile.sunPos[0],profile.sunPos[1],profile.sunPos[2]);
  sun.color.setHex(profile.sunColor);
  hemi.color.setHex(profile.hemiSky);
  hemi.groundColor.copy(hemiGroundCol);
  fill.color.setHex(profile.fillColor);
  fill.intensity=profile.fill;

  const studyBoost=studying&&(duskOrNight||weather==='rain'||weather==='cloud');
  const rainCozy=weather==='rain'||weather==='snow'?.45:0;
  lightBase.hemi=+(profile.hemi*hemiScale).toFixed(3);
  lightBase.sun=+(profile.sun*sunScale).toFixed(3);
  lightBase.warm=+(profile.warm+rainCozy+(studyBoost?1.45:0)).toFixed(3);
  lightBase.bulb=+(profile.bulb+(studyBoost?.95:0)+(weather==='rain'?.25:0)).toFixed(3);
  lightBase.fairy=+(profile.fairy+(weather==='rain'&&!isNight?.35:0)).toFixed(3);
  lightBase.star=weather==='clear'?profile.star:profile.star*.25;
  warm.distance=studyBoost?5.2:4;

  skyMaterial.color.copy(skyCol);
  skyMaterial.emissive.copy(skyEm);
  skyMaterial.emissiveIntensity=profile.skyEmissiveInt;
  const overcast=weather==='cloud'||weather==='rain'||weather==='snow'||weather==='fog';
  daySky.visible=!isNight&&!overcast;
  nightSky.visible=isNight&&!overcast;
  cloudBank.visible=overcast;
  windowCloud.visible=overcast;
  cloudMat.color.setHex(isNight?0x485b71:weather==='rain'?0xc4ccce:0xefefea);
  windowCloudMat.color.setHex(isNight?0x526476:weather==='rain'?0x96a7af:0xb6c4c2);
  if(sunDisk){
   sunDisk.visible=!isNight&&weather!=='rain'&&weather!=='fog';
   const arcClamped=solarArc>=0?solarArc:.5;
   sunDisk.position.x=lerp(-.66,.68,arcClamped);
   sunDisk.position.y=-.12+Math.sin(arcClamped*Math.PI)*.58;
  }
  motes.visible=!isNight&&weather==='clear'&&curtainSunFactor>0;
  if(motes.visible)motes.position.x=(solarArc>=0?(solarArc-.5)*1.1:0);
  syncSunbeam();

  screenMaterial.emissiveIntensity=isNight?.12:duskOrNight?.07:.03;
  scene.fog.color.copy(fogCol);
  scene.fog.near=fogNear;scene.fog.far=fogFar;

  const showPrecip=weather==='rain'||weather==='snow';
  precipMesh.visible=showPrecip;
  if(weather==='rain'){
   precipMat.color.setHex(isNight?0x8fb3cc:0xc5dce8);
   precipMat.opacity=isNight?.52:.62;
  }else if(weather==='snow'){
   precipMat.color.setHex(0xf6f9fb);
   precipMat.opacity=.86;
  }
  windowDrops.visible=weather==='rain';
  wetUmbrella.visible=umbrella;
  if(showPrecip||windowDrops.visible)tick(performance.now()/1000,1);

  const windNorm=wind>0?Math.min(2,wind/18):(weather==='rain'?.6:weather==='snow'?.35:0);
  if(garden.setAtmosphere){
   garden.setAtmosphere({
    night:isNight,
    lantern:Math.min(1,profile.lantern+(weather==='rain'?.22:0)),
    firefly:isNight&&weather==='clear',
    butterfly:!duskOrNight&&weather==='clear',
    weather,
    wind:windNorm,
   });
  }else{
   garden.setNight(isNight);
  }
  garden.styleWeather?.(isNight,weather==='snow'||garden.diagnostics?.().snow);
  sun.shadow.needsUpdate=true;
  onBloomUpdate?.(duskOrNight,phase==='night'?.62:phase==='dusk'?.34:.12);
 }

 function tick(seconds,motion=1){
  if(precipMesh.visible){
   const isRain=currentWeather==='rain';
   const fallSpeed=isRain?7.4:1.15;
   pEuler.set(0,0,isRain?-.13:0);pQuat.setFromEuler(pEuler);
   if(isRain)pScale.set(.022,.36,.022);else pScale.set(.065,.065,.065);
   const windMotion=Math.min(1,Math.max(0,motion));
   for(let i=0;i<PRECIP_COUNT;i++){
    const s=slots[i];
    const topY=s.maxY||5.6,span=topY+0.18;
    const y=topY-((s.y+seconds*fallSpeed*s.speed)%span);
    const x=s.x+(isRain?((topY-y)*.12):Math.sin(seconds*1.4+s.phase)*.22*windMotion);
    const z=s.z+(isRain?0:Math.cos(seconds*1.1+s.phase)*.16*windMotion);
    pPos.set(x,y,z);
    if(!isRain){const fl=.8+.35*Math.sin(seconds*2.3+s.phase);pScale.set(.062*fl,.062*fl,.062*fl);}
    pMat.compose(pPos,pQuat,pScale);
    precipMesh.setMatrixAt(i,pMat);
   }
   precipMesh.instanceMatrix.needsUpdate=true;
  }
  if(windowDrops.visible){
   pQuat.identity();pScale.set(1,1,1);
   for(let i=0;i<DROP_COUNT;i++){
    const d=dropSlots[i];
    const y=.66-((seconds*d.speed+i*.19)%1.32);
    const x=d.x+Math.sin(seconds*1.5+i)*.012;
    pPos.set(x,y,.142);
    pMat.compose(pPos,pQuat,pScale);
    windowDrops.setMatrixAt(i,pMat);
   }
   windowDrops.instanceMatrix.needsUpdate=true;
  }
 }

 return {
  refreshLighting:apply,
  setNight(flag){
   timeMode=flag?'night':'day';
   apply();
  },
  setTimeMode(mode){
   timeMode=['auto','dawn','day','dusk','night'].includes(mode)?mode:'auto';
   apply();
  },
  setWeatherOverride(kind){
   weatherOverride=WEATHER_SET.has(kind)?kind:null;
   apply();
  },
  setEnvironment(env,srvTime,items){
   envData=env||null;
   if(srvTime!==undefined)serverTime=srvTime;
   if(items!==undefined)sceneItems=items||[];
   apply();
  },
  setCurtainFactor(mode){
   const next=mode==='closed'?0:mode==='half'?.46:1;
   if(next===curtainSunFactor)return;
   curtainSunFactor=next;
   if(motes)motes.visible=currentPhase!=='night'&&currentWeather==='clear'&&curtainSunFactor>0;
   syncSunbeam();
  },
  setStudying(flag){
   const next=!!flag;
   if(next===studying)return;
   studying=next;
   apply();
  },
  tick,
  get state(){
   return {
    timeMode,
    dayPhase:currentPhase,
    night:currentPhase==='night',
    nightFactor,
    hour:+hourValue.toFixed(2),
    solarArc:+solarArcValue.toFixed(3),
    sunPos:sun.position.toArray().map(v=>+v.toFixed(2)),
    sunbeam:sunbeamState,
    weather:currentWeather,
    precipitating:precipMesh.visible,
    highClouds:cloudBank.visible,
    windowRain:windowDrops.visible,
    umbrellaWet,
    studying,
   };
  },
  dispose(){
   cloudBank.removeFromParent();windowCloud.removeFromParent();
   cloudBank.dispose();windowCloud.dispose();cloudGeo.dispose();cloudMat.dispose();windowCloudMat.dispose();
   precipGeo.dispose();precipMat.dispose();
   dropGeo.dispose();dropMat.dispose();
   wetUmbrella.traverse(n=>{if(n.isMesh)n.geometry.dispose();});
   uTrayMat.dispose();uPuddleMat.dispose();uClothMat.dispose();uWoodMat.dispose();uTipMat.dispose();
  },
 };
}
