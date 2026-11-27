import {apiGet,apiPost,escapeHtml as esc,formatTs} from './api.js';
import {msg,setText,tr} from './series-ui.js';
import {worldStream} from './world-stream.js?v=round2.1';

const tabs=[['now','此刻'],['agenda','日程'],['events','足迹'],['residents','居民'],['manage','管理']];
const labels={planned:'待开始',running:'进行中',completed:'已完成',deferred:'已延期',cancelled:'已取消',interrupted:'已中断',proposed:'等待回应',accepted:'已接受，尚未到场',declined:'已婉拒',visiting:'双方已到场'};
const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)setText(n,text);return n;};
const nav=node('nav','causal-nav');setText(nav,msg('生活观察与管理'),'aria-label');
const panel=node('aside','causal-panel');panel.hidden=true;panel.id='causal-panel';setText(panel,msg('生活观察'),'aria-label');
const head=node('header','causal-head'),title=node('h2',null,msg('此刻')),close=node('button','wb-button',msg('收起'));title.tabIndex=-1;close.type='button';head.append(title,close);
const scopeRow=node('div','causal-scope'),viewer=node('select'),viewLabel=node('label'),viewText=node('span',null,msg('观察视角'));
setText(viewer,msg('观察视角'),'aria-label');
viewLabel.append(viewText,viewer);scopeRow.append(viewLabel);
const status=node('p','causal-status',tr('等待同步')),content=node('div','causal-content');status.setAttribute('role','status');
panel.append(head,scopeRow,status,content);
document.querySelector('.wb-app')?.append(panel);
const worldNavigation=document.querySelector('.dw-navigation');
const cabinCenter=document.getElementById('dwCabinCenter');
if(cabinCenter)cabinCenter.append(nav);
else worldNavigation?.after(nav);
const smallViewport=window.matchMedia('(max-width: 650px)');
const navEdgeProperty='--causal-nav-edge';
let layoutFrame=0;

function positionMobileSheet(){
 if(panel.hidden||!smallViewport.matches)return;
 const edge=nav.getBoundingClientRect().bottom;
 const value=Math.max(0,Math.ceil(edge))+'px';
 if(panel.style.getPropertyValue(navEdgeProperty)!==value){
  panel.style.setProperty(navEdgeProperty,value);
 }
}

function scheduleMobileLayout(){
 if(panel.hidden||!smallViewport.matches||layoutFrame)return;
 layoutFrame=requestAnimationFrame(()=>{
  layoutFrame=0;
  positionMobileSheet();
 });
}

// The drawer is fixed and does not affect either observed navigation bar.
// Measuring it in a ResizeObserver could feed its own layout changes back in.
if(typeof ResizeObserver==='function'){
 const observer=new ResizeObserver(scheduleMobileLayout);
 observer.observe(nav);
 if(worldNavigation)observer.observe(worldNavigation);
}
window.addEventListener('resize',scheduleMobileLayout,{passive:true});
window.addEventListener('scroll',scheduleMobileLayout,{passive:true});
window.visualViewport?.addEventListener('resize',scheduleMobileLayout,{passive:true});
window.visualViewport?.addEventListener('scroll',scheduleMobileLayout,{passive:true});
smallViewport.addEventListener?.('change',scheduleMobileLayout);

