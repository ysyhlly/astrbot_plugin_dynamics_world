import './causal-panel.js?v=mobile.2';
import {installAvatarUI} from './cabin-avatar-ui.js?v=audit-poll.1';
import {apiGet,apiPost,formatTs,withTimeout} from './api.js';
import {msg,tr,setText,feedback} from './series-ui.js';
import {messages} from './series-messages.js';
import {cabinMessages} from './cabin-messages.js?v=stage.11';
import {createCabinInspector,INSPECT_LABELS} from './cabin-inspect.js?v=causal.1';
import {createCabinBubbles} from './cabin-bubbles.js?v=causal.1';
import {createCabinTimeline} from './cabin-timeline.js?v=stage.11';
import {createCabinAudio} from './cabin-audio.js?v=stage.11';
import {composeClientPolaroid} from './cabin-polaroid.js?v=stage.11';
import {worldStream} from './world-stream.js?v=round2.1';
Object.assign(messages,cabinMessages);
const $=id=>document.getElementById(id),make=(tag,value,cls='')=>{const n=document.createElement(tag);n.className=cls;if(value!=null)setText(n,value);return n;};
const STAGE_DRAWER_VIEWS=new Set(['life','stories','projects','activity','scenes','weather']);
const portals=[
 ['memory','笔记本','群间记忆','astrbot_plugin_dynamics_memory','DM'],
 ['visual','衣柜','视觉工坊','astrbot_plugin_visual_media','VW'],
 ['learning','随身读物','群间学习','astrbot_plugin_dynamics_learning','DL'],
 ['horizons','书架','群间见闻','astrbot_plugin_dynamics_horizons','DH'],
 ['chat','手机','Chat Dynamics','astrbot_plugin_chat_dynamics','CD'],
 ['games','游戏机','群间游戏','astrbot_plugin_dynamics_games','DG'],
];
const target3dKey=key=>key==='games'?null:key==='horizons'?'shelf':key;
const portalKeyFrom3d=key=>key==='shelf'&&controls.has('horizons')?'horizons':(controls.has(key)?key:null);
const labels={ready:'已就绪',enabled:'已启用',disabled:'已停用',missing:'未安装',unloaded:'未加载',conflict:'同名冲突',inactive:'未接入',not_ready:'未就绪',error:'状态异常'};
const TIME_MODES=[['auto','时段：实时'],['dawn','时段：清晨'],['day','时段：正午'],['dusk','时段：黄昏'],['night','时段：夜晚']];
const CURTAIN_CYCLE=['open','half','closed'];
const LAMP_CYCLE=['warm','bright','dim','off'];
let causalReading=false;
let visible=false,busy=false,lastScope='',archiveKey='',snapshot=null,companionCache=null,room3d=null,initializing=null,cameraView='garden',pixelMode=false,timeIndex=0,activePortalKey=null,cozyCam=false;
let localCurtainOverride=null,localLampOverride=null,activeReplaySnapshot=null,presenceLoadedAt=0;
let worldScopeSerial=0,replaySerial=0;
const capabilities=new Map(),controls=new Map();
let presenceRequest=null;
let presenceError='';
const cabinAudio=createCabinAudio();

const tab=make('button',msg('3D 像素小屋'),'wb-tab');tab.id='tab-cabin';tab.type='button';tab.dataset.view='cabin';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','view-cabin');tab.tabIndex=-1;$('wbTabs').prepend(tab);
const host=make('section',null,'wb-view wb-hidden pixel-cabin');host.id='view-cabin';host.setAttribute('role','tabpanel');host.setAttribute('aria-labelledby',tab.id);$('worldContent').prepend(host);
const message=make('p',null,'cabin-message');message.id='cabinMessage';message.setAttribute('role','status');host.append(message);
const layout=make('div',null,'cabin-layout'),stage=make('div',null,'cabin-stage'),heading=make('div',null,'cabin-stage-head'),title=make('div');title.append(make('strong',msg('3D 像素小屋')),make('small',msg('小屋与花园，装下日常的片刻。')));heading.append(title,make('span','WORLD / HOME','cabin-world-badge'));stage.append(heading);

const viewRow=make('div',null,'cabin-view-bar');
const viewbar=make('div',null,'cabin-view-switch');viewbar.setAttribute('role','group');setText(viewbar,msg('小屋视角'),'aria-label');
for(const [key,label] of [['garden','花园全景'],['room','室内近景']]){
 const button=make('button',msg(label),'wb-button tiny');button.type='button';button.dataset.cabinView=key;button.setAttribute('aria-pressed',String(key===cameraView));button.disabled=true;
 button.addEventListener('click',()=>{if(busy)return;if(cozyCam)setCozyCamMode(false);cameraView=key;inspector.close();closePortalPeek();room3d?.setView(key);for(const b of viewbar.children)b.setAttribute('aria-pressed',String(b.dataset.cabinView===key));});
 viewbar.append(button);
}
const tools=make('div',null,'cabin-view-tools');
const pixelBtn=make('button',msg('像素画风'),'wb-button tiny');pixelBtn.type='button';pixelBtn.id='cabinPixelMode';pixelBtn.setAttribute('aria-pressed','false');pixelBtn.disabled=true;
pixelBtn.addEventListener('click',()=>{pixelMode=!pixelMode;pixelBtn.setAttribute('aria-pressed',String(pixelMode));room3d?.setPixelMode(pixelMode);});

const timeBtn=make('button',msg(TIME_MODES[0][1]),'wb-button tiny');timeBtn.type='button';timeBtn.id='cabinTimeMode';timeBtn.dataset.timeMode='auto';timeBtn.disabled=true;
function cycleTimeMode(){
 if(timeline.isPreviewing())timeline.exitPreview();
 timeIndex=(timeIndex+1)%TIME_MODES.length;
 const [mode,label]=TIME_MODES[timeIndex];
 timeBtn.dataset.timeMode=mode;
 timeBtn.dataset.active=String(mode!=='auto');
 setText(timeBtn,msg(label));
 room3d?.setTimeMode(mode);
 syncStageBackdrop();
 inspector.refresh(snapshot,room3d?.diagnostics());
}
timeBtn.addEventListener('click',cycleTimeMode);

const timelineBtn=make('button',msg('24h 足迹'),'wb-button tiny');timelineBtn.type='button';timelineBtn.id='cabinTimelineToggle';timelineBtn.setAttribute('aria-pressed','false');timelineBtn.disabled=true;
const audioBtn=make('button',msg('环境音'),'wb-button tiny');audioBtn.type='button';audioBtn.id='cabinAudioToggle';audioBtn.setAttribute('aria-pressed','false');
audioBtn.addEventListener('click',()=>{
 const on=cabinAudio.toggle();
 audioBtn.setAttribute('aria-pressed',String(on));
 if(on)cabinAudio.playTap('wood');
});
const cozyBtn=make('button',msg('陪伴挂机'),'wb-button tiny');cozyBtn.type='button';cozyBtn.id='cabinCozyToggle';cozyBtn.setAttribute('aria-pressed','false');cozyBtn.disabled=true;
const postcardBtn=make('button',msg('实况拍立得'),'wb-button tiny');postcardBtn.type='button';postcardBtn.id='cabinPostcardBtn';

