import {msg,tr,setText,apply,feedback} from './series-ui.js';
/* Deterministic schematic of persisted areas, not generated artwork or measured geometry. */
import {roomFloor,furnitureArt,itemArt,icon} from './room-art.js';
const NS='http://www.w3.org/2000/svg';
let expanded=false;
const floor={left_wall:[150,245],right_wall:[750,245],back_wall:[450,95],center:[450,260]};
const defaults={bed:[150,245],desk:[750,245],chair:[450,300],bookcase:[450,95],lamp:[760,270],window:[830,150],fixture:[150,100]};
function svgNode(tag,attrs={}){const node=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));return node;}
function clamp([x,y]){return [Math.max(85,Math.min(815,x)),Math.max(75,Math.min(445,y))];}
function anchor(design,kind,seen){const f=design.furniture.find(f=>f.kind===kind);return f?locate(design,f,seen):defaults[kind]||[450,260];}
function position(design,code,seen=new Set()){
  if(floor[code])return [...floor[code]];
  let p;
  if(code==='near_window'){p=anchor(design,'window',seen);return clamp([p[0]>450?p[0]-40:p[0]+40,p[1]+60]);}
  if(code==='bedside'){p=anchor(design,'bed',seen);return clamp([p[0]+105,p[1]+70]);}
  if(['desk_left','desk_right','desktop'].includes(code)){p=anchor(design,'desk',seen);return clamp([p[0]+(code==='desk_left'?-70:code==='desk_right'?70:0),p[1]+45]);}
  if(code==='bookshelf'){p=anchor(design,'bookcase',seen);return clamp([p[0],p[1]+55]);}
  if(code==='entry_rack')return anchor(design,'fixture',seen);
  return [450,400];
}
function locate(design,f,seen=new Set()){
  if(seen.has(f.id))return defaults[f.kind]||[450,260];
  const next=new Set(seen);next.add(f.id);
  let p=position(design,f.position,next);
  if(f.kind==='window'&&f.position==='right_wall')p=[850,140];
  if(f.kind==='window'&&f.position==='left_wall')p=[50,140];
  if(f.kind==='window'&&f.position==='back_wall')p=[450,40];
  if(f.kind==='desk'&&f.position==='right_wall')p=[685,245];
  if(f.kind==='lamp'&&['desk_left','desk_right'].includes(f.position)){const desk=anchor(design,'desk',next);p=[desk[0]+(f.position==='desk_left'?-70:70),desk[1]-28];}
  if(f.kind==='chair'&&f.position==='near_window'){const window=anchor(design,'window',next);p=[window[0]>450?window[0]-140:window[0]+140,window[1]+10];}
  if(f.kind==='chair'&&f.position!=='near_window')p=[p[0],Math.min(425,p[1]+65)];
  return p;
}
function defaultPosition(value){
  if(/书桌.{0,3}右/.test(value))return 'desk_right';
  if(/书桌.{0,3}左/.test(value))return 'desk_left';
  if(/书桌|桌面/.test(value))return 'desktop';
  if(/床边|床头/.test(value))return 'bedside';
  if(/书架|书柜/.test(value))return 'bookshelf';
  if(/伞架|收纳架/.test(value))return 'entry_rack';
  return null;
}
function itemPoint(design,code){
  if(['desk_left','desk_right','desktop'].includes(code)){const p=anchor(design,'desk',new Set());return [p[0]+(code==='desk_left'?-55:code==='desk_right'?55:0),p[1]+8];}
  if(code==='bookshelf'){const p=anchor(design,'bookcase',new Set());return [p[0],p[1]+4];}
  return position(design,code);
}
export function renderSchematic(host,scene,design,selected,select){
  const oldCanvas=host.querySelector('.room-canvas'),scroll=[oldCanvas?.scrollLeft||0,oldCanvas?.scrollTop||0];
  const focus=host.contains(document.activeElement)?document.activeElement?.getAttribute('data-entity-id'):null;
  host.replaceChildren();
  const toolbar=document.createElement('div');toolbar.className='room-view-toolbar';
  const heading=document.createElement('div');heading.className='room-view-heading';heading.append(icon('room'));const headingText=document.createElement('div');const roomTitle=document.createElement('strong');setText(roomTitle,design.room_name);const roomHint=document.createElement('span');setText(roomHint,msg('{0} 件家具 · {1} 件室内物品',design.furniture.length,(scene.items||[]).filter(i=>!i.carried&&i.room_id===design.room_id).length));headingText.append(roomTitle,roomHint);heading.append(headingText);toolbar.append(heading);
  const zoom=document.createElement('button');zoom.type='button';zoom.className='wb-button tiny';setText(zoom,expanded?msg("适配宽度"):msg("放大查看"));zoom.setAttribute('aria-pressed',String(expanded));zoom.onclick=()=>{expanded=!expanded;renderSchematic(host,scene,design,selected,select);};toolbar.append(zoom);host.append(toolbar);
  const frame=document.createElement('div');frame.className='room-view-frame';host.append(frame);
  const canvas=document.createElement('div');canvas.className='room-canvas';canvas.tabIndex=0;canvas.setAttribute('aria-label',msg("房间图，可放大后滚动查看"));
  const svg=svgNode('svg',{viewBox:'0 0 900 520',role:'group','aria-label':tr('{0}的区域示意图',design.room_name),class:'dw-room-svg'});
  if(expanded)svg.style.cssText=`width:${Math.max(1000,Math.round(host.clientWidth*1.3))}px;max-width:none;max-height:none`;
  roomFloor(svg);
  const entries=[];
  for(const f of design.furniture){
    entries.push({id:f.id,name:f.name,kind:f.kind,position:f.position,point:locate(design,f),basis:'confirmed',description:msg('{0}{1}',msg(f.position_label),f.movable?msg(' · 可移动'):msg(' · 固定设施')),furniture:true});
  }
  const unresolved=[],inventory=[];
  for(const item of scene.items||[]){
    if(item.carried){inventory.push(item);continue;}
    if(item.room_id!==design.room_id)continue;
    let code=item.arranged_room_id===design.room_id?item.arranged_position:null,basis='confirmed',description=item.placement;
    if(!code){const profile=scene.visual_profile?.profile?.items?.[item.id];if(profile?.home_room_id===design.room_id){code=defaultPosition(profile.placement);description=profile.placement;basis='reference';}}
    if(!code){unresolved.push(item);continue;}
    const point=itemPoint(design,code);
    entries.push({id:item.id,name:item.name,kind:item.kind,point,basis,description:description||msg("已确认摆放"),appearance:scene.visual_profile?.profile?.items?.[item.id]?.appearance||'',item});
  }
  if(['bright','warm','dim'].includes(design.lighting))for(const entry of entries.filter(e=>e.furniture&&e.kind==='lamp'))svg.append(svgNode('ellipse',{cx:entry.point[0],cy:entry.point[1],rx:110,ry:90,fill:'url(#room-lamp-glow)',opacity:design.lighting==='dim'?.24:design.lighting==='bright'?.55:.42}));
  const groups=new Map();
  for(const entry of entries){
    const key=entry.point.join(',')+(entry.furniture?'f':'i'),index=groups.get(key)||0;groups.set(key,index+1);
    const [x,y]=entry.kind==='window'?entry.point:clamp([entry.point[0],entry.point[1]+index*(entry.furniture?65:32)]);
    const group=svgNode('g',{transform:`translate(${x},${y})`,role:'button',tabindex:0,'aria-label':entry.name+'，'+entry.description,'data-entity-id':entry.id,class:'room-node '+(entry.furniture?'furniture':'item')+(entry.basis==='reference'?' reference':'')+(selected===entry.id?' selected':'')});
    group.append(entry.furniture?furnitureArt(entry,design):itemArt(entry));
    const title=svgNode('title');setText(title,entry.name+' · '+entry.description+(entry.basis==='reference'?msg("（基础参考摆位）"):''));group.append(title);
    group.addEventListener('click',()=>select(entry.id));group.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(entry.id);}});svg.append(group);
  }
  canvas.append(svg);frame.append(canvas);canvas.scrollLeft=scroll[0];canvas.scrollTop=scroll[1];
  if(focus){const node=[...svg.querySelectorAll('[data-entity-id]')].find(n=>n.getAttribute('data-entity-id')===focus);node?.focus({preventScroll:true});}
  const side=document.createElement('aside');side.className='room-inspector';frame.append(side);
  const loose=[...inventory,...unresolved].find(i=>i.id===selected);
  const picked=entries.find(e=>e.id===selected)||(loose?{name:loose.name,kind:loose.kind,item:loose,basis:loose.carried?'carried':'unknown',description:loose.carried?msg("角色正在随身携带"):msg("在本房间，具体摆位尚未登记")}:null);
  const panel=document.createElement('div');panel.className='room-selection';panel.append(icon(picked?.furniture?'room':picked?'book':'room'));const title=document.createElement('strong');setText(title,picked?.name||msg("点选房间里的物件"));panel.append(title);
  const line=document.createElement('p');setText(line,picked?.description||msg("查看它的位置、状态与摆放依据。"));panel.append(line);
  if(picked){const basis=document.createElement('span');basis.className='room-basis';setText(basis,{confirmed:picked.furniture?msg("已登记的家具位置"):msg("动作确认的摆位"),reference:msg("基础设定的参考摆位"),carried:msg("随身物品"),unknown:msg("摆位待确认")}[picked.basis]);panel.append(basis);
    if(picked.item){const i=picked.item;for(const value of [i.kind==='computer'?(i.powered?msg("电脑已开机"):msg("电脑已关机")):'',i.kind==='umbrella'?(i.open?msg("雨伞已撑开"):msg("雨伞已收起")):'',i.wet?msg("当前潮湿"):'',i.note_count!=null?msg('已保存 {0} 条纸本记录',i.note_count):'',i.document_count!=null?msg('已保存 {0} 份草稿',i.document_count):'',i.servings!=null?msg('水量 {0}/{1}',i.servings,i.capacity):'']){if(value){const status=document.createElement('p');status.className='room-fact';setText(status,value);panel.append(status);}}}}
  side.append(panel);
  for(const [label,items] of [[msg("本房间内，具体摆位尚未登记"),unresolved],[msg("角色随身携带，不在房间内重复摆放"),inventory]]){
    if(!items.length)continue;const block=document.createElement('div');block.className='room-side-list';const line=document.createElement('p');setText(line,label);block.append(line);for(const item of items){const button=document.createElement('button');button.type='button';button.className='room-item-chip';setText(button,item.name);button.onclick=()=>select(item.id);block.append(button);}side.append(block);
  }
  const note=document.createElement('p');note.className='room-view-legend';setText(note,msg("外形与尺寸为示意，摆位与状态读取已保存数据。实线：登记或动作确认；虚线：基础参考摆位。"));host.append(note);
}
