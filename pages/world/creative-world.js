import {msg,tr,setText,apply,feedback} from './series-ui.js';
import {apiGet,apiPost,formatTs} from './api.js';
import {icon} from './room-art.js';
import {worldStream} from './world-stream.js?v=round2.1';
const $=id=>document.getElementById(id),el=(tag,value)=>{const n=document.createElement(tag);if(value!=null)setText(n,value);return n;};
let view='',projectData=null,projectScope='',selected='',detailRevision=-1,projectTicket=0,projectBusy=false;
let feedTicket=0,feedScope='',feedCursor=null,feedBusy=false,historyBrowsing=false;
function panel(name,label,html){let tab=$('tab-'+name);if(!tab){tab=el('button',label);tab.type='button';tab.className='wb-tab';tab.id='tab-'+name;tab.dataset.view=name;tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','view-'+name);tab.tabIndex=-1;$('wbTabs').insertBefore(tab,$('tab-life'));}
  const host=el('section');host.id='view-'+name;host.className='wb-view wb-hidden';host.setAttribute('role','tabpanel');host.setAttribute('aria-labelledby',tab.id);host.innerHTML=html;$('worldContent').append(host);apply(host);}
panel('projects',msg("创作项目"),'<div class="creative-toolbar"><p id="projectStatus" role="status"></p><button id="projectRefresh" class="wb-button" type="button" data-series-text="刷新项目">刷新项目</button></div><div id="projectCurrent" class="wb-notice"></div><p class="dw-meta" data-series-text="进度来自已经保存的构思、初稿、修订和定稿回执。旧笔记不会自动改成项目，原版本始终保留。">进度来自已经保存的构思、初稿、修订和定稿回执。旧笔记不会自动改成项目，原版本始终保留。</p><div class="project-layout"><div id="projectList"></div><section class="wb-panel"><header><h2 id="projectDetailTitle" data-series-text="作品与版本">作品与版本</h2></header><div id="projectDetail" class="wb-panel-body"><p class="wb-empty" data-series-text="选择一个项目查看已保存的文字。">选择一个项目查看已保存的文字。</p></div></section></div>');
panel('activity',msg("世界动态"),'<div class="creative-toolbar"><label class="wb-field"><span data-series-text="动态分类">动态分类</span><select id="activityCategory"><option value="all" data-series-text="全部变化">全部变化</option><option value="projects" data-series-text="创作项目">创作项目</option><option value="room" data-series-text="房间布置">房间布置</option><option value="movement" data-series-text="位置与行程">位置与行程</option><option value="admin" data-series-text="管理设置">管理设置</option><option value="errors" data-series-text="未完成与被拒提案">未完成与被拒提案</option></select></label><button id="activityRefresh" class="wb-button" type="button" data-series-text="刷新到最新">刷新到最新</button></div><p id="activityStatus" role="status" class="dw-meta"></p><div id="activityCurrent" class="wb-notice"></div><p class="dw-meta" data-series-text="下方来自程序完成记录与操作回执。计划尚未完成时只出现在“正在进行”；日记叙述仍可在“生活与故事”查看。">下方来自程序完成记录与操作回执。计划尚未完成时只出现在“正在进行”；日记叙述仍可在“生活与故事”查看。</p><ol id="activityList" class="world-feed"></ol><button id="activityMore" class="wb-button" type="button" hidden data-series-text="查看更早记录">查看更早记录</button>');
function status(id,value,error=false){$(id).classList.toggle('error',error);feedback($(id),value,error?'error':'info');}
const projectStats=el('div');projectStats.id='projectStats';projectStats.className='project-stats';$('projectCurrent').after(projectStats);
function current(node,data){node.replaceChildren();node.classList.add('creative-current');const mark=el('div');mark.className='creative-current-icon';mark.append(icon(data.paused?'pause':data.action?'clock':'room'));const copy=el('div');copy.className='creative-current-copy';node.append(mark,copy);
  if(data.paused){copy.append(el('strong',msg("生活已暂停")),el('p',msg("项目与行动进度保留。")));return;}
  if(data.action){copy.append(el('strong',msg('正在进行：{0}',data.action.label)),el('p',msg('预计 {0} 完成当前步骤；尚未作为完成记录显示。',formatTs(data.action.step_ends_at))));}
  else copy.append(el('strong',msg("此刻没有正在执行的行动")),el('p',msg("接下来的变化，会在实际完成后留下记录。")));}
async function loadProjects(){
  const umo=$('dwScope').value.trim(),own=++projectTicket;if(!umo){status('projectStatus',msg("请先选择会话"));return;}
  if(projectScope!==umo){projectScope=umo;selected='';detailRevision=-1;$('projectDetail').replaceChildren(el('p',msg("请选择项目")));}
  try{const data=await apiGet('projects',{umo});if(own!==projectTicket||umo!==$('dwScope').value.trim())return;projectData=data;current($('projectCurrent'),data);
    $('projectStats').replaceChildren(...[['active',msg("进行中"),'book'],['paused',msg("已暂停"),'pause'],['completed',msg("已定稿"),'check']].map(([state,label,kind])=>{const card=el('div');card.className='project-stat';const symbol=el('span');symbol.className='project-stat-icon';symbol.append(icon(kind));const copy=el('div');copy.append(el('span',label),el('strong',data.projects.filter(p=>p.status===state).length));card.append(symbol,copy);return card;}));
    const nodes=data.projects.map(p=>{const card=el('article');card.className='wb-panel project-card'+(selected===p.id?' selected':'');card.dataset.projectId=p.id;
      const heading=el('h3',p.title),badge=el('span',p.status==='paused'?msg("已暂停"):p.status==='completed'?msg("已定稿"):msg(p.stage_label));badge.className='wb-tag';
      const progress=el('progress');progress.max=p.target_parts*2+2;progress.value=1+p.draft_parts+p.revised_parts+(p.status==='completed'?1:0);setText(progress,msg('{0} · {1}',p.title,msg('项目阶段')),'aria-label');
      card.dataset.status=p.status;const top=el('div');top.className='project-card-top';const emblem=el('div');emblem.className='project-emblem';emblem.append(icon('book'));const info=el('div');info.className='project-card-title';const eyebrow=el('span','WRITING PROJECT');eyebrow.className='creative-eyebrow';info.append(eyebrow,heading);top.append(emblem,info,badge);
      const stages=el('ol');stages.className='project-stage-strip';stages.setAttribute('aria-label',msg("项目阶段"));for(const [name,done] of [[msg("构思"),true],[msg("初稿"),p.draft_parts===p.target_parts],[msg("修订"),p.revised_parts===p.target_parts],[msg("定稿"),p.status==='completed']]){const stage=el('li',name);stage.className=done?'done':'';stages.append(stage);}
      card.append(top,stages,progress,el('p',msg('初稿 {0}/{1} 段 · 已修订 {2}/{1} 段',p.draft_parts,p.target_parts,p.revised_parts)),el('p',msg('最近更新 {0}',formatTs(p.updated_at))));
      const row=el('div');row.className='wb-row';const open=el('button',msg("查看作品与版本"));open.type='button';open.className='wb-button';open.onclick=()=>{selected=p.id;detailRevision=-1;loadDetail(p);};row.append(open);
      if(p.status!=='completed'){const toggle=el('button',p.status==='paused'?msg("继续项目"):msg("暂停项目"));toggle.type='button';toggle.className='wb-button';toggle.dataset.projectToggle=p.id;toggle.disabled=projectBusy||!data.can_write;
        toggle.onclick=()=>controlProject(p);row.append(toggle);}card.append(row);return card;});
    const empty=el('div');empty.className='project-empty';const illustration=el('div');illustration.className='project-empty-art';illustration.append(icon('book'));empty.append(illustration,el('h3',data.available===false?msg("先准备一处创作空间"):msg("等待第一份构思")),el('p',data.available===false?msg("尚未建立房间与物品，请先在安装引导中准备纸本或电脑。"):msg("还没有持续创作项目。角色有合适创作意图时，可以从构思开始；保存的文字会在这里持续积累。")));
    $('projectList').replaceChildren(...(nodes.length?nodes:[empty]));
    status('projectStatus',msg('{0} 个项目 · {1}',data.projects.length,worldStream.isSSEActive?'SSE 实时同步':'自动同步'));
    const active=data.projects.find(p=>p.id===selected);
    if(active&&detailRevision!==active.revision)await loadDetail(active);
    if(selected&&!active){selected='';detailRevision=-1;$('projectDetail').replaceChildren(el('p',msg("该项目不属于当前世界。")));}
  }catch(e){if(own===projectTicket)status('projectStatus',e.message,true);}
}
async function loadDetail(project){
  const umo=projectScope,id=project.id;status('projectStatus',msg("正在读取已保存版本…"));
  try{const data=await apiGet('projects',{umo,project_id:id});if(projectScope!==umo||selected!==id)return;
    if(data.project.revision<(projectData?.projects.find(p=>p.id===id)?.revision||0))return;
    const expanded=$('projectDetail').dataset.projectId===id?new Set([...$('projectDetail').querySelectorAll('details[open]')].map(n=>n.dataset.recordId)):new Set();
    detailRevision=data.project.revision;setText($('projectDetailTitle'),data.project.title);$('projectDetail').replaceChildren();$('projectDetail').dataset.projectId=id;
    for(const [index,r] of data.project.records.entries()){const details=el('details');details.className='project-version';details.dataset.recordId=r.record_id;details.open=expanded.has(r.record_id)||(!expanded.size&&index===data.project.records.length-1);
      const label={project_start:msg("构思"),project_write:msg("初稿"),project_revise:msg("修订")}[r.operation]||msg("记录");details.append(el('summary',`${label}${r.section?' · '+tr('第 {0} 段',r.section):''} · ${r.title||msg("记录缺失")} · ${formatTs(r.created_at)}`));
      const content=el('pre',r.missing?msg("原始记录无法读取，未补写正文。"):r.text);content.className='project-text';details.append(content);$('projectDetail').append(details);}
    status('projectStatus',msg("已读取保存的版本；未完成的写作不会出现在这里。"));
  }catch(e){if(projectScope===umo&&selected===id)status('projectStatus',e.message,true);}
}
async function controlProject(project){
  if(projectBusy||!projectData)return;projectBusy=true;const umo=projectScope;
  try{await apiPost('projects',{umo,action:project.status==='paused'?'resume':'pause',expected_revision:projectData.scene_revision,project_id:project.id});
    if(umo===projectScope){await loadProjects();status('projectStatus',project.status==='paused'?msg("项目已恢复，可在后续日常中继续。"):msg("项目已暂停，已保存版本保留。"));}}
  catch(e){if(umo===projectScope)status('projectStatus',e.message,true);}
  finally{projectBusy=false;for(const button of document.querySelectorAll('[data-project-toggle]'))button.disabled=!projectData?.can_write;}
}
async function loadFeed(reset=true,automatic=false){
  if(feedBusy&&!reset)return;const umo=$('dwScope').value.trim();if(!umo){status('activityStatus',msg("请先选择会话"));return;}
  if(automatic&&historyBrowsing)return;
  if(feedScope!==umo){feedScope=umo;reset=true;}
  const own=++feedTicket;feedBusy=true;$('activityMore').disabled=true;
  try{const data=await apiGet('activity',{umo,category:$('activityCategory').value,...(!reset&&feedCursor?{before:feedCursor}:{})});if(own!==feedTicket||umo!==$('dwScope').value.trim())return;
    if(reset){$('activityList').replaceChildren();historyBrowsing=false;}else historyBrowsing=true;
    current($('activityCurrent'),data.current);
    if(data.current.phase==='travelling')$('activityCurrent').prepend(el('p',msg('角色正在途中{0}',data.current.destination?msg('，前往{0}',data.current.destination):'')));
    else if(data.current.place)$('activityCurrent').prepend(el('p',data.current.place+' · '+(data.current.room||msg("房间待确认"))));
    const existing=new Set([...$('activityList').children].map(n=>n.dataset.eventId));
    for(const event of data.events){if(existing.has(event.id))continue;const row=el('li');row.dataset.eventId=event.id;row.className='feed-entry '+event.status;
      const category=event.project_id?'book':event.title.startsWith('房间布置')?'room':event.scope==='角色地图历史'?'move':event.source==='管理员'?'settings':'clock';const mark=el('div');mark.className='feed-marker';mark.append(icon(['failed','rejected'].includes(event.status)?'warning':category));
      const content=el('div');content.className='feed-content';const meta=el('div');meta.className='feed-meta';meta.append(el('time',formatTs(event.occurred_at)),el('span',event.source));content.append(meta,el('h3',event.title));if(event.description)content.append(el('p',event.description));const scope=el('small',event.scope);scope.className='feed-scope';content.append(scope);
      if(event.project_id){const button=el('button',msg("查看对应项目"));button.type='button';button.className='wb-button tiny';button.onclick=()=>{selected=event.project_id;projectScope=umo;detailRevision=-1;if(document.body.dataset.stageMode==='cabin-drawer'){document.dispatchEvent(new CustomEvent('cabin-open-view',{detail:{view:'projects',drawer:true}}));}else{$('tab-projects')?.click();}};content.append(button);}row.append(mark,content);$('activityList').append(row);}
    if(!$('activityList').children.length){const empty=el('li',msg("还没有这类完成记录。"));empty.className='wb-empty';$('activityList').append(empty);}
    feedCursor=data.next_cursor;$('activityMore').hidden=!feedCursor;
    status('activityStatus',msg('更新于 {0}{1}',formatTs(data.server_time),msg(historyBrowsing?' · 查看较早记录，自动刷新已暂停':(worldStream.isSSEActive?' · SSE 实时同步':' · 自动同步'))));
  }catch(e){if(own===feedTicket)status('activityStatus',e.message,true);}
  finally{if(own===feedTicket){feedBusy=false;$('activityMore').disabled=false;}}
}
let lastStreamRevKey='';
worldStream.subscribe(snap=>{
  if(!snap||document.hidden)return;
  const rev=snap.revisions||{};
  const key=`${worldStream.scope}|${rev.scene??''}|${rev.position??''}|${rev.life??''}|${rev.causal??''}|${rev.binding??''}`;
  if(key===lastStreamRevKey)return;
  lastStreamRevKey=key;
  if(view==='projects')loadProjects();
  if(view==='activity')loadFeed(true,true);
});
$('projectRefresh').onclick=loadProjects;$('activityRefresh').onclick=()=>loadFeed(true);$('activityCategory').onchange=()=>loadFeed(true);$('activityMore').onclick=()=>loadFeed(false);
document.addEventListener('world-view',event=>{view=event.detail;if(view==='projects')loadProjects();if(view==='activity')loadFeed(true);});
document.addEventListener('world-scope-ready',()=>{lastStreamRevKey='';if(view==='projects')loadProjects();if(view==='activity')loadFeed(true);});
$('dwScope').addEventListener('change',()=>{lastStreamRevKey='';if(view==='projects')loadProjects();if(view==='activity')loadFeed(true);});
// Defensive fallback only when SSE stream is unavailable
setInterval(()=>{if(document.hidden||worldStream.isSSEActive)return;if(view==='projects')loadProjects();if(view==='activity')loadFeed(true,true);},30000);