tools.append(pixelBtn,timeBtn,timelineBtn,audioBtn,cozyBtn,postcardBtn);
viewRow.append(viewbar,tools);
stage.append(viewRow);

const art=make('div',null,'cabin-diorama cabin3d-stage');stage.append(art);
const loading=make('p',msg('正在搭建 3D 小屋…'),'cabin3d-loading');art.append(loading);
const hover=make('span','','cabin3d-hover');hover.hidden=true;art.append(hover);
const cozyExitBtn=make('button',msg('退出挂机'),'wb-button tiny cabin-cozy-exit');cozyExitBtn.type='button';cozyExitBtn.hidden=true;art.append(cozyExitBtn);

function setCozyCamMode(next){
 cozyCam=Boolean(next);
 cozyBtn.setAttribute('aria-pressed',String(cozyCam));
 host.classList.toggle('is-cozy-cam',cozyCam);
 cozyExitBtn.hidden=!cozyCam;
 if(cozyCam){
  inspector.close();
  closePortalPeek();
  timeline.setOpen(false);
 }
 room3d?.setCozyCam(cozyCam);
}
cozyBtn.addEventListener('click',()=>setCozyCamMode(!cozyCam));
cozyExitBtn.addEventListener('click',()=>setCozyCamMode(false));

function pickActiveRoomDesign(scene){
 const designs=Array.isArray(scene?.room_designs)?scene.room_designs:[];
 const base=designs.find(d=>d.room_id===scene?.room_id)||designs[0]||scene?.room_design||{};
 return {
  ...base,
  ...(localCurtainOverride?{curtains:localCurtainOverride}:{}),
  ...(localLampOverride?{lighting:localLampOverride}:{}),
 };
}

function isCharUnavailableForRoomStep(data){
 const scene=data?.scene||{};
 const rooms=Array.isArray(scene.rooms)?scene.rooms:[];
 const homeIds=new Set(rooms.map(r=>r?.place_id).filter(Boolean));
 const away=scene.phase==='travelling'||Boolean(data?.actor?.journey)||(homeIds.size>0&&scene.place_id&&!homeIds.has(scene.place_id));
 const asleep=data?.availability==='asleep'||data?.activity_code==='sleeping';
 return away||asleep||Boolean(scene.paused)||Boolean(scene.action);
}

const postcardModal=make('dialog',null,'cabin-postcard-modal');
const postcardImg=document.createElement('img');postcardImg.alt='小屋实况拍立得明信片';
const postcardActions=make('div',null,'cabin-inspect-btn-row');
const postcardDownload=make('a','下载 PNG 明信片','wb-button primary tiny');postcardDownload.download='cabin-postcard.png';
const postcardClose=make('button','关闭','wb-button tiny');postcardClose.type='button';
postcardClose.addEventListener('click',()=>postcardModal.close());
postcardActions.append(postcardDownload,postcardClose);
postcardModal.append(postcardImg,postcardActions);
host.append(postcardModal);

async function captureAndShowPolaroid(noteOverride=''){
 const umo=$('dwScope').value.trim();
 if(!umo){feedback(message,msg('请先选择会话'),'error');return;}
 if(postcardBtn.disabled)return;
 const viewSerial=worldScopeSerial, ownReplay=replaySerial;
 const isCurrent=()=>viewSerial===worldScopeSerial&&ownReplay===replaySerial&&umo===$('dwScope').value.trim();
 postcardBtn.disabled=true;
 feedback(message,'正在冲印小屋实况拍立得…','loading');
 try{
  let dataUrl='';
  if(room3d&&typeof room3d.captureDataURL==='function'){
   const rawShot=room3d.captureDataURL('image/png');
   if(rawShot){
    const snap=timeline.isPreviewing()?activeReplaySnapshot:snapshot;
    dataUrl=await composeClientPolaroid(rawShot,snap||{},room3d.diagnostics?.()||null,noteOverride);
   }
  }
  if(!isCurrent())return;
  if(!dataUrl){
   if(timeline.isPreviewing())throw new Error('回放画面暂不可拍摄');
   const res=await apiPost('scene',{umo,action:'postcard_render',prefer_3d:true});
   if(!isCurrent())return;
   dataUrl=res?.data_url||'';
  }
  if(dataUrl){
   postcardImg.src=dataUrl;
   postcardDownload.href=dataUrl;
   postcardDownload.download=`cabin-postcard-${Date.now()}.png`;
   if(typeof postcardModal.showModal==='function')postcardModal.showModal();
   else postcardModal.setAttribute('open','');
   feedback(message,'实况拍立得已生成。','success');
  }
 }catch(err){
  if(isCurrent())feedback(message,err.message||'生成明信片失败','error');
 }finally{
  postcardBtn.disabled=false;
 }
}

postcardBtn.addEventListener('click',()=>captureAndShowPolaroid());

function expandWardrobeBar(){
 const avatarBox=$('cabinAvatar');
 if(avatarBox){
  avatarBox.classList.add('is-expanded');
  avatarBox.scrollIntoView({behavior:'smooth',block:'nearest'});
  $('avatarModel')?.focus();
 }
}

