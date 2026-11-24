import {msg,setText,tr} from './series-ui.js';
import {renderScene,bindScene,resetScene} from "./scene.js?v=round2.1";
import {apiPost,formatTs} from "./api.js";
import {renderWeather,bindWeather,city,resetWeather} from "./weather.js";
import {worldStream} from "./world-stream.js?v=round2.1";
const $=id=>document.getElementById(id);
let map=null,layers=null,avatar=null,travelLine=null,documentMap=null,pendingMapDoc=null,last=null,currentScope="",visible=false,activeView="",editing=null,pin=null;
let mapType="virtual",tileLayer=null,lastDrawnMapKey="";
const xy=p=>[mapType==="real"?p[1]:-p[1],p[0]];
function moveSlot(hostId,nodeId){const host=$(hostId),node=$(nodeId);if(host&&node&&node.parentElement!==host)host.append(node);}
function dockMapPanels(viewName){
  if(viewName==="scenes"){
    moveSlot("drawerScenesHost","mapScenes");
    moveSlot("mapWeatherHome","mapEnvironment");
    moveSlot("mapWeatherConfigHome","weatherSettings");
    moveSlot("mapWeatherConfigHome","qweatherSettings");
  }else if(viewName==="weather"){
    moveSlot("drawerWeatherHost","mapEnvironment");
    moveSlot("drawerWeatherConfigHost","weatherSettings");
    moveSlot("drawerWeatherConfigHost","qweatherSettings");
    moveSlot("mapScenesHome","mapScenes");
    const ws=$("weatherSettings");if(ws)ws.open=true;
  }else{
    moveSlot("mapWeatherHome","mapEnvironment");
    moveSlot("mapScenesHome","mapScenes");
    moveSlot("mapWeatherConfigHome","weatherSettings");
    moveSlot("mapWeatherConfigHome","qweatherSettings");
  }
}
function text(value){const node=document.createElement("span");node.textContent=String(value??"");return node;}
function status(value,error=false){
  setText($("mapStatus"),value);$("mapStatus").dataset.error=String(error);
  if(error&&activeView!=="map"){const notice=$("wbNotice");if(notice){notice.textContent=value;notice.className="wb-notice error";}}
}
function setup(mode="virtual"){
  if(map&&mapType===mode)return;
  if(map)map.remove();
  mapType=mode;tileLayer=null;avatar=null;travelLine=null;editing=null;pin=null;
  map=L.map("worldMap",mode==="real"?{minZoom:2,maxZoom:19}:{crs:L.CRS.Simple,minZoom:-3,maxZoom:3,zoomSnap:.25});
  layers=L.layerGroup().addTo(map);
  map.attributionControl.setPrefix("Leaflet");
  if(mode==="virtual")map.attributionControl.addAttribution(tr("地形：Azgaar · 角色状态：群间世界"));
  map.on("click",event=>{if(!documentMap)return;pin=[event.latlng.wrap().lng,mapType==="real"?event.latlng.lat:-event.latlng.lat];if(mapType!=="real")pin[0]=event.latlng.lng;coordinateLabel();});
}
function coordinateLabel(){$("mapCoordinates").textContent=`${mapType==="real"?tr("经度、纬度"):tr("坐标")} ${pin.map(x=>x.toFixed(mapType==="real"?5:1)).join(", ")}`;}
function fit(){if(!map||!documentMap)return;if(mapType==="real")map.fitBounds(L.latLngBounds([...documentMap.places.map(p=>xy([p.x,p.y])),xy(documentMap.center)]),{padding:[45,45],maxZoom:14});else map.fitBounds([[-documentMap.height,0],[0,documentMap.width]],{padding:[25,25]});}
function draw(doc){
  if(typeof L==="undefined"){pendingMapDoc=doc;return;}
  const firstView=!documentMap||documentMap.world_id!==doc.world_id||mapType!==(doc.map_type||"virtual");
  setup(doc.map_type||"virtual");layers.clearLayers();if(avatar)avatar.remove();avatar=null;documentMap=doc;
  lastDrawnMapKey=`${doc.world_id||""}:${doc.map_type||"virtual"}:${doc.revision||0}`;
  $("mapMode").value=mapType;
  $("mapModeHint").textContent=mapType==="real"?tr("现实底图 · 角色为虚构位置 · 行程为直线示意，非现实导航"):tr("虚拟地形 · 两种地图分别保存，切走时冻结行程");
  if(firstView&&mapType==="virtual"){$("mapSeed").value=doc.seed;$("mapSpeed").value=doc.seconds_per_unit;$("mapPlaceNames").value=doc.places.map(p=>p.name).join("\n");}
  if(mapType==="real"){
    if(!tileLayer){tileLayer=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,noWrap:true,referrerPolicy:"origin",attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'}).addTo(map);tileLayer.on("tileerror",()=>{$("mapModeHint").textContent=tr("底图暂不可用；角色位置与地点仍可使用。行程为直线示意，非现实导航。");});}
    if(firstView){$("realLatitude").value=doc.center[1];$("realLongitude").value=doc.center[0];$("realTimezone").value=doc.timezone;$("realSpeed").value=doc.walking_kmh;$("realName").value=doc.places[0]?.name||tr("地图中心");}
  }else L.imageOverlay(doc.image,[[-doc.height,0],[0,doc.width]]).addTo(layers);
  for(const road of doc.roads||[])L.polyline(road.path.map(xy),{color:"#aa8053",weight:2,opacity:.65,dashArray:"4 4"}).addTo(layers);
  for(const place of doc.places){
    const marker=L.circleMarker(xy([place.x,place.y]),{radius:5,color:"#fff",weight:2,fillColor:"#735c3c",fillOpacity:1}).addTo(layers);
    marker.bindTooltip(text(place.name),{permanent:true,direction:"top",className:"dw-map-place-label"});
    marker.on("click",event=>{L.DomEvent.stopPropagation(event);editing=place.id;pin=[place.x,place.y];$("mapPlaceName").value=place.name;$("mapDestination").value=place.id;coordinateLabel();});
  }
  $("mapDestination").replaceChildren(...doc.places.map(p=>{const o=document.createElement("option");o.value=p.id;o.textContent=p.name;return o;}));
  $("mapEmpty").style.display="none";fit();
}
function renderActor(data){
  last=data;
  renderWeather(data.environment,currentScope);
  renderScene(data.scene,documentMap,currentScope);
  const actor=data.actor||{},journey=actor.journey;
  $("mapCharacter").textContent=data.character?.name||tr("角色");
  $("mapWhere").textContent=journey?tr("前往 {0}", journey.destination_name):(actor.place_name||tr("待定位"));
  $("mapActivity").textContent=data.activity||tr("尚无活动");
  $("mapJourney").textContent=journey?tr("{0}{1}预计抵达 {2}", journey.route_kind==="straight_line_estimate"?tr("直线示意 · "):"", actor.paused?tr("已暂停 · "):"", formatTs(journey.arrives_at)):tr("位置与生活状态共同保存");
  $("mapPlan").textContent=actor.plan?tr("计划前往 {0} · 尚未出发", actor.plan.destination_name):tr("暂无出行计划");
  $("mapProgress").style.width=`${(actor.progress||0)*100}%`;
  if(avatar){avatar.remove();avatar=null;}
  if(travelLine){travelLine.remove();travelLine=null;}
  if(map&&journey)travelLine=L.polyline(journey.path.map(xy),{color:"#246e52",weight:4,opacity:.9}).addTo(map);
  if(map&&actor.position){
    const face=document.createElement("div");face.className="dw-avatar";face.textContent=(data.character?.name||"角").slice(0,1);
    avatar=L.marker(xy(actor.position),{icon:L.divIcon({html:face.outerHTML,className:"dw-map-marker",iconSize:[38,38],iconAnchor:[19,19]}),zIndexOffset:1000}).addTo(map);
    avatar.bindTooltip(text(`${data.character?.name||""} · ${data.activity||""}`));
  }
  document.querySelectorAll("[data-map-action]").forEach(button=>button.disabled=!documentMap||actor.paused===true||(button.dataset.mapAction==="depart"&&actor.phase!=="located")||(button.dataset.mapAction==="cancel"&&!actor.journey&&!actor.plan));
  const job=data.job||{};
  $("mapGenerate").disabled=data.can_write===false||job.status==="running";
  if(job.status==="running")status(tr("正在离线生成地图，完成后自动显示。当前地图会继续保留。"));
  else if(job.status==="failed")status(job.error,true);
  else if(documentMap)status(tr("地图 v{0} · {1} 个地点 · {2}", documentMap.revision, documentMap.places.length, documentMap.generator));
  else status(tr("世界尚未绘制。可从世界书地点生成第一张地图。"));
}
function resetMapScope(scope){
  currentScope=scope;documentMap=null;pendingMapDoc=null;last=null;editing=null;pin=null;lastDrawnMapKey="";
  resetWeather();resetScene();
  if(map){map.remove();map=null;layers=null;avatar=null;travelLine=null;tileLayer=null;}
  $("mapEmpty").style.display="flex";
  $("mapCharacter").textContent=tr("角色");
  $("mapWhere").textContent=tr("待定位");
  $("mapActivity").textContent=tr("尚无活动");
  $("mapJourney").textContent="";
  $("mapPlan").textContent=tr("暂无出行计划");
  $("mapProgress").style.width="0%";
  $("mapDestination").replaceChildren();
  $("mapPlaceNames").value="";
  $("mapGenerate").disabled=true;
  document.querySelectorAll("[data-map-action]").forEach(button=>button.disabled=true);
  setText($("mapStatus"),msg(scope?"正在读取当前会话的地图。":"请先选择会话。"));
  $("mapStatus").dataset.error="false";
}
function applyWorldData(data){
  if(!data)return;
  if(last?.revisions?.binding!==undefined&&last.revisions.binding!==data.revisions?.binding)resetMapScope(currentScope);
  const mapDoc=data.map&&!data.map.unchanged?data.map:null;
  const nextKey=mapDoc?`${mapDoc.world_id||""}:${mapDoc.map_type||"virtual"}:${mapDoc.revision||0}`:"";
  if(activeView==="map"){
    if(mapDoc&&nextKey!==lastDrawnMapKey){pendingMapDoc=null;draw(mapDoc);}
    else if(pendingMapDoc){const doc=pendingMapDoc;pendingMapDoc=null;draw(doc);}
  }else if(mapDoc&&nextKey!==lastDrawnMapKey){
    pendingMapDoc=mapDoc;documentMap=mapDoc;
    $("mapDestination").replaceChildren(...mapDoc.places.map(p=>{const o=document.createElement("option");o.value=p.id;o.textContent=p.name;return o;}));
  }
  if(!data.map){
    documentMap=null;pendingMapDoc=null;lastDrawnMapKey="";
    if(layers)layers.clearLayers();
    if(travelLine){travelLine.remove();travelLine=null;}
    $("mapEmpty").style.display="flex";$("mapGeneration").open=true;
    if(!$("mapPlaceNames").value)$("mapPlaceNames").value=(data.suggested_places||[]).join("\n");
  }
  renderActor(data);
  if(activeView!=="map")document.dispatchEvent(new CustomEvent("cabin-world-mutated",{detail:data}));
}
async function refresh({afterWrite=false}={}){
  const scope=$("dwScope").value.trim();if(!visible)return;
  if(scope!==currentScope)resetMapScope(scope);
  if(!scope){
    setText($("mapStatus"),msg("请先选择会话。"));
    $("mapGenerate").disabled=true;
    if(worldStream.scope)await worldStream.setScope('');
    return;
  }
  try{
    if(worldStream.scope!==scope){
      const snap=await worldStream.setScope(scope);
      if(snap&&visible&&scope===$("dwScope").value.trim()&&snap!==last)applyWorldData(snap);
    }else{
      const snap=await worldStream.refreshNow({fresh:afterWrite});
      if(snap&&visible&&scope===$("dwScope").value.trim()&&snap!==last)applyWorldData(snap);
    }
  }catch(error){if(scope===$("dwScope").value.trim())status(error.message,true);}
}
worldStream.subscribe(data=>{
  const scope=$("dwScope")?.value?.trim()||"";
  if(scope!==worldStream.scope)return;
  if(!data){resetMapScope(scope);return;}
  if(scope!==currentScope)resetMapScope(scope);
  if(visible)applyWorldData(data);
});
worldStream.onError(error=>{if(visible)status(error.message,true);});

async function mutate(body){
  const umo=$("dwScope").value.trim();if(!umo)throw new Error(tr("请先选择会话"));
  await apiPost("map",{umo,...body});if(umo===$("dwScope").value.trim())await refresh({afterWrite:true});
}
$("mapGenerate").addEventListener("click",async()=>{
  if(documentMap&&!confirm(tr("重新生成会改变地形，并保留上一版本。仍存在的同名地点会继续保留角色位置。继续吗？")))return;
  $("mapGenerate").disabled=true;
  try{await mutate({action:"generate",seed:$("mapSeed").value.trim(),places:$("mapPlaceNames").value.split(/\n/).map(x=>x.trim()).filter(Boolean),seconds_per_unit:Number($("mapSpeed").value),expected_revision:documentMap?.revision||0});}
  catch(error){status(error.message,true);$("mapGenerate").disabled=false;}
});
document.querySelectorAll("[data-map-action]").forEach(button=>button.addEventListener("click",async()=>{
  if(!last?.actor)return;button.disabled=true;
  try{await mutate({action:button.dataset.mapAction,target_id:$("mapDestination").value,map_revision:last.actor.map_revision,position_revision:last.actor.revision});}
  catch(error){status(error.message,true);}finally{button.disabled=false;}
}));
$("mapFit").addEventListener("click",fit);
$("mapNewPlace").addEventListener("click",()=>{editing=null;pin=null;$("mapPlaceName").value="";$("mapCoordinates").textContent=tr("点击地图上的陆地选择位置");});
$("mapSavePlace").addEventListener("click",async()=>{
  try{if(!pin||!documentMap)throw new Error(tr("请先点击地图选择坐标"));await mutate({action:"save_place",place_id:editing,name:$("mapPlaceName").value.trim(),x:pin[0],y:pin[1],expected_revision:documentMap.revision});}
  catch(error){status(error.message,true);}
});
document.addEventListener('world-scope-ready',()=>{
  const scope=$("dwScope").value.trim();
  if(scope!==currentScope)resetMapScope(scope);
  if(visible)void refresh();
});
document.addEventListener("world-view",event=>{
  activeView=event.detail||"";
  dockMapPanels(activeView);
  visible=["map","scenes","weather"].includes(activeView);
  if(visible){
    const scope=$("dwScope").value.trim();
    if(scope&&scope!==currentScope)resetMapScope(scope);
    if(activeView==="map"&&pendingMapDoc){const doc=pendingMapDoc;pendingMapDoc=null;draw(doc);}
    if(activeView==="map")requestAnimationFrame(()=>map?.invalidateSize());
    const cached=worldStream.scope===scope?worldStream.getSnapshot():null;
    if(cached)applyWorldData(cached);
    else void refresh();
  }
});
$("mapSwitch").onclick=async()=>{try{await mutate({action:"switch_mode",mode:$("mapMode").value,expected_revision:documentMap?.revision||0});}catch(e){status(e.message,true);$("realMapSettings").open=$("mapMode").value==="real";if($("mapMode").value==="virtual")$("mapGeneration").open=true;}};
$("realConfigure").onclick=async()=>{try{await mutate({action:"configure_real",...city(),timezone:$("realTimezone").value.trim(),walking_kmh:Number($("realSpeed").value),expected_revision:documentMap?.revision||0});}catch(e){status(e.message,true);}};
bindWeather(refresh,status);
bindScene(refresh,status);
