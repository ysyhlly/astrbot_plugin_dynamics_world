/* Contextual live-world inspection popover for 3D cabin furniture, character, gate & garden stations. */
import {formatTs} from './api.js';
import {msg,setText} from './series-ui.js';

export const INSPECT_LABELS={
 actor:'角色状态 · 身心与日程',
 gate:'院门路标 · 世界地图与出行',
 desk:'书桌 · 写作与世界空间',
 bed:'床铺 · 休息与作息',
 kitchen:'厨房 · 餐食与茶水',
 window:'北窗 · 窗帘与天气天光',
 cat:'小屋猫咪 · 实时动态',
 clothesline:'院子晾衣绳',
 shelf:'书架 · 完结书册与纪念格',
 mailbox:'拱门信箱 · 投递与访客',
 garden_bed:'花圃菜畦 · 生态与收获',
};

const PHASE_NAMES={dawn:'清晨柔光',day:'正午日光',dusk:'黄昏斜阳',night:'静谧夜晚'};
const CURTAIN_LABELS={open:'全开透光',half:'半拢柔光',closed:'拉合遮光'};
const LAMP_LABELS={bright:'明亮伴读',warm:'暖光常亮',dim:'夜灯微光',off:'已关闭'};
const STAGE_LABELS={seedling:'幼苗抽芽',growing:'枝叶舒展',blooming:'繁花盛放',ripe:'饱满待收'};
const FORM_LABELS={pixel_avatar:'像素旅人',dove:'白鸽信使',squirrel:'松鼠访客',kitten:'三花幼猫'};
const FLOOR_SLOT_PILLS=[
 ['left_wall','左墙'],
 ['right_wall','右墙'],
 ['back_wall','北墙'],
 ['center','居中'],
 ['near_window','窗畔'],
 ['bedside','床畔'],
];
const SURFACE_SLOT_PILLS=[
 ['desk_left','桌左'],
 ['desk_right','桌右'],
 ['bedside','床头'],
 ['bookshelf','书架'],
];
const ARRANGE_TARGET_BY_CARD={desk:'desk',bed:'bed',shelf:'bookcase'};
const ARRANGE_LABEL_BY_ID={desk:'书桌位置',bed:'床铺位置',bookcase:'书柜位置',chair:'座椅位置',lamp:'台灯位置'};