async function runCabinQuickAction(kind,payload={}){
 if(kind==='postcard_capture'){
  await captureAndShowPolaroid(payload.caption||'');
  return;
 }
 if(kind==='open_wardrobe'){
  room3d?.clearFocus();
  expandWardrobeBar();
  return;
 }
 const umo=$('dwScope').value.trim();
 if(!umo){feedback(message,msg('请先选择会话'),'error');return;}
 if(timeline.isPreviewing()||!snapshot||lastScope!==umo)return;
 const own=worldScopeSerial;
 const current=()=>own===worldScopeSerial&&umo===$('dwScope').value.trim();
 const report=(text,type)=>{if(current())feedback(message,text,type);};
 const sync=()=>current()?worldStream.refreshNow({fresh:true}):null;
 try{
  if(kind==='pause_life'||kind==='resume_life'){
   await apiPost('life',{action:kind==='pause_life'?'pause':'resume',umo});
   report(msg('已更新生活节奏。'),'success');
  }else if(kind==='write_note'){
   await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'preset',preset:'write_note',title:'桌畔随笔',text:String(payload.text||'').trim()});
   report(msg('已发起室内动作，稍后在小屋中呈现。'),'success');
  }else if(kind==='drink'){
   await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'preset',preset:'drink'});
   report(msg('已发起室内动作，稍后在小屋中呈现。'),'success');
  }else if(['dry','water_garden','harvest_garden','prepare_meal','brew_tea','open_mailbox'].includes(kind)){
   await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'start',steps:[{kind}]});
   report(msg('已发起室内动作，稍后在小屋中呈现。'),'success');
  }else if(kind==='move_furniture'){
   await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'start',steps:[{kind:'move_furniture',target_id:payload.target_id,position:payload.position}]});
   report('角色已动身整理家具位置。','success');
  }else if(kind==='admin_arrange'){
   await apiPost('scene',{umo,action:'admin_arrange',room_id:payload.room_id,steps:payload.steps});
   report('管理员布置已即时落位。','success');
  }else if(kind==='map_depart'||kind==='map_plan'||kind==='map_cancel'){
   const mapAct=kind.slice(4);
   await apiPost('map',{umo,action:mapAct,target_id:payload.target_id||'',map_revision:snapshot?.actor?.map_revision||0,position_revision:snapshot?.actor?.revision||0});
   report('出行状态已同步至世界地图。','success');
  }else if(kind==='curtains_cycle'){
   const cur=pickActiveRoomDesign(snapshot?.scene).curtains||'open';
   const next=CURTAIN_CYCLE[(CURTAIN_CYCLE.indexOf(cur)+1)%CURTAIN_CYCLE.length];
   localCurtainOverride=next;
   room3d?.setRoomDesign(pickActiveRoomDesign(snapshot?.scene),snapshot?.scene?.items,snapshot?.server_time);
   const d=pickActiveRoomDesign(snapshot?.scene);
   if(d?.room_id&&d.curtains!=null){
    try{
     if(!isCharUnavailableForRoomStep(snapshot)&&d.enabled){
      await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'start',steps:[{kind:'set_curtains',target_id:d.room_id,mode:next}]});
     }else{
      await apiPost('scene',{umo,action:'admin_arrange',room_id:d.room_id,steps:[{kind:'set_curtains',target_id:d.room_id,mode:next,room_id:d.room_id}]});
     }
    }finally{if(current()){localCurtainOverride=null;if(!timeline.isPreviewing())applySnapshotTo3D(snapshot);}}
   }
   if(!current())return;
   inspector.refresh(snapshot,room3d?.diagnostics());
   await sync();
   return;
  }else if(kind==='lamp_cycle'){
   const cur=pickActiveRoomDesign(snapshot?.scene).lighting||'warm';
   const next=LAMP_CYCLE[(LAMP_CYCLE.indexOf(cur)+1)%LAMP_CYCLE.length];
   localLampOverride=next;
   room3d?.setRoomDesign(pickActiveRoomDesign(snapshot?.scene),snapshot?.scene?.items,snapshot?.server_time);
   const d=pickActiveRoomDesign(snapshot?.scene);
   if(d?.room_id&&d.lighting!=null){
    try{
     if(!isCharUnavailableForRoomStep(snapshot)&&d.enabled){
      await apiPost('scene',{umo,expected_revision:snapshot?.scene?.revision||0,action:'start',steps:[{kind:'set_lighting',target_id:d.room_id,mode:next}]});
     }else{
      await apiPost('scene',{umo,action:'admin_arrange',room_id:d.room_id,steps:[{kind:'set_lighting',target_id:d.room_id,mode:next,room_id:d.room_id}]});
     }
    }finally{if(current()){localLampOverride=null;if(!timeline.isPreviewing())applySnapshotTo3D(snapshot);}}
   }
   if(!current())return;
   inspector.refresh(snapshot,room3d?.diagnostics());
   await sync();
   return;
  }else if(['mailbox_deliver','mailbox_open','visitor_policy','visitor_enter','keepsake_swap','world_space_bind','peer_visit'].includes(kind)){
   await apiPost('scene',{umo,action:kind,...payload});
   report('小屋世界状态已同步。','success');
  }
  await sync();
 }catch(err){
  report(err.message,'error');
 }
}

const inspector=createCabinInspector(art,{
 onResetFocus:()=>room3d?.clearFocus(),
 onOpenDrawer:viewName=>{room3d?.clearFocus();document.dispatchEvent(new CustomEvent('cabin-open-view',{detail:viewName}));},
 onCycleTime:cycleTimeMode,
 onQuickAction:runCabinQuickAction,
});

const bubbles=createCabinBubbles(art,{
 onBubbleSelect:target=>{
  if(!target)return;
  if(target.startsWith('inspect:')){
   const k=target.slice(8);
   closePortalPeek();
   room3d?.focusTarget(k);
   room3d?.pulseInspect?.(k);
   inspector.open(k,snapshot,room3d?.diagnostics());
  }else{
   document.dispatchEvent(new CustomEvent('cabin-open-view',{detail:target}));
  }
 },
});

const REPLAY_SLOT_BY_LABEL={'左侧墙边':'left_wall','右侧墙边':'right_wall','后墙旁':'back_wall','房间中央':'center','窗边':'near_window','床边':'bedside','书桌左侧':'desk_left','书桌右侧':'desk_right','书架上':'bookshelf','门边收纳架':'entry_rack'};
const REPLAY_CURTAIN_BY_LABEL={'窗帘打开':'open','窗帘半掩':'half','窗帘合拢':'closed'};
const REPLAY_LIGHT_BY_LABEL={'明亮室内灯光':'bright','柔和暖光':'warm','昏暗小灯':'dim','室内灯已关闭':'off'};
const REPLAY_DEFAULT_POS={desk:'near_window',bed:'left_wall',bookcase:'back_wall'};
const REPLAY_POSE_ACTIVITY={
 write:{code:'writing',text:'在书桌写笔记'},write_note:{code:'writing',text:'在书桌写笔记'},
 project_start:{code:'writing',text:'构思新稿'},project_write:{code:'writing',text:'撰写书稿'},
 project_revise:{code:'writing',text:'修订手稿'},computer_work:{code:'writing',text:'在电脑前写作'},
 read:{code:'reading',text:'在书架旁翻看书页'},read_notes:{code:'reading',text:'翻阅旧笔记'},
 cook:{code:'chores',text:'在灶台下厨备餐'},prepare_meal:{code:'chores',text:'在灶台下厨备餐'},
 brew_tea:{code:'chores',text:'冲泡花草茶'},refill:{code:'chores',text:'在厨房添水'},
 eat:{code:'eating',text:'在餐桌旁用餐'},
 wash:{code:'chores',text:'在洗漱台梳洗'},
 sweep:{code:'chores',text:'打扫整理房间'},
 water:{code:'chores',text:'浇水照料绿植'},water_garden:{code:'chores',text:'浇灌花圃菜畦'},harvest_garden:{code:'chores',text:'采收花圃蔬果'},
 game:{code:'gaming',text:'坐在床边玩掌机'},
 stroll:{code:'walking',text:'在庭院里散步'},open_mailbox:{code:'walking',text:'去院门查收信箱'},
 rest:{code:'resting',text:'在床边小憩'},
};