let menuResidents=[];
let active='now',data=null,world=null,replaying=false,seq=0,scope='',loading=false,lastSync=0,stale=false,errorText='';
let scopeSerial=0;
let renderedBody='', renderedView='', deferredViewer=false, lastActorRevision=null;
const time=v=>esc(formatTs(v));
function dayKeyOf(ts){
 const n=Number(ts);if(!Number.isFinite(n)||n<=0)return '0000-00-00';
 const d=new Date(n*1000);
 return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function clockOf(ts){
 const n=Number(ts);if(!Number.isFinite(n)||n<=0)return '--:--';
 const d=new Date(n*1000);
 return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}
function dayHeading(key,todayKey){
 if(key==='0000-00-00')return tr('未指定日期');
 const [y,m,d]=key.split('-').map(Number);
 const dt=new Date(y,m-1,d);
 const weekdays=[tr('周日'),tr('周一'),tr('周二'),tr('周三'),tr('周四'),tr('周五'),tr('周六')];
 const wd=weekdays[dt.getDay()]||'';
 const md=`${String(m).padStart(2,'0')}/${String(d).padStart(2,'0')}`;
 if(key===todayKey)return `${tr('今天')} · ${md} ${wd}`;
 const [ty,tm,td]=todayKey.split('-').map(Number);
 const diffDays=Math.round((new Date(ty,tm-1,td)-dt)/86400000);
 if(diffDays===1)return `${tr('昨天')} · ${md} ${wd}`;
 return `${y}-${md} ${wd}`;
}
const section=(key,title,body)=>`<section class="causal-card" data-causal-key="${esc(key)}"><h3>${esc(title)}</h3>${body}</section>`;
const empty=text=>`<p class="causal-empty">${esc(text)}</p>`;
const tag=(s,cls='')=>`<span class="causal-tag${cls?' '+cls:''}">${esc(labels[s]?tr(labels[s]):s)}</span>`;
const hasWritePermission=()=>Boolean(data?.can_write)&&viewer.value==='admin';
const canWrite=()=>hasWritePermission()&&!replaying&&!stale&&!loading;
const viewerAvailable=()=>['admin','self'].includes(viewer.value)||
 menuResidents.some(actor=>actor.id===viewer.value);

for(const [id,label] of tabs){
 const b=node('button','wb-button causal-seg-btn',msg(label));b.type='button';b.dataset.causalTab=id;b.setAttribute('aria-controls','causal-panel');b.setAttribute('aria-expanded','false');
 b.onclick=()=>{
  const opening=panel.hidden;
  active=id;errorText='';
  if(opening){
   panel.hidden=false;
   positionMobileSheet();
   document.dispatchEvent(new CustomEvent('dw-causal-open',{detail:true}));
  }
  for(const x of nav.querySelectorAll('[data-causal-tab]')){
   const expanded=String(x===b);
   if(x.getAttribute('aria-expanded')!==expanded)x.setAttribute('aria-expanded',expanded);
  }
  render();title.focus({preventScroll:true});
  if(opening||!data||(id==='manage'||id==='agenda')&&viewer.value==='admin')void refresh();
 };nav.append(b);
}
const wbJump=node('button','wb-button causal-seg-btn causal-workbench-btn',msg('工作台'));
wbJump.type='button';wbJump.id='cabinWorkbenchSwitch';wbJump.dataset.cabinWorkbench='true';
wbJump.onclick=()=>{
 if(!panel.hidden){
  panel.hidden=true;
  document.dispatchEvent(new CustomEvent('dw-causal-open',{detail:false}));
  for(const x of nav.querySelectorAll('[data-causal-tab]'))x.setAttribute('aria-expanded','false');
 }
 document.dispatchEvent(new CustomEvent('cabin-open-view',{detail:{view:'overview',drawer:false}}));
};
nav.append(wbJump);
close.onclick=()=>{panel.hidden=true;document.dispatchEvent(new CustomEvent('dw-causal-open',{detail:false}));for(const x of nav.querySelectorAll('[data-causal-tab]'))x.setAttribute('aria-expanded','false');nav.querySelector(`[data-causal-tab="${active}"]`)?.focus();};
viewer.onchange=()=>{
 seq++;data=null;errorText='';lastActorRevision=null;
 render();void refresh();
};

function renderNow(){
 if(data?.resident){const a=data.resident;return section('current-resident',a.name,`<p>${esc(a.activity||tr('尚未开始'))}</p><p>${esc(tr("当前地点：{0}",placeName(a.place_id)))}</p>${empty(tr('以下仅显示这名居民实际获得的见闻。'))}`)+knowledge();}
 const b=data?.body||{},action=world?.scene?.action;
 const current=action?.label||(world?.activity_code==='unknown'?tr('当前活动待确认'):String(world?.activity||tr('当前活动待确认')).split(/；?环境参考/)[0]);
 const started=action?.step_started_at||world?.activity_started_at;
 const expected=action?.step_ends_at;
 const next=(data?.agenda||[]).find(p=>['planned','deferred'].includes(p.status)&&p.end>(world?.server_time||0));
 return section('current',tr('此刻正在发生'),`<p class="causal-current">${esc(current)}</p><p>${esc([world?.scene?.place_name,world?.scene?.room_name].filter(Boolean).join(' · ')||tr('位置待确认'))}</p><p class="causal-meta">${started?tr('开始于 ')+time(started):tr('开始时间未知')}${expected?tr(' · 预计结束 ')+time(expected):''}</p>${tag(action?tr('执行中'):world?.availability==='unknown'?tr('待确认'):tr('生活状态'))}<p>${esc(tr("接下来：{0}",next?.activity||tr("尚无确定安排，允许留白")))}</p>`)
 +section('body',tr('身心与依据'),`<p class="causal-current">${esc(b.label||tr('尚未建立状态'))}</p><details data-causal-key="body-reasons"><summary data-series-text="查看状态依据">查看状态依据</summary><p>${esc(data?.baseline||'')}</p>${['energy','satiety','hydration'].map((k,i)=>`<label class="causal-meter">${[tr('精力'),tr('饱足'),tr('水分')][i]}<meter min="0" max="1" value="${Number(b[k]??0)}"></meter><span>${b[k]===undefined?tr('未知'):Math.round(b[k]*100)+'%'}</span></label>`).join('')}<ul>${(b.reasons||[]).map(r=>`<li>${esc(r.text)}${r.until?' · '+time(r.until):''}</li>`).join('')}</ul></details>`)
 +section('growth',tr('逐渐积累'),Object.entries(data?.growth||{}).map(([k,v])=>`<p>${esc(tr("{0}：{1} 次已完成练习 · {2} 天有记录",{reading:tr("阅读"),writing:tr("写作"),gardening:tr("园艺")}[k]||k,v.sessions,(v.days||[]).length))}</p>`).join('')||empty(tr('完成阅读、写作或园艺后，会留下有来源的练习记录。')))
 + (canWrite() ? section('actions',tr('行动管理'), action ? `<button class="wb-button" data-scene-action="interrupt" data-series-text="当前步骤完成后中断">当前步骤完成后中断</button>` : world?.scene?.last_action?.status==='interrupted' ? `<button class="wb-button" data-scene-action="resume" data-series-text="继续中断的流程">继续中断的流程</button>` : empty(tr('没有需要恢复的行动。'))) : '')
 +renderObjects();
}
function renderObjects(){
 const items=(world?.scene?.items||[]).filter(i=>viewer.value==='admin'||i.visible||i.carried);
 const food=world?.ecology?.prepared||[];
 return section('objects',tr('身边的物件'),items.map(i=>`<details class="causal-object" data-causal-key="object:${esc(i.id)}"><summary>${esc(i.name)} ${i.carried?tr('· 随身'):i.visible?tr('· 当前可见'):''}</summary><p>${esc(tr("归属：当前角色世界 · {0}",i.carried?tr("随身携带"):i.room_id||i.place_id||tr("位置待确认")))}</p><p>${i.wet?tr('尚未干燥'):i.kind==='book'?tr("已读 {0} / {1} 页", i.page||0, i.pages||0):i.kind==='water'?tr("余量 {0} 份", i.servings||0):tr('当前记录已保存')}</p><p class="causal-meta">${objectActions(i).map(a=>esc(a.kind)).join(' · ')||tr('此刻没有可直接执行的动作；请先检查位置、持有状态和当前行动。')}</p><button class="wb-button" data-jump="scenes" data-series-text="查看物品与动作">查看物品与动作</button></details>`).join('')+food.map(f=>`<p>${esc(f.title)} ${tag(tr('已制作，尚未食用'))}<small> ${time(f.at)}</small></p>`).join('')+(items.length||food.length?'':empty(tr('当前没有已登记物件。'))));
}
function objectActions(i){return(world?.scene?.available_actions||[]).filter(a=>a.target_id===i.id);}
function agendaForm(plan){
 if(!['planned','deferred','interrupted'].includes(plan.status)||!hasWritePermission())return '';
 const disabled=canWrite()?'':'disabled';
 return `<form data-causal-key="plan-form" data-agenda="${esc(plan.id)}">
  <label><span data-series-text="调整原因">调整原因</span><input name="reason" required maxlength="200"></label>
  <label><span data-series-text="开始">开始</span><input type="datetime-local" name="start"></label>
  <label><span data-series-text="结束">结束</span><input type="datetime-local" name="end"></label>
  <button class="wb-button" name="mode" value="deferred" ${disabled} data-series-text="延期">延期</button>
  <button class="wb-button" name="mode" value="cancelled" ${disabled} data-series-text="取消安排">取消安排</button>
 </form>`;
}
function renderPlanRegenCard(){
 if(!hasWritePermission())return '';
 const ps=data?.plan_status;
 const st=ps?.status||'missing';
 const failed=st==='failed';
 const generating=st==='generating'||loading;
 const disabled=canWrite()&&!generating&&!data?.paused?'':'disabled';
 const headline=generating?tr('正在重新生成今日日程…')
  :failed?tr('今日日程生成失败')
  :st==='ready'?tr('今日日程已就绪（{0}）',ps?.plan_date||ps?.today||'')
  :tr('今日日程尚未生成');
 const details=[];
 if(ps?.last_attempt_at&&st!=='ready')details.push(tr('最近尝试 ')+time(ps.last_attempt_at));
 if(ps?.last_attempt_status&&st!=='ready'&&ps.last_attempt_status!=='advanced')details.push(ps.last_attempt_status);
 if(ps?.last_error&&st!=='ready')details.push(ps.last_error);
 if(ps?.plan_date&&ps?.today&&ps.plan_date!==ps.today)details.push(tr('当前日程停留在 {0}',ps.plan_date));
 const toneCls=failed?' is-error':st==='missing'?' is-warning':'';
 const btnCls=failed||st==='missing'?'wb-button primary':'wb-button';
 const btnText=generating?tr('生成中…'):failed?tr('重新生成今日日程'):st==='ready'?tr('重新生成'):tr('生成今日日程');
 return `<section class="causal-card causal-plan-banner${toneCls}" data-causal-key="plan-regen"><div class="causal-plan-head"><div><h3>${esc(headline)}</h3>${details.length?`<p class="causal-meta">${esc(details.join(' · '))}</p>`:''}</div><button class="${btnCls}" type="button" data-regen-plan="true" ${disabled}>${esc(btnText)}</button></div></section>`;
}
function renderPlanItem(p,nowTs){
 const isCancelled=p.status==='cancelled';
 const isActive=p.status==='running'||(p.status==='planned'&&Number(p.start)<=nowTs&&Number(p.end)>nowTs);
 const statusCls=isActive?'is-running':p.status==='completed'?'is-done':p.status==='deferred'?'is-warn':(isCancelled||p.status==='interrupted')?'is-muted':'';
 const startClock=clockOf(p.start),endClock=clockOf(p.end);
 const sameDay=dayKeyOf(p.start)===dayKeyOf(p.end);
 const rangeLabel=sameDay?`${startClock} – ${endClock}`:`${startClock} – ${tr('次日')} ${endClock}`;
 const formHtml=agendaForm(p);
 const metaBody=`<div class="causal-tracks"><div><small data-series-text="原计划">原计划</small><p>${time(p.original?.start||p.start)} → ${time(p.original?.end||p.end)}</p></div><div><small data-series-text="当前安排 / 实际">当前安排 / 实际</small><p>${time(p.start)} → ${time(p.end)}</p><p>${p.actual_start?tr('实际开始 ')+time(p.actual_start):tr('尚无执行回执')}${p.actual_end?tr(' · 结束 ')+time(p.actual_end):''}</p></div></div>${(p.history||[]).map(h=>`<p>${time(h.at)} · ${esc(h.reason)}</p>`).join('')}<p>${esc(tr("{0} 条行动回执",(p.receipts||[]).length))}</p>${formHtml}`;
 return `<article class="causal-card causal-plan-item${isCancelled?' is-cancelled':''}${isActive?' is-current':''}" data-causal-key="plan:${esc(p.id)}"><div class="causal-plan-item-head"><span class="causal-plan-time">${esc(rangeLabel)}</span>${tag(p.status,statusCls)}</div><p class="causal-plan-activity">${esc(p.activity)}</p>${p.reason?`<p class="causal-meta">${esc(p.reason)}</p>`:''}<details data-causal-key="plan-reasons"><summary data-series-text="详情与调整">详情与调整</summary>${metaBody}</details></article>`;
}
function renderAgenda(){
 const header=renderPlanRegenCard();
 const rawList=Array.isArray(data?.agenda)?data.agenda:[];
 if(!rawList.length){
  return header+empty(tr('日程从新版本启用后的计划开始积累；不会把旧计划补记为已经完成。'));
 }
 const nowTs=Number(world?.server_time||Date.now()/1000);
 const todayKey=data?.plan_status?.today||dayKeyOf(nowTs);
 const groups=new Map();
 for(const item of rawList){
  const key=dayKeyOf(item.start||item.original?.start);
  if(!groups.has(key))groups.set(key,[]);
  groups.get(key).push(item);
 }
 const sortedDays=[...groups.keys()].sort((a,b)=>{
  if(a===todayKey&&b!==todayKey)return -1;
  if(b===todayKey&&a!==todayKey)return 1;
  const aActive=groups.get(a).some(x=>x.status!=='cancelled')?0:1;
  const bActive=groups.get(b).some(x=>x.status!=='cancelled')?0:1;
  if(aActive!==bActive)return aActive-bActive;
  return b.localeCompare(a);
 });
 const firstOpenKey=groups.has(todayKey)?todayKey:(sortedDays.find(k=>groups.get(k).some(x=>x.status!=='cancelled'))||sortedDays[0]);
 const dayBlocks=sortedDays.map(dayKey=>{
  const dayItems=groups.get(dayKey).slice().sort((a,b)=>{
   const sa=Number(a.start||a.original?.start||0);
   const sb=Number(b.start||b.original?.start||0);
   if(sa!==sb)return sa-sb;
   const ca=a.status==='cancelled'?1:0,cb=b.status==='cancelled'?1:0;
   if(ca!==cb)return ca-cb;
   return Number(a.end||0)-Number(b.end||0);
  });
  const activeItems=dayItems.filter(x=>x.status!=='cancelled');
  const cancelledItems=dayItems.filter(x=>x.status==='cancelled');
  const openAttr=dayKey===firstOpenKey?' open':'';
  const countText=cancelledItems.length
   ?tr('{0} 项有效 · {1} 项已替代',activeItems.length,cancelledItems.length)
   :tr('{0} 项安排',activeItems.length);
  const cancelledBlock=cancelledItems.length
   ?`<details class="causal-cancelled-group" data-causal-key="day-cancelled:${esc(dayKey)}"><summary>${esc(tr('查看当日已取消 / 替代的 {0} 项旧计划',cancelledItems.length))}</summary><div class="causal-day-list">${cancelledItems.map(p=>renderPlanItem(p,nowTs)).join('')}</div></details>`
   :'';
  return `<details class="causal-day-group${dayKey===todayKey?' is-today':''}" data-causal-key="day:${esc(dayKey)}"${openAttr}><summary class="causal-day-head"><strong>${esc(dayHeading(dayKey,todayKey))}</strong><span class="causal-day-count">${esc(countText)}</span></summary><div class="causal-day-list">${activeItems.map(p=>renderPlanItem(p,nowTs)).join('')||empty(tr('当日暂无有效安排。'))}${cancelledBlock}</div></details>`;
 }).join('');
 return header+dayBlocks;
}
function renderEvents(){return (data?.events||[]).map(e=>section('event:'+e.id,e.summary||e.operation||e.kind,`<p class="causal-meta">${time(e.occurred_at)} · ${esc(e.origin==='admin'||e.kind.startsWith('admin.')?tr('管理操作'):e.kind==='step.completed'?tr('完成回执'):tr('世界事件'))}</p>${e.reason?`<p>${esc(e.reason)}</p>`:''}<details><summary data-series-text="事件依据">事件依据</summary><p>${esc(e.id)}</p>${e.action_id?`<p>${esc(tr("关联行动：{0}",e.action_id))}</p>`:''}${e.result?`<p>${esc(e.result.summary||e.result.name||tr('状态变化已保存'))}</p>`:''}</details>`)).join('')||knowledge();}
function knowledge(){return(data?.knowledge||[]).slice().reverse().map(k=>section('knowledge:'+k.id,k.text,`<p>${time(k.at)}</p>`)).join('')||empty(tr('还没有可展示的已感知事件。'));}
function placeName(id){return world?.map?.places?.find(p=>p.id===id)?.name||id||tr('待确认');}
function renderNeighborOnboarding(){
 if(!hasWritePermission())return empty(tr('尚未登记背景居民。可在管理页选择已有角色卡，登记后默认不启用。'));
 const places=world?.map?.places||[];
 const candidates=Array.isArray(data?.worldbook_characters)?data.worldbook_characters:[];
 const disabled=canWrite()&&places.length?'':'disabled';
 const placeOptions=places.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
 const chipsHtml=candidates.length
  ? `<div class="causal-neighbor-chips"><p class="causal-meta">${esc(tr('从世界书发现的人物（点击一键建卡并登记为邻居）：'))}</p><div class="causal-links">${candidates.map(c=>`<button type="button" class="wb-button tiny" data-quick-neighbor="true" data-nb-name="${esc(c.name)}" data-nb-desc="${esc(c.description||'')}" ${disabled}>＋ ${esc(c.name)}</button>`).join('')}</div></div>`
  : '';
 const formHtml=places.length
  ? `<form data-quick-neighbor-form="true" class="causal-neighbor-form"><label><span>${esc(tr('邻居名称'))}</span><input name="name" required maxlength="32" placeholder="${esc(tr('例如：花店老板 / 世界书人物'))}" ${disabled} /></label><label><span>${esc(tr('人物简述'))}</span><input name="description" maxlength="200" placeholder="${esc(tr('性格或身份一句话简介（可选）'))}" ${disabled} /></label><label><span>${esc(tr('初始地点'))}</span><select name="place_id" required ${disabled}>${placeOptions}</select></label><button class="wb-button primary" type="submit" ${disabled}>${esc(tr('一键建卡并登记为邻居'))}</button></form>`
  : `<p class="causal-meta">${esc(tr('请先在「世界地图」生成至少一个地点，再登记背景邻居。'))}</p><button type="button" class="wb-button" data-jump="map">${esc(tr('前往世界地图'))}</button>`;
 return `<div class="causal-neighbor-wizard" data-causal-key="neighbor-wizard"><p>${esc(tr('世界里目前还没有背景邻居。你可以直接从世界书人物快速建卡并登记为邻居（登记后可在上方随时启停）。'))}</p>${chipsHtml}${formHtml}</div>`;
}
function renderResidents(){
 const list=data?.residents||[];
 const residentsBody=list.length
  ? list.map(a=>`<article class="causal-resident" data-causal-key="resident:${esc(a.id)}"><strong>${esc(a.name)}</strong> ${tag(a.enabled?tr('参与自主生活'):tr('未启用'))}<p>${esc(a.activity||tr('尚未行动'))} · ${esc(placeName(a.place_id))}</p>${a.journey?`<p>${esc(tr("途中 · 预计 {0} 抵达",formatTs(a.journey.arrives_at)))}</p>`:''}<p class="causal-meta">${esc(tr("最近评估：{0}",a.last_evaluated_at?formatTs(a.last_evaluated_at):tr("尚未轮到")))} · ${esc(({advanced:tr('已执行行动'),no_change:tr('选择保持现状'),wait:tr('选择保持现状'),invalid:tr('未提交，需查看原因'),timeout:tr('模型超时'),not_evaluated:tr('尚未评估')})[a.last_evaluation_status]||a.last_evaluation_status||tr('尚未评估'))}</p>${a.last_reason?`<p class="causal-meta">${esc(tr("角色想法：{0}",a.last_reason))}</p>`:''}${canWrite()?`<button class="wb-button" data-resident="${esc(a.id)}" data-enabled="${!a.enabled}">${esc(tr(a.enabled?'停用自主生活':'启用自主生活'))}</button>`:''}</article>`).join('')
  : renderNeighborOnboarding();
 return section('residents',tr('背景居民'),residentsBody)
 +section('invitations',tr('来往与约定'),(data?.invitations||[]).map(i=>`<article class="causal-resident" data-causal-key="invitation:${esc(i.id)}"><strong>${esc(residentName(i.host))} → ${esc(residentName(i.guest))}</strong> ${tag(i.status)}<p>${time(i.when)} · ${esc(placeName(i.place_id))}</p><p>${esc(i.reason||'')}</p>${canWrite()&&!['completed','declined','cancelled'].includes(i.status)?`<button class="wb-button" data-cancel-invitation="${esc(i.id)}" data-series-text="管理取消">管理取消</button>`:''}</article>`).join('')||empty(tr('尚无自主邀请。接受、抵达与实际交流会分别记录。')));
}
function residentName(id){return id==='self'?tr('主角色'):data?.residents?.find(a=>a.id===id)?.name||id;}
function renderManage(){
 if(viewer.value!=='admin')return empty(tr('切回世界全貌可打开管理入口。'));
 return section('manage-links',tr('世界管理'),`<div class="causal-links">${[['scenes',tr('物品与动作')],['map',tr('世界地图')],['cards',tr('角色卡')],['books',tr('世界书')],['life',tr('暂停与状态纠正')],['config',tr('运行配置')],['migration',tr('数据迁移')]].map(([v,l])=>`<button class="wb-button" data-jump="${v}">${esc(l)}</button>`).join('')}</div><p class="causal-meta" data-series-text="即时布置与状态纠正会记录为管理操作。">即时布置与状态纠正会记录为管理操作。</p>`)
 +section('register',tr('登记背景居民'),`<form data-register><label><span data-series-text="已有角色卡">已有角色卡</span><select name="card_id" required><option value="" data-series-text="选择角色">选择角色</option>${(data?.cards||[]).map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select></label><label><span data-series-text="初始地点">初始地点</span><select name="place_id" required><option value="" data-series-text="选择地点">选择地点</option>${(world?.map?.places||[]).map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select></label><button class="wb-button primary" ${canWrite()?'':'disabled'} data-series-text="登记，暂不启用">登记，暂不启用</button></form><p class="causal-meta" data-series-text="共用一个后台模型和全体居民调用限额；每次仅读取一名居民的私有资料，按轮转和待回应邀请推进。">共用一个后台模型和全体居民调用限额；每次仅读取一名居民的私有资料，按轮转和待回应邀请推进。</p>`)
 +section('runtime',tr('运行状态'),`<p>${esc(tr("最近结算：{0}",formatTs(data?.last_settled_at)))}</p><p>${data?.paused?tr('世界已暂停'):tr('世界正常推进')}</p><p>${esc(tr("数据版本：{0}",data?.revision))}</p><p data-series-text="居民卡显示最近评估与选择原因；调用记录区分居民推演和主角色生活。">居民卡显示最近评估与选择原因；调用记录区分居民推演和主角色生活。</p>`);
}
function matchingNode(current,next){
 if(!current||current.nodeType!==next.nodeType||current.nodeName!==next.nodeName)return false;
 if(current.nodeType!==1)return true;
 if(current.localName==='option')return current.value===next.value;
 const key='data-causal-key';
 return current.getAttribute(key)===next.getAttribute(key)&&
   (current.hasAttribute(key)||current.className===next.className);
}

// Keep each card and its live controls mounted as the visible values change.
// The desired tree comes only from this panel's escaped templates.
function patchChildren(parent,source){
 const keyed=new Map([...parent.children]
  .filter(child=>child.hasAttribute('data-causal-key'))
  .map(child=>[child.getAttribute('data-causal-key'),child]));
 let current=parent.firstChild;
 for(const next of [...source.childNodes]){
  const key=next.nodeType===1?next.getAttribute('data-causal-key'):null;
  let match=key===null?current:keyed.get(key);
  if(parent.localName==='select'&&next.nodeName==='OPTION'&&match?.value!==next.value){
   match=[...parent.options].find(option=>option.value===next.value);
  }
  if(!matchingNode(match,next))match=null;
  if(!match){
   parent.insertBefore(next,current);
   continue;
  }
  if(match!==current){
   if(typeof parent.moveBefore==='function'&&parent.isConnected&&match.isConnected)parent.moveBefore(match,current);
   else parent.insertBefore(match,current);
  }
  if(match.nodeType===1){
   for(const attr of [...match.attributes]){
    if(match.localName==='details'&&attr.name==='open')continue;
    if(!next.hasAttribute(attr.name))match.removeAttribute(attr.name);
   }
   for(const attr of next.attributes){
    if(match.getAttribute(attr.name)!==attr.value)match.setAttribute(attr.name,attr.value);
   }
   const selected=match.localName==='select'?match.value:null;
   patchChildren(match,next);
   if(selected!==null&&match.value!==selected&&[...match.options].some(option=>option.value===selected)){
    match.value=selected;
   }
  }else if(match.nodeValue!==next.nodeValue){
   match.nodeValue=next.nodeValue;
  }
  current=match.nextSibling;
 }
 while(current){
  const next=current.nextSibling;
  current.remove();
  current=next;
 }
}

function render(){
 if(panel.hidden)return;
 setText(title,msg(tabs.find(([k])=>k===active)?.[1]||'生活观察'));
 setText(status,errorText||(!scope?tr('请先选择会话'):replaying?
  tr('当前为历史回放；以下面板显示最后同步的实时资料，管理已禁用'):stale?
  tr('连接中断 · 最后同步 ')+formatTs(lastSync/1000):lastSync?tr('已同步 ')+formatTs(lastSync/1000):tr('正在读取')));
 const view=active+'|'+viewer.value;
 const body=data?({now:renderNow,agenda:renderAgenda,events:renderEvents,residents:renderResidents,manage:renderManage}[active])():
  empty(stale?tr('请重试读取当前角色的生活记录。'):tr('等待当前角色的生活记录。'))+
  (stale?`<button class="wb-button" data-retry>${esc(tr('重试'))}</button>`:'');
 if(view===renderedView&&body===renderedBody)return;
 const template=document.createElement('template');
 template.innerHTML=body;
 if(view===renderedView){
  const scroll=content.scrollTop;
  patchChildren(content,template.content);
  if(content.scrollTop!==scroll)content.scrollTop=scroll;
 }else{
  content.replaceChildren(template.content);
  content.scrollTop=0;
 }
 renderedView=view;
 renderedBody=body;
}
async function refresh(){
 if(panel.hidden||!scope||!viewerAvailable())return;
 const request=++seq,requestedScope=scope,who=viewer.value;
 try{
  const next=await apiGet('causal',{umo:scope,viewer:who==='admin'?'admin':'actor',actor_id:who==='admin'?'self':who});
  if(request!==seq||scope!==requestedScope||who!==viewer.value||!viewerAvailable())return;
  data=next;lastSync=Date.now();stale=false;
  if(who==='admin'&&Array.isArray(next.residents)){
   menuResidents=next.residents;
   paintViewer();
  }
  render();
 }catch(e){if(request===seq){stale=true;errorText=e.message;render();}}
}
function makeRequestId(){
 const crypto=globalThis.crypto;
 if(typeof crypto.randomUUID==='function')return crypto.randomUUID();
 return Array.from(crypto.getRandomValues(new Uint8Array(16)),byte=>byte.toString(16).padStart(2,'0')).join('');
}
async function mutate(body){
 if(!canWrite())return;
 const requestedScope=scope;
 const own=scopeSerial;
 const current=()=>own===scopeSerial&&requestedScope===scope;
 loading=true;errorText='';render();
 try{await apiPost('causal',{...body,umo:requestedScope,expected_revision:data.revision,request_id:makeRequestId()});if(current())await worldStream.refreshNow({fresh:true});}
 catch(e){if(current())errorText=e.message;}
 if(current())await refresh();
 if(current()){loading=false;render();}
}
content.addEventListener('click',e=>{
 if(e.target.closest('[data-retry]')){errorText='';refresh();}
 const jump=e.target.closest('[data-jump]');if(jump){close.click();document.dispatchEvent(new CustomEvent('cabin-open-view',{detail:{view:jump.dataset.jump,drawer:true}}));}
 const sceneAction=e.target.closest('[data-scene-action]');
 if(sceneAction&&canWrite()){
  const own=scopeSerial;
  sceneAction.disabled=true;
  apiPost('scene',{umo:scope,action:sceneAction.dataset.sceneAction,expected_revision:world.scene.revision})
   .then(()=>{if(own===scopeSerial)return worldStream.refreshNow({fresh:true});})
   .catch(err=>{if(own===scopeSerial){status.textContent=err.message;sceneAction.disabled=false;}});
 }
 const regenBtn=e.target.closest('[data-regen-plan]');
 if(regenBtn&&canWrite()){
  const requestedScope=scope,own=scopeSerial;
  const current=()=>own===scopeSerial&&requestedScope===scope;
  loading=true;errorText=tr('正在保留已发生历史并重新生成今日日程…');render();
  apiPost('life',{action:'regenerate_plan',umo:requestedScope})
   .then(res=>{if(current())errorText=tr('今日日程已重新生成（{0} 项安排）。',res?.count??(res?.daily_plan?.length||0));})
   .catch(err=>{if(current())errorText=tr('日程重新生成失败：')+err.message;})
   .finally(async()=>{
    if(current())await Promise.allSettled([worldStream.refreshNow({fresh:true}),refresh()]);
    if(current()){loading=false;render();}
   });
  return;
 }
 const r=e.target.closest('[data-resident]');if(r)mutate({action:'resident_enabled',actor_id:r.dataset.resident,enabled:r.dataset.enabled==='true'});
 const i=e.target.closest('[data-cancel-invitation]');if(i)mutate({action:'cancel_invitation',invitation_id:i.dataset.cancelInvitation});
 const qn=e.target.closest('[data-quick-neighbor]');
 if(qn&&canWrite()){
  const defaultPlace=world?.map?.places?.[0]?.id||'';
  if(defaultPlace)mutate({action:'quick_register_neighbor',name:qn.dataset.nbName||'',description:qn.dataset.nbDesc||'',place_id:defaultPlace});
 }
});
content.addEventListener('submit',e=>{
 e.preventDefault();const form=e.target,fd=new FormData(form);
 if(form.matches('[data-register]'))mutate({action:'resident',card_id:fd.get('card_id'),place_id:fd.get('place_id')});
 if(form.matches('[data-quick-neighbor-form]'))mutate({action:'quick_register_neighbor',name:String(fd.get('name')||'').trim(),description:String(fd.get('description')||'').trim(),place_id:String(fd.get('place_id')||'').trim()});
 if(form.dataset.agenda){const mode=e.submitter?.value||'deferred';const c={id:form.dataset.agenda,status:mode,reason:fd.get('reason')};if(mode==='deferred'){c.start=new Date(fd.get('start')).getTime()/1000;c.end=new Date(fd.get('end')).getTime()/1000;if(!Number.isFinite(c.start)||!Number.isFinite(c.end)){status.textContent=tr('请填写延期起止时间（浏览器本地时区）。');return;}}mutate({action:'agenda',changes:[c]});}
});
worldStream.subscribe(next=>{
 if(worldStream.scope!==document.getElementById('dwScope').value.trim())return;
 if(!next||scope!==worldStream.scope||
   (world?.revisions?.binding!==undefined&&world.revisions.binding!==next.revisions?.binding))resetScope(worldStream.scope);
 if(!next)return;
 const causalChanged=world?.causal_life!==next.causal_life;
 world=next;
 if(next.causal_life&&causalChanged){
  menuResidents=next.causal_life.residents||[];
  // Keep the native picker mounted until blur, but revoke an absent actor
  // immediately. A deferred option never grants access to its old content.
  if(!viewerAvailable()){
   seq++;data=null;lastActorRevision=null;
  }
  paintViewer();
 }
 if(viewer.value==='admin'){
  lastSync=Date.now();stale=false;
  if(next.causal_life)data={...data,...next.causal_life,can_write:next.can_write};
 }else{
  // Reload only when the revision governing receipts or resident state changes.
  // The primary actor also sees condition updates computed without a revision bump.
  const revision=viewer.value==='self'?next.revisions?.causal:next.causal_life?.revision;
  if(!panel.hidden&&viewerAvailable()&&revision!==lastActorRevision){
   lastActorRevision=revision;
   void refresh();
  }
 }
 render();
});
worldStream.onError(()=>{stale=true;render();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!e.defaultPrevented&&!panel.hidden&&!document.querySelector('dialog[open]')){e.preventDefault();close.click();}});
document.addEventListener('dw-replay-change',e=>{replaying=Boolean(e.detail?.active);render();});
function paintViewer({force=false}={}){
 // A native mobile picker can be open while the select retains focus.
 if(!force&&document.activeElement===viewer){deferredViewer=true;return;}
 deferredViewer=false;
 const selected=viewer.value;
 const wanted=[
  ['admin',tr('世界全貌')],['self',tr('主角色所知')],
  ...menuResidents.map(actor=>[actor.id,tr('{0}所知',actor.name)]),
 ];
 const options=new Map([...viewer.options].map(option=>[option.value,option]));
 let anchor=viewer.firstElementChild;
 for(const [value,label] of wanted){
  let option=options.get(value);
  if(!option){option=node('option');option.value=value;}
  if(option.textContent!==label)option.textContent=label;
  if(option!==anchor)viewer.insertBefore(option,anchor);
  anchor=option.nextElementSibling;
  options.delete(value);
 }
 for(const option of options.values())option.remove();
 if(!options.has(selected)||!selected)return;
 viewer.value='admin';
 seq++;data=null;lastActorRevision=null;
 render();void refresh();
}
viewer.addEventListener('blur',()=>{if(deferredViewer)paintViewer({force:true});});

function resetScope(next){
 scope=next;scopeSerial++;data=null;world=null;menuResidents=[];viewer.value='admin';seq++;
 stale=false;lastSync=0;errorText='';loading=false;lastActorRevision=null;
 paintViewer({force:true});
 renderedView='';renderedBody='';
 content.replaceChildren();
 render();
}
function updateScope(){
 const next=document.getElementById('dwScope').value.trim();
 if(next===scope)return;
 resetScope(next);void refresh();
}
document.addEventListener('world-scope-ready',updateScope);
window.addEventListener('series-languagechange',()=>{
 paintViewer();
 if(!panel.hidden){
  render();
  scheduleMobileLayout();
 }
});
paintViewer({force:true});