function formatHM(epochSec,timezone){
 if(!Number.isFinite(epochSec)||epochSec<=0)return '';
 const d=new Date(epochSec*1000);
 try{
  return new Intl.DateTimeFormat('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false,...(timezone?{timeZone:timezone}:{})}).format(d);
 }catch{
  return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
 }
}

function formatPantry(pantry){
 const entries=Object.entries(pantry||{}).filter(([,v])=>Number(v)>0);
 return entries.length?entries.map(([k,v])=>`${k}×${v}`).join(' · '):'篮中暂无鲜采食材（花菜成熟后可采收）';
}

function pickRoomDesign(scene){
 const designs=Array.isArray(scene?.room_designs)?scene.room_designs:[];
 return designs.find(d=>d.room_id===scene?.room_id)||designs[0]||scene?.room_design||{};
}

function isCharacterAwayOrBusy(data){
 const scene=data?.scene||{};
 const rooms=Array.isArray(scene.rooms)?scene.rooms:[];
 const homeIds=new Set(rooms.map(r=>r?.place_id).filter(Boolean));
 const away=scene.phase==='travelling'||Boolean(data?.actor?.journey)||(homeIds.size>0&&scene.place_id&&!homeIds.has(scene.place_id));
 const asleep=data?.availability==='asleep'||data?.activity_code==='sleeping';
 return away||asleep||Boolean(scene.paused)||Boolean(scene.action);
}

function buildRows(key,snapshot,diag){
 const data=snapshot||{};
 const scene=data.scene||{};
 const rd=pickRoomDesign(scene);
 const items=Array.isArray(scene.items)?scene.items:[];
 const env=data.environment||{};
 const cur=env.current||{};
 const tz=env.timezone||'';
 const plan=Array.isArray(data.plan_today)?data.plan_today:[];
 const atm=diag?.atmosphere||{};
 const cues=diag?.cues||{};
 const eco=data.ecology||{};
 const ks=data.keepsakes||{};
 const mb=data.mailbox||{};
 const ws=data.world_space||{};
 const actor=data.actor||{};
 const hDesk=Array.isArray(data.horizons_desk)?data.horizons_desk:[];
 const rows=[];

 if(key==='actor'){
  const charName=data.character?.name||'小屋主人';
  const where=scene.phase==='travelling'&&scene.destination?`前往 ${scene.destination} 途中`:
   [scene.place_name||actor.place_name||'小屋',scene.room_name].filter(Boolean).join(' · ');
  rows.push(['角色与位置',`${charName} · ${where}`]);
  const actNow=scene.action?.label||data.activity||(data.plan_now ? '计划示意：'+data.plan_now : '当前活动待确认');
  rows.push(['此刻行动',actNow]);
  const outfit=data.outfit_now||data.character?.outfit||scene.outfit||'日常居家穿搭';
  rows.push(['当前穿搭',String(outfit)]);
  if(ws.active_guest?.name){
   rows.push(['同行访客',`${ws.active_guest.name} · ${ws.active_guest.activity||'正在院落串门做客'}`]);
  }
  const nowSec=Number.isFinite(data.server_time)?data.server_time:Date.now()/1000;
  const upcoming=plan.filter(p=>Number(p.end||0)>nowSec).slice(0,2);
  if(upcoming.length){
   rows.push(['接下来日程',upcoming.map(p=>`${formatHM(p.start,tz)}–${formatHM(p.end,tz)} ${p.activity}`).join('；')]);
  }else if(plan.length){
   const tail=plan.slice(-2);
   rows.push(['今日日程',tail.map(p=>`${formatHM(p.start,tz)} ${p.activity}`).join('；')]);
  }
 }else if(key==='gate'){
  const journey=actor.journey;
  if(journey){
   rows.push(['当前行程',`前往 ${journey.destination_name||'目的地'} · 预计 ${formatTs(journey.arrives_at)} 抵达`]);
  }else{
   rows.push(['当前驻留',[actor.place_name||scene.place_name||'住所小屋',scene.room_name].filter(Boolean).join(' · ')]);
  }
  if(actor.plan?.destination_name){
   rows.push(['待出发计划',`计划前往 ${actor.plan.destination_name}`]);
  }
  const places=Array.isArray(data.map?.places)?data.map.places:(Array.isArray(actor.places)?actor.places:[]);
  rows.push(['世界地图',places.length?`已连通 ${places.length} 处地点（可直接选点出发）`:'尚未生成世界地图，可打开完整地图绘制']);
  if(env.available){
   const temp=cur.temperature!=null?`${cur.temperature} °C`:'';
   rows.push(['出行天气',[cur.label||'晴朗',temp].filter(Boolean).join(' · ')]);
  }
 }else if(key==='desk'){
  const lampMode=rd.lighting||diag?.lampMode||'warm';
  const lampNote=LAMP_LABELS[lampMode]||(atm.studying?'台灯已点亮伴读':'暖光待机照明中');
  rows.push(['台灯与桌面',lampNote]);
  if(ws.world_id){
   const peerNames=(ws.members||[]).map(m=>m.character_name||m.identity).filter(Boolean);
   const wsDesc=ws.shared?`${ws.label||'共享世界'}（共 ${peerNames.length} 位角色：${peerNames.slice(0,4).join('、')}）`:'独立角色世界（可绑定同组共享地图与天气）';
   rows.push(['世界空间',wsDesc]);
   if(ws.active_guest?.name){
    rows.push(['当前串门',`${ws.active_guest.name} · ${ws.active_guest.activity||'正在院中做客'}`]);
   }else if(Array.isArray(ws.recent_encounters)&&ws.recent_encounters.length){
    rows.push(['最近偶遇',ws.recent_encounters[0].summary||'公共地点擦肩问候']);
   }
  }
  const projects=Array.isArray(scene.projects)?scene.projects:(Array.isArray(data.projects)?data.projects:[]);
  if(projects.length){
   const top=projects.slice(0,2).map(p=>`${p.title||'未命名项目'}${p.stage?'（'+p.stage+'）':p.status?'（'+p.status+'）':''}`).join('；');
   rows.push(['持续创作',top]);
  }
  const notebooks=items.filter(i=>i.kind==='notebook'||i.kind==='computer');
  const records=[];
  for(const item of notebooks){
   for(const n of [...(item.notes||[]),...(item.documents||[])])records.push(n);
  }
  records.sort((a,b)=>(b.created_at||0)-(a.created_at||0));
  if(records.length){
   const latest=records[0];
   rows.push(['最近记录',`${latest.title||'随笔'}${latest.created_at?' · '+formatTs(latest.created_at):''}（共 ${records.length} 篇）`]);
  }else{
   rows.push(['最近记录','笔记本摊开在桌面，暂无已归档段落']);
  }
  const book=items.find(i=>i.kind==='book');
  if(book){
   const progress=Number.isFinite(book.page)&&Number.isFinite(book.pages)?`第 ${book.page} / ${book.pages} 页`:'可随时翻阅';
   rows.push(['在读书籍',`${book.name||'随身读物'} · ${progress}`]);
  }
  if(hDesk.length){
   const top=hDesk[0];
   const cite=[top.title,top.chapter_label].filter(Boolean).join(' · ');
   rows.push(['案头见闻',`${cite}${top.reflection?' — '+top.reflection:(top.digest?' — '+top.digest:'')}`]);
  }
 }else if(key==='bed'){
  const asleep=data.availability==='asleep'||data.activity_code==='sleeping'||cues.sleep;
  const started=formatHM(data.activity_started_at,tz);
  if(asleep){
   rows.push(['当前作息',started?`正在熟睡中（${started} 入睡）`:'正在熟睡中，呼吸平稳']);
  }else if(data.activity_code==='resting'){
   rows.push(['当前作息',started?`正在床边小憩（${started} 开始）`:'正在床边放松休息']);
  }else{
   rows.push(['当前作息','被褥松软整洁，枕畔留着常读的书']);
  }
  const vit=eco.vitality||{};
  if(vit.energy!==undefined){
   rows.push(['身心元气',`精力 ${Math.round(Number(vit.energy)*100)}% · 心情 ${vit.mood_label||'安宁'} · 灵感 ${Math.round(Number(vit.inspiration||0.7)*100)}%`]);
  }
  const restPlans=plan.filter(p=>/睡|就寝|午睡|小憩|休息|早起|醒/.test(p.activity)).slice(0,2);
  if(restPlans.length){
   rows.push(['作息安排',restPlans.map(p=>`${formatHM(p.start,tz)}–${formatHM(p.end,tz)} ${p.activity}`).join('；')]);
  }else if(data.plan_now){
   rows.push(['当前时段',data.plan_now]);
  }
 }else if(key==='kitchen'){
  const status=cues.cook?'灶火正温，汤锅正在咕嘟冒热气':cues.meal?'餐盘与热饮已摆上桌':'灶台与厨具擦拭干净';
  rows.push(['厨台动态',status]);
  rows.push(['时令储物篮',formatPantry(eco.pantry)]);
  if(Array.isArray(eco.recent_meals)&&eco.recent_meals.length){
   const lastMeal=eco.recent_meals[eco.recent_meals.length-1];
   rows.push(['最近料理',`${lastMeal.title||'手作茶点'}${lastMeal.ingredients?.length?'（'+lastMeal.ingredients.join('、')+'）':''}`]);
  }
  const kettle=items.find(i=>i.kind==='water');
  if(kettle){
   const servings=Number.isFinite(kettle.servings)?`剩余 ${kettle.servings} 份饮水`:'水量充足';
   rows.push(['水壶状态',`${kettle.name||'水壶'} · ${servings}${kettle.carried?'（随身携带）':''}`]);
  }
  const mealPlans=plan.filter(p=>/早[餐饭]|午[餐饭]|晚[餐饭]|用餐|做饭|煮|炒|煎|茶|咖啡|点心|夜宵|备餐/.test(p.activity)).slice(0,2);
  if(mealPlans.length){
   rows.push(['今日饮食',mealPlans.map(p=>`${formatHM(p.start,tz)} ${p.activity}`).join(' · ')]);
  }
 }else if(key==='window'){
  const cMode=rd.curtains||diag?.curtainMode||'open';
  rows.push(['窗帘状态',CURTAIN_LABELS[cMode]||'全开透光']);
  const phaseLabel=PHASE_NAMES[atm.dayPhase]||'自然天光';
  rows.push(['天光时段',`${phaseLabel}${tz?'（'+tz+'）':''}`]);
  if(env.available){
   const temp=cur.temperature!=null?`${cur.temperature} °C`:'';
   const feels=cur.apparent_temperature!=null?`（体感 ${cur.apparent_temperature} °C）`:'';
   rows.push(['窗外实况',[env.location?.name,cur.label||'晴朗',temp+feels].filter(Boolean).join(' · ')]);
   const sr=formatHM(env.sunrise,tz),ss=formatHM(env.sunset,tz);
   if(sr||ss)rows.push(['日出日落',`日出 ${sr||'—'} · 日落 ${ss||'—'}`]);
  }else{
   rows.push(['窗外实况','实时天气暂未接入，可在世界设置中配置参考城市']);
  }
 }else if(key==='cat'){
  const catState=eco.cat||{};
  const spotLabel=catState.spot_label||'床尾暖毯角';
  const poseNote=catState.label||(cues.sleep?'蜷在床尾软毯上守着主人安睡':
   cues.cook?'闻到厨房香气，耳朵朝灶台方向微微抖动':
   atm.weather==='rain'?'听着窗外淅沥雨声，团成毛球打着小呼噜':'趴在暖毯上规律呼吸，偶尔动动耳朵');
  rows.push(['当前点位',spotLabel]);
  rows.push(['此刻神态',poseNote]);
 }else if(key==='clothesline'){
  const w=atm.weather||'clear';
  const drying=w==='rain'?'细雨微潮，门口已备好湿伞与滴水盘':
   w==='snow'?'薄雪覆上横杆，衣物在清冷微风中轻晃':
   w==='fog'||w==='cloud'?'云雾柔和，亚麻衬衫与鼠尾草毛巾正慢速风干':
   atm.dayPhase==='night'?'晚风轻拂，晾衣绳上的织物安静垂挂':'日光与微风正好，衬衫、毛巾与方巾正蓬松晾晒';
  rows.push(['晾晒状态',drying]);
  const nowSec=Number.isFinite(data.server_time)?data.server_time:Date.now()/1000;
  const wetItems=items.filter(i=>Number(i.wet_until)>nowSec);
  if(wetItems.length)rows.push(['待晾干物品',wetItems.map(i=>i.name||'雨伞').join('、')]);
 }else if(key==='shelf'){
  const vols=Array.isArray(ks.bookshelf_volumes)?ks.bookshelf_volumes:[];
  rows.push(['定稿成书',vols.length?`已上架 ${vols.length} 册（点击下方书名可翻阅全文）`:'暂无定稿成书，创作项目完结后将自动装帧上架']);
  if(hDesk.length){
   const top=hDesk[0];
   const meta=[top.title,top.chapter_label,top.creator?`作者/来源 ${top.creator}`:''].filter(Boolean).join(' · ');
   rows.push(['见闻书签',meta]);
   if(top.reflection)rows.push(['最近随感',top.reflection]);
  }else{
   rows.push(['见闻书签','暂未同步见闻书签，可在群间见闻阅读信息源与书籍']);
  }
  const slotLabels=ks.slot_labels||{};
  const activeSlots=Object.entries(ks.slots||{}).map(([s,it])=>`${slotLabels[s]||s}：${it.title||'纪念物'}`);
  rows.push(['3D 陈列位',activeSlots.length?activeSlots.slice(0,4).join('；'):'8 处陈列位正待摆放花束、茶点与信物']);
  rows.push(['收藏匣归档',ks.archive_count?`匣中珍藏 ${ks.archive_count} 件旧物（可随时换上陈列位）`:'收藏匣暂空（陈列位满后旧物会自动收入匣中）']);
 }else if(key==='mailbox'){
  rows.push(['访客门禁',mb.policy_label||'像素小人探访（仅限户外花园）']);
  rows.push(['待拆来信',mb.unopened_count?`${mb.unopened_count} 封新投递等待查收（红旗已竖起）`:'信箱已清空，暂无未拆信件']);
  const visitors=Array.isArray(mb.visitors)?mb.visitors:[];
  if(visitors.length){
   rows.push(['花园访客',visitors.map(v=>`${v.display_name}（${FORM_LABELS[v.form]||v.form}）`).join('、')]);
  }else{
   rows.push(['花园访客','此刻户外院落清幽，暂无访客驻足']);
  }
  const openedParcel=(mb.parcels||[]).find(p=>p.status==='opened'&&p.reaction);
  if(openedParcel){
   rows.push(['最近回响',openedParcel.reaction]);
  }
 }else if(key==='garden_bed'){
  const season=eco.season||{};
  rows.push(['时令节气',[season.season_label,season.solar_term].filter(Boolean).join(' · ')||'温和时节']);
  const vit=eco.vitality||{};
  if(vit.energy!==undefined){
   rows.push(['角色元气',`精力 ${Math.round(Number(vit.energy)*100)}% · ${vit.mood||vit.mood_label||'状态待确认'}${vit.legacy_visual_only?'':(' · 灵感 '+Math.round(Number(vit.inspiration||0.7)*100)+'%')}`]);
  }
  const fl=eco.flowerbed||{};
  const vg=eco.veg_patch||{};
  rows.push(['院西花圃',`${fl.crop||'洋甘菊'} · ${STAGE_LABELS[fl.stage]||'生长中'}（${Math.round(Number(fl.progress||0)*100)}%）`]);
  rows.push(['院东菜畦',`${vg.crop||'卷心菜'} · ${STAGE_LABELS[vg.stage]||'生长中'}（${Math.round(Number(vg.progress||0)*100)}%）`]);
  rows.push(['收获储物篮',formatPantry(eco.pantry)]);
 }
 return rows;
}

export function createCabinInspector(stage,{onResetFocus,onOpenDrawer,onCycleTime,onQuickAction}={}){
 const card=document.createElement('aside');
 card.className='cabin-inspect-card';
 card.id='cabinInspectCard';
 card.setAttribute('popover','manual');
 card.setAttribute('aria-live','polite');
 card.hidden=true;

 const head=document.createElement('div');
 head.className='cabin-inspect-head';
 const title=document.createElement('strong');
 title.className='cabin-inspect-title';
 const closeBtn=document.createElement('button');
 closeBtn.type='button';
 closeBtn.className='wb-button tiny cabin-inspect-close';
 setText(closeBtn,msg('恢复视角'));
 head.append(title,closeBtn);

 const list=document.createElement('dl');
 list.className='cabin-inspect-list';
 const actions=document.createElement('div');
 actions.className='cabin-inspect-actions';
 card.append(head,list,actions);
 stage.append(card);

 const supportsPopover=typeof card.showPopover==='function';
 let activeKey=null,actionBusy=false,openBookId='',adminArrangePref=null;

 function hideCard(){
  activeKey=null;
  openBookId='';
  if(supportsPopover&&card.matches(':popover-open')){
   try{card.hidePopover();}catch{}
  }
  card.hidden=true;
 }

 closeBtn.addEventListener('click',()=>{
  hideCard();
  onResetFocus?.();
 });

 card.addEventListener('toggle',event=>{
  if(event.newState==='closed'){
   activeKey=null;
   openBookId='';
   card.hidden=true;
  }
 });

 function makeBtn(label,cls,handler,disabled=false){
  const b=document.createElement('button');
  b.type='button';
  b.className='wb-button tiny '+cls;
  b.disabled=disabled||actionBusy;
  setText(b,msg(label));
  b.addEventListener('click',handler);
  return b;
 }

 async function runQuick(kind,payload={}){
  if(actionBusy||!onQuickAction)return;
  actionBusy=true;
  actions.querySelectorAll('button,input,select').forEach(n=>{n.disabled=true;});
  try{
   await onQuickAction(kind,payload);
  }finally{
   actionBusy=false;
  }
 }

 function appendVitalityMeters(eco){
  const vit=eco?.vitality||{};
  const energyPct=Math.max(0,Math.min(100,Math.round(Number(vit.energy??0.82)*100)));
  const inspPct=Math.max(0,Math.min(100,Math.round(Number(vit.inspiration??0.74)*100)));
  const mood=vit.mood_label||vit.mood||'平和舒展';
  const wrap=document.createElement('div');
  wrap.className='cabin-vital-meters';
  const moodTag=document.createElement('div');
  moodTag.className='cabin-vital-mood';
  moodTag.textContent=`心情：${mood}`;
  wrap.append(moodTag);
  for(const [lbl,pct,tone] of (vit.legacy_visual_only ? [['精力',energyPct,'energy']] : [['精力',energyPct,'energy'],['灵感',inspPct,'insp']])){
   const row=document.createElement('div');
   row.className='cabin-vital-meter';
   const name=document.createElement('span');
   name.className='cabin-vital-label';
   name.textContent=lbl;
   const track=document.createElement('span');
   track.className='cabin-vital-track';
   const fill=document.createElement('span');
   fill.className='cabin-vital-fill is-'+tone;
   fill.style.width=`${pct}%`;
   track.append(fill);
   const val=document.createElement('span');
   val.className='cabin-vital-value';
   val.textContent=`${pct}%`;
   row.append(name,track,val);
   wrap.append(row);
  }
  actions.append(wrap);
 }

 function appendFurnitureArrange(key,data,canWrite){
  const targetKind=ARRANGE_TARGET_BY_CARD[key];
  if(!targetKind||!canWrite)return;
  const scene=data?.scene||{};
  const rd=pickRoomDesign(scene);
  const furnList=Array.isArray(rd.furniture)?rd.furniture:[];
  const furn=furnList.find(f=>f&&(f.kind===targetKind||f.id===targetKind)&&f.movable!==false);
  if(!furn||!rd.room_id)return;

  const charBusyOrAway=isCharacterAwayOrBusy(data);
  const instantMode=charBusyOrAway?true:(adminArrangePref??false);
  const box=document.createElement('div');
  box.className='cabin-arrange-box';

  const top=document.createElement('div');
  top.className='cabin-arrange-head';
  const lbl=document.createElement('span');
  lbl.className='cabin-arrange-title';
  lbl.textContent=ARRANGE_LABEL_BY_ID[targetKind]||'家具落位';

  const modeLabel=document.createElement('label');
  modeLabel.className='cabin-arrange-mode';
  const chk=document.createElement('input');
  chk.type='checkbox';
  chk.checked=instantMode;
  chk.disabled=actionBusy||charBusyOrAway;
  chk.addEventListener('change',()=>{
   adminArrangePref=chk.checked;
  });
  const modeText=document.createElement('span');
  modeText.textContent=msg('即时落位（管理员布置）');
  modeLabel.append(chk,modeText);
  top.append(lbl,modeLabel);

  const pills=document.createElement('div');
  pills.className='cabin-slot-pills';
  const baseDefs=furn.kind==='lamp'||furn.anchor==='surface'?SURFACE_SLOT_PILLS:FLOOR_SLOT_PILLS;
  const allowed=Array.isArray(furn.allowed_positions)&&furn.allowed_positions.length?new Set(furn.allowed_positions):null;
  const slotDefs=allowed?baseDefs.filter(([k])=>allowed.has(k)):baseDefs;
  const curPos=furn.position||furn.slot||'';
  for(const [slotKey,slotName] of slotDefs){
   const pill=document.createElement('button');
   pill.type='button';
   const isCurrent=curPos===slotKey;
   pill.className='cabin-slot-pill'+(isCurrent?' is-active':'');
   pill.setAttribute('aria-pressed',String(isCurrent));
   pill.disabled=actionBusy||isCurrent;
   pill.textContent=slotName;
   pill.addEventListener('click',()=>{
    const useAdmin=chk.checked||charBusyOrAway;
    if(useAdmin){
     runQuick('admin_arrange',{room_id:rd.room_id,steps:[{kind:'move_furniture',target_id:furn.id,position:slotKey,room_id:rd.room_id}]});
    }else{
     runQuick('move_furniture',{room_id:rd.room_id,target_id:furn.id,position:slotKey});
    }
   });
   pills.append(pill);
  }
  box.append(top,pills);
  actions.append(box);
 }

 function renderActions(key,snapshot){
  if(actions.contains(document.activeElement)&&actions.querySelector('.cabin-quick-input, .cabin-quick-select'))return;
  actions.replaceChildren();
  const data=snapshot||{};
  const scene=data.scene||{};
  const ks=data.keepsakes||{};
  const mb=data.mailbox||{};
  const ws=data.world_space||{};
  const eco=data.ecology||{};
  const actor=data.actor||{};
  const canWrite=data.can_write!==false;
  const canSceneAct=Boolean(canWrite&&scene.available&&!scene.paused&&!scene.action);
  const row=document.createElement('div');
  row.className='cabin-inspect-btn-row';

  if(key==='actor'){
   appendVitalityMeters(eco);
   row.append(
    makeBtn('实况拍立得','primary',()=>runQuick('postcard_capture')),
    makeBtn('切换角色换装','',()=>{hideCard();runQuick('open_wardrobe');}),
    makeBtn('展开日常安排','',()=>{hideCard();onOpenDrawer?.('life');}),
   );
  }else if(key==='gate'){
   const places=Array.isArray(data.map?.places)?data.map.places:(Array.isArray(actor.places)?actor.places:[]);
   let destSelect=null;
   if(places.length&&canWrite){
    const destBox=document.createElement('div');
    destBox.className='cabin-quick-note';
    destSelect=document.createElement('select');
    destSelect.className='cabin-quick-select';
    for(const p of places){
     const o=document.createElement('option');
     o.value=p.id;
     o.textContent=p.id===actor.place_id?`${p.name}（当前）`:p.name;
     if(actor.plan?.destination_id===p.id)o.selected=true;
     destSelect.append(o);
    }
    if(!actor.plan?.destination_id){
     const other=places.find(p=>p.id!==actor.place_id);
     if(other)destSelect.value=other.id;
    }
    destBox.append(destSelect);
    actions.append(destBox);
   }
   const canDepart=Boolean(canWrite&&places.length&&!actor.paused&&actor.phase==='located');
   const canPlan=Boolean(canWrite&&places.length&&!actor.paused);
   const canCancel=Boolean(canWrite&&(actor.journey||actor.plan));
   row.append(
    makeBtn('立即出发','primary',()=>{
     if(destSelect?.value)runQuick('map_depart',{target_id:destSelect.value});
    },!canDepart),
    makeBtn('加入出行计划','',()=>{
     if(destSelect?.value)runQuick('map_plan',{target_id:destSelect.value});
    },!canPlan),
    makeBtn('撤销行程','',()=>runQuick('map_cancel'),!canCancel),
    makeBtn('打开完整地图','',()=>{hideCard();onOpenDrawer?.('map');}),
   );
  }else if(key==='desk'){
   appendFurnitureArrange('desk',data,canWrite);
   const noteBox=document.createElement('div');
   noteBox.className='cabin-quick-note';
   const input=document.createElement('input');
   input.type='text';
   input.maxLength=200;
   input.className='cabin-quick-input';
   input.placeholder=msg('输入简短随笔，角色将执笔记录…');
   input.disabled=!canSceneAct||actionBusy;
   const saveNote=makeBtn('记入笔记本','primary',()=>{
    const text=input.value.trim();
    if(!text){input.focus();return;}
    runQuick('write_note',{text}).then(()=>{input.value='';});
   },!canSceneAct);
   noteBox.append(input,saveNote);
   actions.append(noteBox);

   const wsBox=document.createElement('div');
   wsBox.className='cabin-quick-note';
   const wsInput=document.createElement('input');
   wsInput.type='text';
   wsInput.maxLength=40;
   wsInput.className='cabin-quick-input';
   wsInput.placeholder=msg('共享世界组 ID（如 manor-shared，留空解绑）');
   wsInput.value=ws.shared?(ws.world_id||''):'';
   wsInput.disabled=!canWrite||actionBusy;
   const wsBtn=makeBtn('绑定世界组','',()=>{
    runQuick('world_space_bind',{world_id:wsInput.value.trim()});
   },!canWrite);
   wsBox.append(wsInput,wsBtn);
   actions.append(wsBox);

   row.append(
    makeBtn('切换台灯','',()=>runQuick('lamp_cycle'),!canWrite||!scene.available),
    makeBtn('邻屋串门','',()=>runQuick('peer_visit',{guest_name:ws.members?.find(m=>m.character_name&&m.character_name!==data.character?.name)?.character_name||'邻屋伙伴'}),!canWrite),
    makeBtn('创作项目','',()=>{hideCard();onOpenDrawer?.('projects');}),
   );
  }else if(key==='bed'){
   appendFurnitureArrange('bed',data,canWrite);
   const paused=Boolean(scene.paused||data.actor?.paused);
   row.append(
    makeBtn(paused?'恢复生活':'暂停生活','primary',()=>runQuick(paused?'resume_life':'pause_life'),!canWrite),
    makeBtn('展开日常安排','',()=>{hideCard();onOpenDrawer?.('life');}),
   );
  }else if(key==='kitchen'){
   const pantry=eco.pantry||{};
   const hasHerb=(Number(pantry['洋甘菊'])||0)+(Number(pantry['薄荷叶'])||0)>0;
   const hasVeg=(Number(pantry['卷心菜'])||0)+(Number(pantry['小南瓜'])||0)>0;
   row.append(
    makeBtn('喝一口水','primary',()=>runQuick('drink'),!canSceneAct),
    makeBtn('下厨备餐','',()=>runQuick('prepare_meal'),!canSceneAct&&!hasVeg?!canSceneAct:!canSceneAct),
    makeBtn('冲泡花草茶','',()=>runQuick('brew_tea'),!canSceneAct&&!hasHerb?!canSceneAct:!canSceneAct),
    makeBtn('室内动作','',()=>{hideCard();onOpenDrawer?.('scenes');}),
   );
  }else if(key==='window'){
   row.append(
    makeBtn('切换窗帘','primary',()=>runQuick('curtains_cycle'),!canWrite||!scene.available),
    makeBtn('切换天光时段','',()=>onCycleTime?.()),
    makeBtn('天气环境','',()=>{hideCard();onOpenDrawer?.('weather');}),
   );
  }else if(key==='clothesline'){
   const nowSec=Number.isFinite(data.server_time)?data.server_time:Date.now()/1000;
   const hasWet=(Array.isArray(scene.items)?scene.items:[]).some(i=>Number(i.wet_until)>nowSec||i.wet);
   row.append(
    makeBtn('晾干湿物','primary',()=>runQuick('dry'),!(canSceneAct&&hasWet)),
    makeBtn('展开室内动作','',()=>{hideCard();onOpenDrawer?.('scenes');}),
   );
  }else if(key==='cat'){
   row.append(
    makeBtn('展开故事约定','primary',()=>{hideCard();onOpenDrawer?.('stories');}),
    makeBtn('展开日常安排','',()=>{hideCard();onOpenDrawer?.('life');}),
   );
  }else if(key==='shelf'){
   appendFurnitureArrange('shelf',data,canWrite);
   const vols=Array.isArray(ks.bookshelf_volumes)?ks.bookshelf_volumes:[];
   if(vols.length){
    const bookBar=document.createElement('div');
    bookBar.className='cabin-inspect-btn-row';
    const readerBox=document.createElement('div');
    readerBox.className='cabin-booklet-reader';
    const activeVol=vols.find(v=>v.id===openBookId)||vols[0];
    openBookId=activeVol.id;
    readerBox.textContent=`《${activeVol.title}》：${activeVol.content||activeVol.excerpt||'（手稿正文已归档）'}`;
    for(const vol of vols.slice(0,6)){
     const btn=makeBtn(`📖 ${vol.title}`,vol.id===openBookId?'primary':'',()=>{
      openBookId=vol.id;
      readerBox.textContent=`《${vol.title}》：${vol.content||vol.excerpt||'（手稿正文已归档）'}`;
      bookBar.querySelectorAll('button').forEach((b,idx)=>{
       b.classList.toggle('primary',vols[idx]?.id===openBookId);
      });
     });
     bookBar.append(btn);
    }
    actions.append(bookBar,readerBox);
   }
   const archive=Array.isArray(ks.archive)?ks.archive:[];
   if(archive.length&&canWrite){
    const swapBox=document.createElement('div');
    swapBox.className='cabin-quick-note';
    const itemSel=document.createElement('select');
    itemSel.className='cabin-quick-select';
    for(const a of archive){
     const o=document.createElement('option');
     o.value=a.id;o.textContent=`${a.title||'旧物'}`;
     itemSel.append(o);
    }
    const slotSel=document.createElement('select');
    slotSel.className='cabin-quick-select';
    for(const [sk,sl] of Object.entries(ks.slot_labels||{shelf_1:'书架上格',desk_2:'书桌右角',windowsill_vase:'窗台花瓶'})){
     if(sk==='entry_hook')continue;
     const o=document.createElement('option');
     o.value=sk;o.textContent=sl;
     slotSel.append(o);
    }
    const swapBtn=makeBtn('换上陈列','primary',()=>runQuick('keepsake_swap',{item_id:itemSel.value,slot:slotSel.value}));
    swapBox.append(itemSel,slotSel,swapBtn);
    actions.append(swapBox);
   }
   row.append(
    makeBtn('群间见闻','',()=>{hideCard();window.DynamicsSeriesNavigation?.open('astrbot_plugin_dynamics_horizons');}),
    makeBtn('创作项目','',()=>{hideCard();onOpenDrawer?.('projects');}),
   );
  }else if(key==='mailbox'){
   if(canWrite){
    const polBox=document.createElement('div');
    polBox.className='cabin-quick-note';
    const polSel=document.createElement('select');
    polSel.className='cabin-quick-select';
    const opts=mb.policy_options||{
     pixel_avatar:'像素旅人探访（仅限户外花园）',
     critter:'化身小动物信使（白鸽/松鼠/幼猫）',
     mailbox_only:'仅开启院门信箱投递',
     off:'关闭访客与投递',
    };
    for(const [val,lbl] of Object.entries(opts)){
     const o=document.createElement('option');
     o.value=val;o.textContent=lbl;
     if(val===mb.policy)o.selected=true;
     polSel.append(o);
    }
    polSel.addEventListener('change',()=>runQuick('visitor_policy',{visitor_mode:polSel.value}));
    polBox.append(polSel);
    actions.append(polBox);

    const mailBox=document.createElement('div');
    mailBox.className='cabin-quick-note';
    const kindSel=document.createElement('select');
    kindSel.className='cabin-quick-select';
    for(const [kv,kl] of [['postcard','明信片'],['flower','鲜花束'],['snack','手作茶点'],['gift','纪念小礼']]){
     const o=document.createElement('option');o.value=kv;o.textContent=kl;kindSel.append(o);
    }
    const msgInput=document.createElement('input');
    msgInput.type='text';
    msgInput.maxLength=120;
    msgInput.className='cabin-quick-input';
    msgInput.placeholder=msg('写一句附言投入院门信箱…');
    const sendBtn=makeBtn('投递','primary',()=>{
     const text=msgInput.value.trim();
     if(!text){msgInput.focus();return;}
     runQuick('mailbox_deliver',{kind:kindSel.value,message:text}).then(()=>{msgInput.value='';});
    });
    mailBox.append(kindSel,msgInput,sendBtn);
    actions.append(mailBox);
   }
   const unopened=Number(mb.unopened_count)||0;
   row.append(
    makeBtn(unopened>0?`拆阅信箱 (${unopened})`:'信箱已空','primary',()=>runQuick('mailbox_open'),!canWrite||unopened<=0),
    makeBtn('派访客逛花园','',()=>runQuick('visitor_enter',{sender_name:'路过旅人',message:'在院门旁驻足看看花'}),!canWrite||mb.policy==='off'||mb.policy==='mailbox_only'),
   );
  }else if(key==='garden_bed'){
   const harvestable=(Number(eco.flowerbed?.progress)||0)>=0.75||(Number(eco.veg_patch?.progress)||0)>=0.75;
   row.append(
    makeBtn('浇灌花菜','primary',()=>runQuick('water_garden'),!canSceneAct),
    makeBtn('采收作物',harvestable?'primary':'',()=>runQuick('harvest_garden'),!(canSceneAct&&harvestable)),
    makeBtn('冲泡花草茶','',()=>runQuick('brew_tea'),!canSceneAct),
   );
  }
  if(row.children.length)actions.append(row);
 }

 function renderContent(key,snapshot,diag){
  setText(title,msg(INSPECT_LABELS[key]||key));
  list.replaceChildren();
  for(const [k,v] of buildRows(key,snapshot,diag)){
   const dt=document.createElement('dt');dt.textContent=k;
   const dd=document.createElement('dd');dd.textContent=v;
   list.append(dt,dd);
  }
  renderActions(key,snapshot);
 }

 return {
  element:card,
  get activeKey(){return activeKey;},
  open(key,snapshot,diag){
   if(!key||!INSPECT_LABELS[key]){
    if(activeKey){hideCard();onResetFocus?.();}
    return false;
   }
   const switching=activeKey&&activeKey!==key&&!card.hidden;
   activeKey=key;
   renderContent(key,snapshot,diag);
   card.classList.remove('is-switching');
   card.hidden=false;
   if(switching){void card.offsetWidth;card.classList.add('is-switching');}
   if(supportsPopover&&!card.matches(':popover-open')){
    try{card.showPopover();}catch{}
   }
   return true;
  },
  refresh(snapshot,diag){
   if(activeKey)renderContent(activeKey,snapshot,diag);
  },
  close(){
   hideCard();
  },
 };
}