function buildReplayState(keyframe,index=0,historyFrames=[]){
 const baseScene=snapshot?.scene||{};
 const baseDesign=pickActiveRoomDesign(baseScene);
 const baseFurn=Array.isArray(baseDesign?.furniture)?baseDesign.furniture.map(f=>({...f,position:(f.movable&&REPLAY_DEFAULT_POS[f.kind])||f.position})):[];
 let furniture=baseFurn;
 let curtains=keyframe.curtains||baseDesign.curtains||'open';
 let lighting=keyframe.lighting||baseDesign.lighting||'warm';
 if(Array.isArray(keyframe.furniture)&&keyframe.furniture.length){
  furniture=keyframe.furniture.map(f=>({...f}));
 }else if(historyFrames.length){
  for(let i=0;i<=index&&i<historyFrames.length;i++){
   const kf=historyFrames[i];
   if(!kf)continue;
   if(kf.kind!=='admin_arrange'){
    if(kf.curtains)curtains=kf.curtains;
    if(kf.lighting)lighting=kf.lighting;
   }
   if(Array.isArray(kf.furniture)&&kf.furniture.length){
    furniture=kf.furniture.map(f=>({...f}));
    curtains=kf.curtains||curtains;
    lighting=kf.lighting||lighting;
    continue;
   }
   const m=typeof kf.summary==='string'&&kf.summary.match(/^布置了小屋：(.+?)\s*→\s*(.+)$/);
   if(m){
    const targetName=m[1].trim(),afterLabel=m[2].trim();
    const slotKey=REPLAY_SLOT_BY_LABEL[afterLabel];
    if(slotKey){
     for(const item of furniture){
      if(item.movable&&(item.name===targetName||targetName.includes(item.name))){
       item.position=slotKey;
      }
     }
    }else if(REPLAY_CURTAIN_BY_LABEL[afterLabel]){
     curtains=REPLAY_CURTAIN_BY_LABEL[afterLabel];
    }else if(REPLAY_LIGHT_BY_LABEL[afterLabel]){
     lighting=REPLAY_LIGHT_BY_LABEL[afterLabel];
    }
   }
  }
 }
 const replayRoomDesign={
  ...baseDesign,
  curtains,
  lighting,
  furniture,
 };

 const sel=avatarUI.getSelection?.()||{home_room_id:$('avatarHomeRoom')?.value||'',garden_room_id:$('avatarGardenRoom')?.value||''};
 const rooms=Array.isArray(baseScene.rooms)?baseScene.rooms:[];
 const homeRoom=rooms.find(r=>r.id===sel.home_room_id)||null;
 const gardenRoom=rooms.find(r=>r.id===sel.garden_room_id)||null;
 const away=keyframe.location==='away';
 const inGarden=keyframe.location==='garden'&&gardenRoom;
 const targetRoom=inGarden?gardenRoom:(homeRoom||rooms.find(r=>r.id===baseScene.room_id)||rooms[0]||null);

 const rawPose=String(keyframe.pose||'idle');
 const rawSummary=String(keyframe.summary||'').trim();
 const isSleep=rawPose==='sleep'||rawSummary==='睡觉';
 const mapped=REPLAY_POSE_ACTIVITY[rawPose]||null;
 const summaryPlan=!rawSummary.startsWith('布置了小屋')?rawSummary:'';
 const isDay=keyframe.timeMode!=='night';
 const replayEnv={
  ...(snapshot?.environment||{}),
  available:true,
  current:{
   ...(snapshot?.environment?.current||{}),
   effect:keyframe.weatherEffect||'clear',
   label:keyframe.weather_label||snapshot?.environment?.current?.label||'',
   temperature:keyframe.temperature!==undefined&&keyframe.temperature!==null?keyframe.temperature:snapshot?.environment?.current?.temperature,
   is_day:rawPose==='idle'?true:isDay,
  },
 };
 const replaySnapshot={
  ...(snapshot||{}),
  isReplay:true,
  server_time:Number.isFinite(keyframe.occurred_at)?keyframe.occurred_at:(snapshot?.server_time||Date.now()/1000),
  received_at_ms:Date.now(),
  replaySummary:keyframe.summary||'',
  availability:isSleep?'asleep':'available',
  activity_code:isSleep?'sleeping':(mapped?mapped.code:'unknown'),
  activity:isSleep?'睡觉':(mapped?mapped.text:summaryPlan),
  plan_now:mapped?mapped.text:(isSleep?'睡觉':summaryPlan),
  outfit_now:keyframe.outfit_now||snapshot?.outfit_now||'',
  environment:replayEnv,
  actor:{
   ...(snapshot?.actor||{}),
   phase:away?'travelling':'located',
   place_id:targetRoom?.place_id||baseScene.place_id||snapshot?.actor?.place_id||'',
   place_name:keyframe.place_name||baseScene.place_name||snapshot?.actor?.place_name||'',
   paused:false,
   journey:away?{id:'replay_journey',destination_name:keyframe.place_name||'外出途中',departed_at:(keyframe.occurred_at||0)-300,arrives_at:(keyframe.occurred_at||0)+300,progress:.5}:null,
  },
  scene:{
   ...baseScene,
   available:true,
   paused:false,
   action:null,
   phase:away?'travelling':'located',
   destination:away?(keyframe.place_name||'外出途中'):null,
   place_id:targetRoom?.place_id||baseScene.place_id||'',
   place_name:keyframe.place_name||baseScene.place_name||'',
   room_id:away?null:(targetRoom?.id||baseScene.room_id||''),
   room_name:away?'':(targetRoom?.name||baseScene.room_name||''),
   room_design:replayRoomDesign,
   room_designs:[replayRoomDesign],
  },
  journey:away?{in_transit:true,destination:keyframe.place_name||'外出途中',progress:.5}:null,
 };
 return {replaySnapshot,replayRoomDesign,replayEnv};
}

