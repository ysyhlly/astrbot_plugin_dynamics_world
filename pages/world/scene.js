import {apiPost,formatTs} from './api.js';
import {msg,setText,tr} from './series-ui.js';
import {bindVisual,renderVisual,resetVisual} from './visual-editor.js';
import {bindRoomDesign,renderRoomDesign} from './room-design.js';
import {worldStream} from './world-stream.js?v=round2.1';
const $=id=>document.getElementById(id);
let scene=null,doc=null,scope='',steps=[];
let scopeSerial=0;
const NO_TARGET_STEPS=['leave','rest','dry','water_garden','harvest_garden','prepare_meal','brew_tea','open_mailbox'];
export function resetScene(){scopeSerial++;scene=null;doc=null;scope='';steps=[];drawSteps();resetVisual();$('sceneContents').hidden=true;$('sceneBootstrap').hidden=true;$('sceneStatus').textContent=tr('等待有效会话的场景');}
const labels={enter:'进入',leave:'到入口',take:'拿取',put:'放下',read:'阅读',drink:'喝水',refill:'补水',open_umbrella:'撑伞',fold_umbrella:'收伞',rest:'休息',dry:'晾干',travel:'前往',write_note:'写笔记',read_notes:'翻阅笔记',power_on:'开机',power_off:'关机',computer_work:'使用电脑',water_garden:'浇灌花菜',harvest_garden:'采收花菜',prepare_meal:'下厨备餐',brew_tea:'冲泡花草茶',open_mailbox:'查收信箱',move_furniture:'移动家具',place_item:'摆放物品',set_lighting:'调整灯光',set_curtains:'调整窗帘',display_note:'展示纸页'};
function text(tag,value){const n=document.createElement(tag);n.textContent=String(value??'');return n;}
function options(id,rows,empty){const n=$(id),old=n.value;n.replaceChildren(...(empty?[{id:'',name:empty},...rows]:rows).map(r=>{const o=text('option',r.name);o.value=r.id;return o;}));if([...n.options].some(o=>o.value===old))n.value=old;}
function targetName(id){return [...(scene?.items||[]),...(scene?.rooms||[]),...(doc?.places||[])].find(x=>x.id===id)?.name||'';}
function writingFields(kind){const body={};if(kind==='computer_work')body.mode=$('sceneComputerMode').value;if(kind==='write_note'||kind==='computer_work'&&body.mode==='writing'){body.title=$('sceneDraftTitle').value.trim()||'未命名记录';body.text=$('sceneDraftText').value.trim();}return body;}
const actionLabel=kind=>labels[kind]?tr(labels[kind]):kind;
function drawSteps(){$('sceneSteps').replaceChildren(...steps.map(s=>text('li',actionLabel(s.kind)+(s.target_id?' '+targetName(s.target_id):''))));}
function targetOptions(){const k=$('sceneStepKind').value;options('sceneStepTarget',k==='enter'?scene?.rooms||[]:k==='travel'?doc?.places||[]:NO_TARGET_STEPS.includes(k)?[]:scene?.items||[]);$('sceneStepTarget').disabled=NO_TARGET_STEPS.includes(k);}
function roomFields(){const r=(scene?.rooms||[]).find(r=>r.id===$('sceneRoom').value);$('sceneRoomName').value=r?.name||'';$('sceneRoomShelter').value=r?.sheltered===false?'no':'yes';$('sceneRoomAccess').value=r?.accessible===false?'no':'yes';$('sceneRoomWater').value=r?.water?'yes':'no';}
function placeFields(){if(!scene)return;const id=$('scenePlace').value,p=scene.places[id]||{};$('scenePlaceKind').value=p.kind||'unknown';$('sceneShelter').value=p.sheltered===true?'yes':p.sheltered===false?'no':'unknown';$('sceneOpen').value=p.open===false?'no':'yes';$('sceneOpens').value=p.opens??0;$('sceneCloses').value=p.closes??24;const rooms=scene.rooms.filter(r=>r.place_id===id);options('sceneRoom',rooms,tr('新建房间'));options('sceneItemRoom',rooms,tr('地点入口'));roomFields();}
export function renderScene(data,map,currentScope){
  const changedScope=scope!==currentScope;scope=currentScope;doc=map;scene=data;
  if(changedScope){scopeSerial++;steps=[];drawSteps();}
  options('sceneHome',doc?.places||[]);$('sceneBootstrap').hidden=!!scene?.available;$('sceneContents').hidden=!scene?.available;
  if(!scene?.available){$('sceneStatus').textContent=tr('当前地图尚未启用房间和物品。原有生活记录保持不变。');return;}
  const oldPlace=$('scenePlace').value;options('scenePlace',doc?.places||[]);if(changedScope||!oldPlace)placeFields();
  $('sceneStatus').textContent=tr("场景 v{0} · {1}", scene.revision, scene.paused?tr('生活已暂停'):tr('状态持续保存'));
  $('sceneWhere').textContent=`${scene.place_name||tr('待定位')} · ${scene.room_name}`;
  $('sceneCondition').textContent=tr("{0} · 衣物湿度 {1}%", scene.sheltered===true?tr('有遮蔽'):scene.sheltered===false?tr('室外 / 无遮蔽'):tr('遮蔽情况待确认'), scene.wetness);
  renderVisual(scene,currentScope);
  renderRoomDesign(scene,currentScope);
  const action=scene.action,last=scene.last_action;
  $('sceneAction').textContent=action?tr("{0}{1} · 第 {2}/{3} 步 · 预计 {4} 完成当前步骤", action.origin==='life_model'?tr('自主日常 · '):action.origin==='admin'?tr('管理操作 · '):'', action.label, action.index+1, action.steps.length, formatTs(action.step_ends_at)):last?tr("上次流程：{0}{1}", {completed:tr('完成'),cancelled:tr('已取消'),failed:tr('失败')}[last.status]||last.status, last.reason?' · '+last.reason:''):tr('当前没有行动流程');
  $('sceneActionProgress').value=action?.progress||0;
  $('sceneCancel').disabled=!action||scene.paused;
  const hasComputer=scene.items.some(i=>i.kind==='computer');
  document.querySelector('[data-scene-preset="computer_work"]').hidden=!hasComputer;
  $('sceneComputerMode').closest('label').hidden=!hasComputer;
  setText($('sceneWriting').querySelector('summary'),msg(hasComputer?'写笔记与使用电脑':'写笔记'));
  setText($('sceneWriting').querySelector('p.dw-meta'),msg(hasComputer?'内容在动作完成后保存。这里的电脑是虚拟设施，不操作宿主电脑或真实网络；角色自主写作时自行选择内容。':'笔记在动作完成后保存。'));
  document.querySelectorAll('[data-scene-preset]').forEach(n=>n.disabled=!!action||scene.paused||(n.dataset.scenePreset==='computer_work'&&!scene.items.some(i=>i.kind==='computer')));
  $('sceneStart').disabled=!!action||scene.paused;
  const expanded=new Set([...$('sceneItems').querySelectorAll('details[open]')].map(n=>n.dataset.itemId));
  $('sceneItems').replaceChildren(...scene.items.map(i=>{const card=document.createElement('div');card.className='dw-scene-item';card.append(text('strong',i.name),text('p',i.carried?tr('随身携带'):`${targetName(i.place_id)||tr('原地点')} · ${targetName(i.room_id)||tr('入口')}`));const info=i.kind==='book'?tr("书签 {0}/{1} 页", i.page, i.pages):i.kind==='water'?tr("余量 {0}/{1} 份", i.servings, i.capacity):i.kind==='notebook'?tr("已保存 {0} 条笔记", i.note_count??i.notes?.length??0):i.kind==='computer'?tr("{0} · 草稿 {1} 篇 · 游戏 {2} 分钟", i.powered?tr('已开机'):tr('已关机'), i.document_count??i.documents?.length??0, i.gaming_minutes||0):i.open?tr('已撑开'):tr('已收起');card.append(text('small',info+(i.wet?tr(' · 潮湿，待晾干'):'')));const rows=i.notes||i.documents||[];if(rows.length){const details=document.createElement('details');details.dataset.itemId=i.id;details.open=expanded.has(i.id);details.append(text('summary',tr('查看保存的内容')));for(const row of [...rows].reverse()){details.append(text('strong',row.title),text('p',row.text));}card.append(details);}return card;}));
  $('sceneReceipts').replaceChildren(...scene.receipts.slice(0,6).map(r=>text('p',`${formatTs(r.occurred_at)} · ${{'scene.initialized':tr('建立当前场景设定'),'step.completed':tr('步骤完成'),'action.started':tr('流程开始'),'action.completed':tr('流程完成'),'action.failed':tr('流程失败'),'action.cancelled':tr('取消后续步骤'),'action.rejected':tr('自主提案未执行')}[r.kind]||tr('管理员调整')}${r.origin==='life_model'?tr(' · 自主日常流程'):r.origin==='admin'?tr(' · 管理流程'):''}${r.reason?' · '+r.reason:''}${r.reason_code?' · '+r.reason_code:''}${r.operation?' · '+(labels[r.operation]||r.operation):''}${r.target_id?' · '+targetName(r.target_id):''}`)));
  targetOptions();
}
export function bindScene(refresh,status){
  bindVisual(refresh);
  bindRoomDesign(refresh);
  async function act(n,body,after){
    const umo=$('dwScope').value.trim(), own=scopeSerial;
    const current=()=>own===scopeSerial&&umo===$('dwScope').value.trim();
    n.disabled=true;
    try{
      if(!umo||scope!==umo)throw new Error(tr('请先选择会话'));
      await apiPost('scene',{umo,expected_revision:scene?.revision||0,...body()});
      if(!current())return;
      if(after)after();
      await refresh({afterWrite:true});
    }catch(e){if(current())status(e.message,true);}
    finally{
      if(current()){
        const latest=worldStream.getSnapshot();
        const sceneAction=latest?.scene?.action;
        n.disabled=(n.id==='sceneCancel'&&!sceneAction)||
          ((n.id==='sceneStart'||n.dataset.scenePreset)&&Boolean(sceneAction||latest?.scene?.paused));
      }
    }
  }
  function action(id,body,after){const n=$(id);n.onclick=()=>act(n,body,after);}
  action('sceneInitialize',()=>({action:'bootstrap',place_id:$('sceneHome').value}),placeFields);
  action('sceneCancel',()=>({action:'cancel'}));
  document.querySelectorAll('[data-scene-preset]').forEach(n=>n.onclick=()=>act(n,()=>({action:'preset',preset:n.dataset.scenePreset,target_id:$('mapDestination').value,...writingFields(n.dataset.scenePreset)})));
  $('sceneStepKind').onchange=targetOptions;$('scenePlace').onchange=placeFields;$('sceneRoom').onchange=roomFields;
  $('sceneAddStep').onclick=()=>{if(steps.length>=6){status(tr('最多 6 步'),true);return;}const kind=$('sceneStepKind').value;steps.push({kind,...writingFields(kind),...(!NO_TARGET_STEPS.includes(kind)?{target_id:$('sceneStepTarget').value}:{})});drawSteps();};
  $('sceneClearSteps').onclick=()=>{steps=[];drawSteps();};
  action('sceneStart',()=>({action:'start',steps}),()=>{steps=[];drawSteps();});
  action('sceneSavePlace',()=>({action:'place',place_id:$('scenePlace').value,kind:$('scenePlaceKind').value,sheltered:$('sceneShelter').value==='unknown'?null:$('sceneShelter').value==='yes',open:$('sceneOpen').value==='yes',opens:Number($('sceneOpens').value),closes:Number($('sceneCloses').value)}),placeFields);
  action('sceneSaveRoom',()=>({action:'room',place_id:$('scenePlace').value,room_id:$('sceneRoom').value||null,name:$('sceneRoomName').value.trim(),sheltered:$('sceneRoomShelter').value==='yes',accessible:$('sceneRoomAccess').value==='yes',water:$('sceneRoomWater').value==='yes'}),placeFields);
  action('sceneAddItem',()=>({action:'item',place_id:$('scenePlace').value,room_id:$('sceneItemRoom').value||null,kind:$('sceneItemKind').value,name:$('sceneItemName').value.trim()}));
}
