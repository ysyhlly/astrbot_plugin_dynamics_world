import {msg,tr,setText,apply,feedback} from './series-ui.js';
import {apiPost,formatTs} from './api.js';
import {renderSchematic} from './room-schematic.js';
const $=id=>document.getElementById(id);
let latest=null,scope='',refresh=null,selectedRoom='',selectedEntity='',follow=true,contextKey='';
const text=(tag,value)=>{const n=document.createElement(tag);setText(n,value);return n;};
export function bindRoomDesign(reload){
  refresh=reload;
  const host=document.createElement('section');host.id='roomDesign';host.className='dw-room-design';
  host.style.cssText='margin:20px 0;padding-top:18px;border-top:1px solid var(--wb-border)';
  host.innerHTML='<div class="dw-weather-heading"><div><h3 data-series-text="房间二维示意图">房间二维示意图</h3><p id="roomDesignState" class="dw-meta"></p></div><button type="button" class="wb-button" id="roomDesignToggle" data-series-text="暂停自主布置">暂停自主布置</button></div><label class="wb-field"><span data-series-text="查看房间">查看房间</span><select id="roomDesignRoom"></select></label><p id="roomActorLocation" class="dw-meta"></p><div id="roomSchematic"></div><details open><summary data-series-text="家具与摆位清单">家具与摆位清单</summary><div id="roomDesignFurniture" class="dw-scene-items"></div></details><p id="roomDesignFixtures"></p><div id="roomDesignChanges"></div><p class="dw-meta" data-series-text="布置在动作完成后保存。原底图继续提供建筑和美术参考，当前摆位、灯光和窗帘优先。">布置在动作完成后保存。原底图继续提供建筑和美术参考，当前摆位、灯光和窗帘优先。</p>';
  $('sceneItems').before(host);apply(host);
  host.querySelector('.dw-weather-heading').style.alignItems='center';
  host.classList.add('room-design-workbench');
  const eyebrow=text('p','ROOM / LIVE');eyebrow.className='room-eyebrow';host.querySelector('h3').before(eyebrow);
  $('roomDesignToggle').onclick=async()=>{
    const d=latest?.room_designs?.find(d=>d.room_id===selectedRoom);if(!d)return;
    const button=$('roomDesignToggle');button.disabled=true;
    try{await apiPost('scene',{umo:scope,action:'room_design',expected_revision:latest.revision,room_id:d.room_id,place_id:latest.rooms.find(r=>r.id===d.room_id)?.place_id,enabled:!d.enabled});await refresh();}
    catch(e){feedback($('roomDesignState'),e.message,'error');}
    finally{button.disabled=!!latest?.action||latest?.visual_profile?.can_write===false;}
  };
  $('roomDesignRoom').onchange=()=>{selectedRoom=$('roomDesignRoom').value;selectedEntity='';follow=false;renderRoomDesign(latest,scope);};
}
export function renderRoomDesign(scene,currentScope){
  latest=scene;scope=currentScope;
  const key=currentScope+'|'+(scene.visual_profile?.mode||'');
  if(contextKey!==key){contextKey=key;selectedRoom='';selectedEntity='';follow=true;}
  const designs=scene.room_designs||[];
  if(follow&&designs.some(d=>d.room_id===scene.room_id))selectedRoom=scene.room_id;
  if(!designs.some(d=>d.room_id===selectedRoom))selectedRoom=designs[0]?.room_id||'';
  $('roomDesignRoom').replaceChildren(...designs.map(d=>{const option=text('option',d.room_name);option.value=d.room_id;return option;}));$('roomDesignRoom').value=selectedRoom;
  const d=designs.find(d=>d.room_id===selectedRoom);
  $('roomDesign').hidden=!d;if(!d)return;
  setText($('roomDesignState'),(d.enabled?msg("允许角色自主布置"):msg("自主布置已暂停"))+' · '+(d.history.length?msg('最近 {0} 次调整',d.history.length):msg("保持当前布置")));
  setText($('roomDesignToggle'),d.enabled?msg("暂停自主布置"):msg("允许自主布置"));
  $('roomDesignToggle').disabled=!!scene.action||scene.visual_profile?.can_write===false;
  $('roomDesignToggle').title=scene.action?msg("当前行动完成或取消后可切换"):scene.visual_profile?.can_write===false?msg("面板处于只读模式"):'';
  setText($('roomActorLocation'),scene.phase==='travelling'?msg('角色正在途中{0}，不在此房间。',scene.destination?msg('，前往{0}',scene.destination):''):scene.phase==='unknown'?msg("角色位置待确认，尚未认定在此房间。"):scene.room_id===d.room_id?msg("角色当前在此房间；室内具体位置未记录。"):msg('角色当前在：{0} · {1}',scene.place_name||msg('待定位'),scene.room_name||msg('房间待确认')));
  renderSchematic($('roomSchematic'),scene,d,selectedEntity,id=>{selectedEntity=id;renderRoomDesign(latest,scope);},{
    canWrite:scene.visual_profile?.can_write!==false,
    onMoveFurniture:async(design,furn,slotKey)=>{
      try{
        await apiPost('scene',{umo:scope,action:'admin_arrange',room_id:design.room_id,steps:[{kind:'move_furniture',target_id:furn.id,position:slotKey,room_id:design.room_id}]});
        feedback($('roomDesignState'),`${furn.name} 已移至新摆位。`,'success');
        if(refresh)await refresh();
      }catch(e){feedback($('roomDesignState'),e.message,'error');}
    },
  });
  $('roomDesignFurniture').replaceChildren(...d.furniture.map(f=>{const card=text('article','');card.className='dw-scene-item';card.append(text('strong',f.name),text('p',msg(f.position_label)),text('small',f.movable?msg("可按需要移动"):msg("固定设施")));return card;}));
  setText($('roomDesignFixtures'),msg('{0} · {1}',msg(d.lighting_label||''),msg(d.curtains_label||'')));
  $('roomDesignChanges').replaceChildren(...d.history.slice(-4).reverse().map(c=>text('p',`${formatTs(c.occurred_at)} · ${c.origin==='life_model'?msg("自主布置"):msg("管理操作")} · ${c.name}：${c.before} → ${c.after}`)));
}