const timeline=createCabinTimeline(art,{
 onOpenChange:isOpen=>{
  timelineBtn.setAttribute('aria-pressed',String(isOpen));
  live.hidden=isOpen;
 },
 onPreviewChange:({active,keyframe,index,keyframes})=>{
  replaySerial++;
  document.dispatchEvent(new CustomEvent('dw-replay-change',{detail:{active}}));
  document.body.dataset.worldReplay=String(active);
  if(active&&keyframe){
   const {replaySnapshot,replayRoomDesign,replayEnv}=buildReplayState(keyframe,index,keyframes);
   activeReplaySnapshot=replaySnapshot;
   const applyPreview=()=>{
    if(Number.isFinite(keyframe.occurred_at)){
     room3d?.setTimeMode('auto');
     room3d?.setEnvironment({...replayEnv,current:{...replayEnv.current,is_day:keyframe.timeMode!=='night'}},keyframe.occurred_at,snapshot?.scene?.items||[]);
    }else{
     room3d?.setTimeMode(keyframe.timeMode||'auto');
    }
    room3d?.setWeatherOverride(keyframe.weatherEffect||'clear');
    room3d?.setRoomDesign(replayRoomDesign,snapshot?.scene?.items||[],keyframe.occurred_at||Date.now()/1000);
    room3d?.setCatState({spot:keyframe.cat_spot||'bed_nap'},true);
    avatarUI.preview(replaySnapshot);
   };
   if(room3d?.batch)room3d.batch(applyPreview);else applyPreview();
   syncStageBackdrop();
   inspector.refresh(replaySnapshot,room3d?.diagnostics());
   bubbles.update(replaySnapshot,room3d);
  }else{
   activeReplaySnapshot=null;
   const restoreLive=()=>{
    room3d?.setTimeMode(TIME_MODES[timeIndex][0]);
    room3d?.setWeatherOverride(null);
    if(snapshot)applySnapshotTo3D(snapshot);
   };
   if(room3d?.batch)room3d.batch(restoreLive);else restoreLive();
   if(snapshot)renderWorld(snapshot);
  }
 },
});
timelineBtn.addEventListener('click',()=>timeline.toggle());

const portalCard=make('aside',null,'cabin-inspect-card cabin-portal-card');
portalCard.id='cabinPortalCard';
portalCard.setAttribute('popover','manual');
portalCard.setAttribute('aria-live','polite');
portalCard.hidden=true;
const portalHead=make('div',null,'cabin-inspect-head');
const portalTitle=make('strong','','cabin-inspect-title');
const portalClose=make('button',msg('恢复视角'),'wb-button tiny cabin-inspect-close');
portalClose.type='button';
portalHead.append(portalTitle,portalClose);
const portalList=make('dl',null,'cabin-inspect-list');
const portalFoot=make('div',null,'cabin-inspect-actions cabin-inspect-btn-row');
const wardrobeBtn=make('button',msg('切换角色换装'),'wb-button tiny');
wardrobeBtn.type='button';
wardrobeBtn.id='cabinPortalWardrobe';
wardrobeBtn.hidden=true;
const enterBtn=make('button',msg('进入完整面板'),'wb-button primary tiny');
enterBtn.type='button';
enterBtn.id='cabinPortalEnter';
portalFoot.append(wardrobeBtn,enterBtn);
portalCard.append(portalHead,portalList,portalFoot);
art.append(portalCard);
const supportsPortalPopover=typeof portalCard.showPopover==='function';
let portalRowsKey='';

function closePortalPeek({resetCamera=false}={}){
 const prev=activePortalKey;
 activePortalKey=null;
 if(prev){
  controls.get(prev)?.button.classList.remove('is-opening','is-highlighted');
  const target=target3dKey(prev);
  if(target)room3d?.closeProp?.(target);
 }
 if(supportsPortalPopover&&portalCard.matches(':popover-open')){
  try{portalCard.hidePopover();}catch{}
 }
 portalCard.hidden=true;
 if(resetCamera)room3d?.clearFocus();
}
portalClose.addEventListener('click',()=>{closePortalPeek({resetCamera:true});room3d?.focus(null);});
portalCard.addEventListener('toggle',event=>{
 if(event.newState==='closed'&&!portalCard.matches(':popover-open')){
  activePortalKey=null;
  portalCard.hidden=true;
 }
});
wardrobeBtn.addEventListener('click',()=>{
 if(activePortalKey!=='visual')return;
 closePortalPeek({resetCamera:true});
 expandWardrobeBar();
});
enterBtn.addEventListener('click',()=>{
 const key=activePortalKey;
 if(!key)return;
 const cap=capabilities.get(key);
 if(!cap||cap.state==='error')void refreshPresence(true);
 else void launchPortal(key);
});

function buildPortalRows(key){
 const control=controls.get(key);
 const cap=capabilities.get(key);
 const comp=(snapshot?.companions||companionCache)?.[key]||{};
 const rows=[];
 rows.push(['接入状态',cap?labels[cap.state]||cap.state:'读取中…']);
 if(cap?.state==='error'&&presenceError)rows.push(['读取失败',presenceError]);
 if(comp.summary)rows.push(['实时快览',comp.summary]);
 if(key==='memory'){
  rows.push(['待核对冲突',String(comp.conflicts??0)+' 项'+(comp.bookmark_glow?' · 书签微光提醒中':'')]);
 }else if(key==='learning'){
  rows.push(['待审提案',String(comp.pending??0)+' 条']);
  rows.push(['已应用知识',String(comp.applied??0)+' 条'+(comp.scope_active?' · 本会话学习中':'')]);
  if(Array.isArray(comp.recent_terms)&&comp.recent_terms.length)rows.push(['近期习得',comp.recent_terms.join('、')]);
 }else if(key==='visual'){
  rows.push(['关联角色',String(comp.characters??0)+' 位 · 近期作品 '+String(comp.recent??0)+' 张']);
  rows.push(['墙面相框',comp.frame_pixel_grid?'已挂载最新像素化画作':'可在视觉工坊生成或上传参考画']);
 }else if(key==='horizons'){
  rows.push(['见闻储备',`活跃兴趣 ${comp.active_interests??0} 项 · 在读书籍 ${comp.books_reading??0} 册`]);
  rows.push(['待审提案',String(comp.pending_reviews??0)+' 条'+(comp.pending_questions?` · 待聊话题 ${comp.pending_questions} 个`:'')]);
  if(comp.recent_title)rows.push(['近期见闻',comp.recent_title]);
  const deskTop=snapshot?.horizons_desk?.[0];
  if(deskTop)rows.push(['案头书签',`${deskTop.title}${deskTop.chapter_label?' · '+deskTop.chapter_label:''}`]);
 }else if(key==='chat'){
  rows.push(['活跃会话',String(comp.active_sessions??0)+' 个'+(comp.session_tracked?' · 当前会话已托管':'')]);
  if(comp.pending_outreach)rows.push(['主动联络',`${comp.pending_outreach} 条待发出问候（手机屏幕微光）`]);
  if(comp.mode)rows.push(['运行模式',comp.mode+(comp.shadow?'（影子观察）':'')]);
 }else if(key==='games'){
  rows.push([msg('群间游戏'),msg('共读、约局、接龙、挑战与共创')]);
 }
 const scopeVal=$('dwScope')?.value?.trim();
 if(scopeVal)rows.push(['携带会话',scopeVal]);
 return {control,cap,rows};
}

function renderPortalPeek(key){
 const {control,cap,rows}=buildPortalRows(key);
 if(!control)return;
 setText(portalTitle,msg('{0} · {1}',msg(control.object),msg(control.label)));
 const rowsKey=JSON.stringify([key,rows]);
 if(portalRowsKey!==rowsKey){
  portalRowsKey=rowsKey;
  portalList.replaceChildren(...rows.flatMap(([label,value])=>[make('dt',label),make('dd',value)]));
 }
 // Keep the button in place during snapshot refresh, including between a
 // pointer press and release. Only its text and enabled state can change.
 wardrobeBtn.hidden=key!=='visual';
 const retry=!cap||cap.state==='error';
 setText(enterBtn,msg(retry?'刷新入口状态':'进入完整面板'));
 enterBtn.disabled=busy||(retry?Boolean(presenceRequest):!cap.can_open);
 if((wardrobeBtn.hidden&&document.activeElement===wardrobeBtn)||
   (enterBtn.disabled&&document.activeElement===enterBtn))portalClose.focus({preventScroll:true});
}

async function openPortalPeek(rawKey,{fromCanvas=false}={}){
 const key=portalKeyFrom3d(rawKey);
 if(busy||!key)return;
 cabinAudio.playTap('wood');
 inspector.close();
 if(activePortalKey&&activePortalKey!==key){
  controls.get(activePortalKey)?.button.classList.remove('is-opening','is-highlighted');
  const previousTarget=target3dKey(activePortalKey);
  if(previousTarget)room3d?.closeProp?.(previousTarget);
 }
 const switching=activePortalKey&&activePortalKey!==key&&!portalCard.hidden;
 activePortalKey=key;
 for(const [id,control] of controls)control.button.classList.toggle('is-opening',id===key);
 const targetKey=target3dKey(key);
 if(targetKey){
  room3d?.focusTarget(targetKey);
  if(key==='horizons')room3d?.pulseInspect?.('shelf');
  else room3d?.animate(targetKey,matchMedia('(prefers-reduced-motion: reduce)').matches,{sparks:!fromCanvas});
 }
 renderPortalPeek(key);
 portalCard.classList.remove('is-switching');
 portalCard.hidden=false;
 if(switching){void portalCard.offsetWidth;portalCard.classList.add('is-switching');}
 if(supportsPortalPopover&&!portalCard.matches(':popover-open')){
  try{portalCard.showPopover();}catch{}
 }
 if(!capabilities.get(key)||capabilities.get(key)?.state==='error')void refreshPresence();
 if(targetKey&&!snapshot?.companions&&!companionCache){
  try{
   const w=await apiGet('world',{umo:$('dwScope')?.value?.trim()||''});
   if(w?.companions){companionCache=w.companions;room3d?.setCompanionCues(companionCache);if(activePortalKey===key)renderPortalPeek(key);}
  }catch{}
 }
}

const footer=make('div',null,'cabin-footer');footer.append(make('span',msg('拖动旋转 · 双指或滚轮缩放 · 点选物件')));
const map=make('button',msg('查看房间与地图'),'wb-button tiny');map.type='button';map.addEventListener('click',()=>$('tab-map').click());
const reset=make('button',msg('重置视角'),'wb-button tiny');reset.type='button';reset.id='cabinResetView';reset.addEventListener('click',()=>{if(cozyCam)setCozyCamMode(false);inspector.close();closePortalPeek();room3d?.resetView();});
const fx=make('button','光效动效','wb-button tiny');fx.type='button';fx.id='cabinEffects';fx.setAttribute('aria-pressed','true');let fxOn=true;
fx.addEventListener('click',()=>{fxOn=!fxOn;fx.setAttribute('aria-pressed',String(fxOn));room3d?.setEffects(fxOn);});
footer.append(reset,fx,map);stage.append(footer);
const fxState={particle:.9,glow:.45,motion:2};

const shortcuts=make('nav',null,'cabin-portals');setText(shortcuts,msg('小屋入口'),'aria-label');shortcuts.append(make('p',msg('小屋入口'),'cabin-portals-title'));layout.append(stage,shortcuts);host.append(layout);
for(const [key,object,label,id,mark] of portals){
 const button=make('button',null,'cabin-portal');button.type='button';button.dataset.cabinLink=key;
 const copy=make('span');copy.append(make('strong',msg(object)));const state=make('small',msg('加载中…'));copy.append(state);button.append(make('span',mark,'cabin-portal-mark'),copy,make('span','↗','cabin-portal-arrow'));
 setText(button,msg('{0} · {1}',msg(object),msg(label)),'aria-label');
 button.addEventListener('click',()=>openPortalPeek(key));
 const target=target3dKey(key);
 if(target){
  button.addEventListener('pointerenter',()=>room3d?.focus(target));
  button.addEventListener('pointerleave',()=>{if(activePortalKey!==key)room3d?.focus(null);});
  button.addEventListener('focus',()=>room3d?.focus(target));
  button.addEventListener('blur',()=>{if(activePortalKey!==key)room3d?.focus(null);});
 }
 shortcuts.append(button);controls.set(key,{button,state,id,label,object});
}

const live=make('div',null,'cabin-live'),life=make('div'),weather=make('div');life.append(make('small',msg('此刻的生活')));weather.append(make('small',msg('窗外天气')));const lifeText=make('strong',msg('等待当前世界状态')),placeText=make('small',''),weatherText=make('strong',msg('天气暂不可用'));life.append(lifeText,placeText);weather.append(weatherText);live.append(life,weather);layout.append(live);
const avatarUI=installAvatarUI(host);
const archive=make('details',null,'cabin-archive');archive.id='cabinArchive';archive.hidden=true;archive.append(make('summary',msg('旧稿件档案')));const archiveBody=make('div');archive.append(archiveBody);host.append(archive);

function syncStageBackdrop(){
 const atm=room3d?.diagnostics().atmosphere;
 if(atm){
  art.dataset.dayPhase=atm.dayPhase;
  art.dataset.weather=atm.weather;
  document.body.dataset.dayPhase=atm.dayPhase;
  document.body.dataset.weather=atm.weather;
  host.classList.toggle('cabin-night',atm.night);
 }else{
  const isNight=snapshot?.environment?.current?.is_day===false||snapshot?.environment?.current?.is_day===0;
  const phase=isNight?'night':'day';
  art.dataset.dayPhase=phase;
  document.body.dataset.dayPhase=phase;
  document.body.dataset.weather=snapshot?.environment?.current?.effect||'clear';
  host.classList.toggle('cabin-night',isNight);
 }
}

function paintControls(){
 room3d?.setAvailability(capabilities);
 const comps=snapshot?.companions||companionCache||{};
 for(const [key,control] of controls){
  const value=capabilities.get(key);
  const comp=comps[key];
  control.button.disabled=busy;
  control.button.dataset.canOpen=String(Boolean(value?.can_open));
  control.button.dataset.glow=String(Boolean(comp?.glow||comp?.bookmark_glow));
  setText(control.state,msg('{0} · {1}',msg(control.label),msg(value?labels[value.state]||'未知':'加载中…')));
 }
 if(activePortalKey)renderPortalPeek(activePortalKey);
}

async function launchPortal(key){
 const control=controls.get(key);if(busy||!capabilities.get(key)?.can_open)return;
 const targetKey=target3dKey(key);
 inspector.close();
 closePortalPeek();
 busy=true;paintControls();host.setAttribute('aria-busy','true');
 try{
  const navigation=window.DynamicsSeriesNavigation;if(!navigation)throw Error(tr('请从 AstrBot 控制台打开'));
  const opened=await navigation.open(control.id,async()=>{
   control.button.classList.add('is-opening');room3d?.setBusy(true);feedback(message,msg('正在打开{0}，请稍候…',msg(control.label)),'loading');
   if(key==='horizons')room3d?.pulseInspect?.('shelf');
   else if(targetKey){
    // The hidden iframe may stop receiving animation frames during a route change.
    await withTimeout(room3d?.animate(targetKey,matchMedia('(prefers-reduced-motion: reduce)').matches),900).catch(()=>{});
   }
  });
  if(!opened)feedback(message,msg('已取消跳转，保留当前编辑。'));
 }catch(error){feedback(message,error.message||msg('未能打开面板，请稍后重试。'),'error');}
 finally{if(targetKey&&key!=='horizons')room3d?.reset(targetKey);room3d?.setBusy(false);control.button.classList.remove('is-opening');busy=false;paintControls();host.setAttribute('aria-busy','false');}
}

function applySnapshotTo3D(data){
 if(!room3d||!data)return;
 const run=()=>{
  const scene=data.scene||{},environment=data.environment||{};
  room3d.setEnvironment(environment,data.server_time,scene.items);
  room3d.setRoomDesign(pickActiveRoomDesign(scene),scene.items,data.server_time);
  if(data.ecology){
   room3d.setSeason(data.ecology.season);
   room3d.setEcology(data.ecology);
   room3d.setCatState(data.ecology.cat);
  }
  if(data.keepsakes)room3d.setKeepsakes(data.keepsakes);
  if(data.mailbox)room3d.setMailbox(data.mailbox);
  if(data.companions||companionCache)room3d.setCompanionCues(data.companions||companionCache);
 };
 if(room3d.batch)room3d.batch(run);else run();
}

function renderWorld(data){
 if(!data)return;
 data.received_at_ms=data.received_at_ms||Date.now();
 snapshot=data;
 if(data.companions){companionCache=data.companions;paintControls();}
 const scene=data.scene||{},environment=data.environment||{},current=environment.current||{};
 timeline.setKeyframes(data.timeline||[]);
 if(!timeline.isPreviewing()){
  avatarUI.refresh(data,lastScope);
  applySnapshotTo3D(data);
  syncStageBackdrop();
 }
 const diag=room3d?.diagnostics();
 cabinAudio.setState({
  weather:diag?.atmosphere?.weather||current.effect||'clear',
  night:Boolean(diag?.night),
  cooking:Boolean(diag?.cues?.cook),
 });
 inspector.refresh(timeline.isPreviewing()&&activeReplaySnapshot?activeReplaySnapshot:snapshot,diag);
 if(activePortalKey)renderPortalPeek(activePortalKey);
 bubbles.update(timeline.isPreviewing()?activeReplaySnapshot:snapshot,room3d);

 const vitMood=data.ecology?.vitality?.mood_label;
 const microLabel=room3d?.actorDiagnostics()?.projection?.micro?.active?room3d?.actorDiagnostics()?.projection?.micro?.label:'';
 setText(lifeText,scene.action?scene.action.label:scene.paused?msg('生活已暂停'):microLabel||(scene.available?msg('此刻没有正在执行的行动'):msg('当前世界尚未准备好，可先使用小屋入口。')));
 const placeParts=[scene.place_name,scene.room_name,vitMood?`心情${vitMood}`:''].filter(Boolean);
 setText(placeText,placeParts.join(' · '));
 const solar=data.ecology?.season?.solar_term;
 const wxParts=[solar,current.label||'',current.temperature!=null?current.temperature+' °C':''].filter(Boolean);
 setText(weatherText,environment.available?(wxParts.join(' · ')||msg('天气暂不可用')):(solar?`${solar} · 天气待接入`:msg('天气暂不可用')));

 const archived=scene.archived_items||[];archive.hidden=!archived.length;
 const key=lastScope+'|'+JSON.stringify(archived.map(item=>[item.id,item.documents?.length,item.notes?.length]));
 if(key!==archiveKey){archiveKey=key;archiveBody.replaceChildren(make('p',msg('电脑已停用；以下记录保留供查看。')));
  let count=0;for(const item of archived)for(const record of [...(item.documents||[]),...(item.notes||[])]){const details=make('details');details.append(make('summary',record.title+' · '+formatTs(record.created_at)),make('pre',record.text));archiveBody.append(details);count++;}
  if(!count)archiveBody.append(make('p',msg('没有已保存的旧稿件。')));
 }
}

function refreshPresence(force=false){
 if(presenceRequest)return presenceRequest;
 if(!force&&presenceLoadedAt>0&&Date.now()-presenceLoadedAt<30000)return Promise.resolve();
 presenceRequest=apiGet('series_presence').then(data=>{
  for(const [key,,,id] of portals)capabilities.set(key,data.plugins.find(plugin=>plugin.id===id)||{can_open:false,state:'missing'});
  presenceLoadedAt=Date.now();
  presenceError='';
 }).catch(err=>{
  presenceLoadedAt=0;
  presenceError=err.message;
  for(const [key] of portals)capabilities.set(key,{can_open:false,state:'error'});
 }).finally(()=>{
  presenceRequest=null;
  paintControls();
 });
 paintControls();
 return presenceRequest;
}

function resetScopeState(scope){
 worldScopeSerial++;
 lastScope=scope;
 localCurtainOverride=null;
 localLampOverride=null;
 archive.hidden=true;
 archiveKey='';
 archiveBody.replaceChildren();
 avatarUI.clear();
 snapshot=null;
 companionCache=null;
 inspector.close();
 closePortalPeek();
 timeline.setOpen(false);
 timeline.setKeyframes([]);
 if(postcardModal.open)postcardModal.close?.();
 postcardImg.removeAttribute('src');
 postcardDownload.removeAttribute('href');
 bubbles.update(null,room3d);
 setText(lifeText,msg(scope?'等待当前世界状态':'请先选择会话'));
 setText(placeText,'');
 setText(weatherText,msg('天气暂不可用'));
}

async function refresh({force=false}={}){
 if(busy)return;
 const scope=$('dwScope').value.trim();
 const scopeChanged=scope!==lastScope;
 if(scopeChanged)resetScopeState(scope);
 void refreshPresence(force);
 if(!scope){
  if(worldStream.scope)await worldStream.setScope('');
  setText(lifeText,msg('请先选择会话'));
  return;
 }
 if(scopeChanged||worldStream.scope!==scope){
  await worldStream.setScope(scope);
 }else if(force||!worldStream.getSnapshot()){
  await worldStream.refreshNow({full:false}).catch(()=>{});
 }else if(visible){
  renderWorld(worldStream.getSnapshot());
 }
}

worldStream.subscribe(data=>{
 const scope=$('dwScope')?.value?.trim()||'';
 if(scope!==worldStream.scope)return;
 if(!data||scope!==lastScope||
   (snapshot?.revisions?.binding!==undefined&&snapshot.revisions.binding!==data.revisions?.binding))resetScopeState(scope);
 if(!data)return;
 if(visible)renderWorld(data);
 else snapshot=data;
});

worldStream.onError(err=>{
 if(visible){
  avatarUI.unavailable();
  feedback(message,err.message,'error');
 }
});

paintControls();
document.addEventListener('world-view',event=>{
 const next=event.detail||'';
 visible=next==='cabin'||STAGE_DRAWER_VIEWS.has(next);
 if(!visible){inspector.close();closePortalPeek();if(cozyCam)setCozyCamMode(false);}
 bubbles.setHidden(STAGE_DRAWER_VIEWS.has(next));
 room3d?.setActive(visible&&!document.hidden&&!causalReading);
 if(visible){ensure3D();void refresh();}
});
document.addEventListener('cabin-world-mutated',event=>{if(event.detail&&visible)renderWorld(event.detail);});
document.addEventListener('world-scope-ready',()=>{avatarUI.clear();if(visible||!$('dwScope').value.trim())void refresh({force:true});});
document.addEventListener('world-overview-ready',()=>{if(visible){void ensure3D();void refresh({force:true});if(!timeline.isPreviewing()&&snapshot&&lastScope===$('dwScope').value.trim())void avatarUI.refresh(snapshot,lastScope,true);}});

let portalHoverKey=null,inspectHoverKey=null;
function updateHoverPill(){
 if(portalHoverKey){
  const c=controls.get(portalHoverKey);
  if(!c){hover.hidden=true;return;}
  hover.hidden=false;
  setText(hover,msg('{0} · {1}',msg(c.object),msg(c.label)));
 }else if(inspectHoverKey&&INSPECT_LABELS[inspectHoverKey]){
  hover.hidden=false;
  setText(hover,msg('{0} · {1}',msg(INSPECT_LABELS[inspectHoverKey]),msg('轻点查看动态')));
 }else{
  hover.hidden=true;
 }
}

async function ensure3D(){
 if(room3d){room3d.setActive(visible&&!document.hidden&&!causalReading);return;}
 if(initializing)return initializing;
 setText(loading,msg('正在搭建 3D 小屋…'));
 delete loading.dataset.uiState;
 initializing=(async()=>{try{
  const {createCabin3D}=await withTimeout(import('./cabin3d.min.js?v=garden.1'));
  room3d=createCabin3D(art,{
   onSelect:(rawKey,opts)=>openPortalPeek(portalKeyFrom3d(rawKey)||rawKey,opts),
   onHover:rawKey=>{
    const key=portalKeyFrom3d(rawKey);
    portalHoverKey=key;
    updateHoverPill();
    for(const [id,control] of controls)control.button.classList.toggle('is-highlighted',key===id||activePortalKey===id);
   },
   onInspect:key=>{
    if(busy)return;
    if(key){
     cabinAudio.playTap(key==='shelf'?'paper':'wood');
     closePortalPeek();
     room3d.focusTarget(key);
     room3d.pulseInspect?.(key);
     inspector.open(key,timeline.isPreviewing()&&activeReplaySnapshot?activeReplaySnapshot:snapshot,room3d.diagnostics());
     bubbles.syncPosition(room3d);
    }else if(inspector.activeKey||activePortalKey){
     inspector.close();
     closePortalPeek();
     room3d.clearFocus();
     bubbles.syncPosition(room3d);
    }
   },
   onInspectHover:key=>{
    inspectHoverKey=key;
    updateHoverPill();
   },
  });
  art.cabin3D=room3d;setText(room3d.canvas,msg('3D 小屋：方向键旋转，加减键缩放，Home 重置视角'),'aria-label');
  room3d.onFrame(()=>bubbles.syncPosition(room3d));
  room3d.setAvailability(capabilities);room3d.setView(cameraView);
  room3d.setTimeMode(TIME_MODES[timeIndex][0]);
  room3d.setPixelMode(pixelMode);
  if(snapshot&&!timeline.isPreviewing()){applySnapshotTo3D(snapshot);bubbles.update(snapshot,room3d);}
  syncStageBackdrop();
  room3d.setActive(visible&&!document.hidden&&!causalReading);room3d.setEffects(fxOn);room3d.setParticleAmount(fxState.particle);room3d.setGlow(fxState.glow);room3d.setMotion(fxState.motion);
  avatarUI.attach(room3d);
  for(const b of viewbar.children)b.disabled=false;
  pixelBtn.disabled=false;timeBtn.disabled=false;timelineBtn.disabled=false;cozyBtn.disabled=false;
  loading.hidden=true;
 }catch(error){
  try{room3d?.dispose();}catch{}
  room3d=null;delete art.cabin3D;art.dataset.renderer='unavailable';
  setText(loading,msg('3D 小屋加载失败。下方插件入口仍可使用，或刷新页面重试。'));loading.hidden=false;loading.dataset.uiState='warning';console.warn('Dynamics World: 3D startup failed',error);
 }
 finally{initializing=null;}})();return initializing;
}
document.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&visible){
  if(cozyCam){setCozyCamMode(false);return;}
  if(inspector.activeKey||activePortalKey){
   inspector.close();
   closePortalPeek();
   room3d?.clearFocus();
   room3d?.focus(null);
   bubbles.syncPosition(room3d);
  }
 }
});
document.addEventListener('click',event=>{
 if(!visible||(!inspector.activeKey&&!activePortalKey))return;
 const path=event.composedPath();
 if([art,shortcuts,viewRow,footer].some(container=>path.includes(container)))return;
 inspector.close();
 closePortalPeek();
 room3d?.clearFocus();
 bubbles.syncPosition(room3d);
});
document.addEventListener('visibilitychange',()=>room3d?.setActive(visible&&!document.hidden&&!causalReading));
window.addEventListener('pagehide',event=>{cabinAudio.dispose();if(event.persisted)room3d?.setActive(false);else room3d?.dispose();});
window.addEventListener('pageshow',()=>room3d?.setActive(visible&&!document.hidden&&!causalReading));

document.addEventListener('dw-causal-open',e=>{causalReading=Boolean(e.detail);room3d?.setActive(visible&&!document.hidden&&!causalReading);});
