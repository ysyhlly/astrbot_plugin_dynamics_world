import {apiGet,apiPost} from './api.js';
import {msg,setText,feedback} from './series-ui.js';
import {messages} from './series-messages.js';
import {avatarMessages} from './avatar-messages.js';
import {matchOutfitTexture} from './avatar-model.js';
Object.assign(messages,avatarMessages);
const make=(tag,value,cls='')=>{const n=document.createElement(tag);n.className=cls;if(value!=null)setText(n,value);return n;};
const option=(value,text)=>{const n=make('option',text);n.value=value;return n;};
export function installAvatarUI(host){
 let scope='',sample=null,chosen=null,catalog=null,renderer=null,dirty=false,busy=false,serial=0,modelSerial=0,guestSerial=0,loaded='',pending='',guestLoaded='',guestPending='',canWrite=false,draftRevision=0;
 let refreshRequest=null,nextCatalogRefresh=0,catalogFailed=false,writeSerial=0,failedModelKey='',modelRetryAt=0,failedGuestKey='',guestRetryAt=0;
 const box=make('section',null,'avatar-panel');box.id='cabinAvatar';const heading=make('h3',msg('角色模型'));box.append(heading);
 const controls=make('div',null,'avatar-controls'),model=make('select'),texture=make('select'),save=make('button',msg('应用模型'),'wb-button primary');model.id='avatarModel';texture.id='avatarTexture';save.id='avatarApply';save.type='button';
 for(const [label,node] of [['角色模型',model],['贴图',texture]]){const wrap=make('label',null,'wb-field');wrap.append(make('span',msg(label)),node);controls.append(wrap);}controls.append(save);box.append(controls);
 const settings=make('details',null,'avatar-bindings');settings.append(make('summary',msg('绑定显示区域')));const bindingRows=make('div',null,'avatar-controls'),home=make('select'),garden=make('select');home.id='avatarHomeRoom';garden.id='avatarGardenRoom';
 for(const [label,node] of [['室内房间',home],['花园区域',garden]]){const wrap=make('label',null,'wb-field');wrap.append(make('span',msg(label)),node);bindingRows.append(wrap);}settings.append(bindingRows);box.append(settings);
 const upload=make('details',null,'avatar-upload');upload.append(make('summary',msg('导入 YSM 模型')));upload.append(make('p',msg('支持未加密 YSM ZIP 或模型 JSON（最大 8 MiB）；加密 .ysm 文件需先向作者获取未加密源文件。'),'dw-meta'));
 const file=make('input');file.type='file';file.accept='.zip,.json,.ysm';file.id='avatarFile';setText(file,msg('导入 YSM 模型'),'aria-label');const importButton=make('button',msg('导入 YSM 模型'),'wb-button');importButton.id='avatarImport';importButton.type='button';upload.append(file,importButton);box.append(upload);
 const status=make('p');status.id='avatarFeedback';status.setAttribute('role','status');box.append(status);
 const actor=make('div',null,'avatar-current');actor.id='avatarCurrent';actor.setAttribute('aria-live','polite');const location=make('strong',msg('等待真实角色状态')),action=make('p',''),warning=make('small','');actor.append(location,action,warning);box.append(actor,make('p',msg('位置跟随真实房间和行动；室内与花园中的具体站位是动作示意。'),'dw-meta'));host.append(box);
 function lock(){for(const n of [model,texture,home,garden,file,save,importButton])n.disabled=busy||!canWrite;}
 function textures(){const names=catalog?.models.find(m=>m.id===model.value)?.texture_names||[];texture.replaceChildren(...(names.length?names.map((name,index)=>option(String(index),name)):[option('0','—')]));}
 function fill(data){catalog=data;draftRevision=data.selection.revision;model.replaceChildren(...data.models.map(m=>option(m.id,m.id==='builtin'?msg('内置像素角色'):m.name)));model.value=data.selection.model_id;textures();texture.value=String(data.selection.texture_index);
  for(const select of [home,garden])select.replaceChildren(option('',msg('不绑定')),...data.rooms.map(r=>option(r.id,r.name)));
  home.value=data.selection.home_room_id;garden.value=data.selection.garden_room_id;
 }
 function projection(value,diagnostics){if(!value){setText(location,msg('等待真实角色状态'));setText(action,'');return;}
  setText(location,value.locationLabel||msg('角色不在已绑定的小屋或花园中'));
  const microLabel=value.micro?.active&&value.micro?.label?value.micro.label:'';
  setText(action,value.label||microLabel||msg({idle:'站立',walk:'走动',read:'读书',write:'写笔记',rest:'休息',sleep:'睡觉',cook:'做饭',eat:'用餐',wash:'洗漱',sweep:'打扫',water:'浇水',game:'玩游戏',stroll:'散步'}[value.pose]||'等待真实角色状态'));
  setText(warning,diagnostics?.mode==='static'&&value.pose!=='idle'?msg('模型缺少当前动作，使用静态姿态。'):value.paused?msg('生活已暂停'):'');
  actor.dataset.location=value.location;actor.dataset.pose=value.pose;actor.dataset.visible=String(value.visible);
 }
 function effectiveTextureIndex(){
  if(!chosen)return 0;
  if(!dirty&&sample?.outfit_now&&catalog?.models){
   const m=catalog.models.find(it=>it.id===chosen.model_id);
   const matched=matchOutfitTexture(sample.outfit_now,m?.texture_names||[]);
   if(Number.isInteger(matched)&&matched>=0)return matched;
  }
  return chosen.texture_index;
 }
 async function applyGuestRenderer(){
  if(!renderer||typeof renderer.setGuestAvatarModel!=='function')return;
  const guest=sample?.world_space?.active_guest||sample?.world_space?.active_visit||null;
  const gModelId=guest?.model_id||'builtin';
  const gTex=Number.isFinite(Number(guest?.texture_index))?Number(guest.texture_index):0;
  if(!guest||gModelId==='builtin'){
   if(guestLoaded&&guestLoaded!=='builtin'){guestLoaded='builtin';await renderer.setGuestAvatarModel(null,gTex);}
   return;
  }
  const gKey=`${scope}|${gModelId}|${gTex}`;
  if(guestLoaded===gKey||guestPending===gKey||(failedGuestKey===gKey&&Date.now()<guestRetryAt))return;
  const ticket=++guestSerial;guestPending=gKey;
  try{
   const gData=await apiGet('avatar_model',{umo:scope,model_id:gModelId});
   if(ticket!==guestSerial)return;
   const ok=await renderer.setGuestAvatarModel(gData,gTex);
   if(ticket===guestSerial){if(ok){guestLoaded=gKey;failedGuestKey='';}else{failedGuestKey=gKey;guestRetryAt=Date.now()+5000;}}
  }catch{if(ticket===guestSerial){failedGuestKey=gKey;guestRetryAt=Date.now()+5000;}}
  finally{if(ticket===guestSerial)guestPending='';}
 }
 async function applyRenderer(){
  if(!renderer||!chosen||!sample)return;
  const texIdx=effectiveTextureIndex();
  renderer.setActorState(sample,{...chosen,texture_index:texIdx});
  applyGuestRenderer();
  const key=scope+'|'+chosen.model_id+'|'+texIdx;if(loaded===key||pending===key||(failedModelKey===key&&Date.now()<modelRetryAt))return;
  const ticket=++modelSerial;pending=key;
  try{const data=await apiGet('avatar_model',{umo:scope,model_id:chosen.model_id});if(ticket!==modelSerial)return;
   const applied=await renderer.setAvatarModel(data,texIdx);if(ticket!==modelSerial)return;if(applied){loaded=key;failedModelKey='';}else{failedModelKey=key;modelRetryAt=Date.now()+5000;}
   if(data.warnings?.length)feedback(status,data.warnings.join(' · '),'warning');return applied;
  }catch(error){if(ticket===modelSerial){failedModelKey=key;modelRetryAt=Date.now()+5000;feedback(status,error.message,'error');}return false;}
  finally{if(ticket===modelSerial)pending='';}
 }
 async function refresh(data,nextScope,force=false){
  sample=data;
  if(scope!==nextScope){scope=nextScope;chosen=null;catalog=null;loaded='';pending='';guestLoaded='';guestPending='';dirty=false;busy=false;canWrite=false;refreshRequest=null;nextCatalogRefresh=0;catalogFailed=false;failedModelKey='';failedGuestKey='';++serial;++modelSerial;++guestSerial;++writeSerial;for(const n of [model,texture,home,garden])n.replaceChildren();file.value='';setText(status,'');lock();renderer?.setActorState(null,{});projection(null);}
  if(force){failedModelKey='';failedGuestKey='';}
  if(chosen)void applyRenderer();
  if(!scope||busy)return;
  if(refreshRequest)return refreshRequest;
  if(!force&&Date.now()<nextCatalogRefresh)return;
  const ticket=++serial;
  const requestScope=scope;
  // World snapshots arrive much more often than model or room settings change.
  // Reuse the pending read and refresh the catalog at most once per 30 seconds.
  const request=(async()=>{
   await Promise.resolve();
   try{const response=await apiGet('avatar',{umo:requestScope});if(ticket!==serial||scope!==requestScope||busy)return;chosen=response.selection;canWrite=response.can_write;
    nextCatalogRefresh=Date.now()+30000;
    if(catalogFailed){catalogFailed=false;feedback(status,'');}
    if(!catalog||!dirty&&!box.contains(document.activeElement))fill(response);else catalog=response;
    lock();await applyRenderer();
   }catch(error){if(ticket===serial){nextCatalogRefresh=Date.now()+5000;catalogFailed=true;canWrite=false;lock();feedback(status,error.message,'error');}}
   finally{if(refreshRequest===request)refreshRequest=null;}
  })();
  refreshRequest=request;
  return request;
 }
 model.onchange=()=>{dirty=true;textures();};for(const node of [texture,home,garden])node.onchange=()=>{dirty=true;};
 save.onclick=async()=>{if(busy||!chosen)return;busy=true;++serial;refreshRequest=null;nextCatalogRefresh=0;lock();const current=scope,ticket=++writeSerial;const active=()=>ticket===writeSerial&&current===scope;
  try{const result=await apiPost('avatar',{umo:current,model_id:model.value,texture_index:Number(texture.value),home_room_id:home.value,garden_room_id:garden.value,expected_revision:draftRevision});if(!active())return;chosen=result;draftRevision=result.revision;dirty=false;loaded='';failedModelKey='';const applied=await applyRenderer();if(active()&&applied!==false)feedback(status,msg('角色模型与区域绑定已保存。'),'success');}
  catch(error){if(active())feedback(status,error.message,'error');}finally{if(active()){busy=false;lock();}}
 };
 importButton.onclick=async()=>{if(busy)return;const selected=file.files?.[0];if(!selected){feedback(status,msg('请选择模型文件'),'error');return;}if(selected.size>8*1024*1024){feedback(status,'模型包最大 8 MiB','error');return;}
  busy=true;++serial;refreshRequest=null;nextCatalogRefresh=0;lock();feedback(status,msg('正在导入模型…'),'loading');const current=scope,ticket=++writeSerial;const active=()=>ticket===writeSerial&&current===scope;
  try{const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('无法读取模型文件'));reader.readAsDataURL(selected);});
   if(!active())return;
   const result=await apiPost('avatar_upload',{umo:current,filename:selected.name,name:selected.name.replace(/\.[^.]+$/,''),file_base64:encoded});if(!active())return;
   const response=await apiGet('avatar',{umo:current});if(!active())return;chosen=response.selection;fill(response);model.value=result.id;textures();dirty=true;feedback(status,msg('模型已导入，点击应用模型后生效。'),'success');
  }catch(error){if(active())feedback(status,error.message,'error');}finally{if(active()){busy=false;lock();}}
 };
 lock();
 return {
  refresh,
  preview(replayData){
   sample=replayData;
   if(renderer&&chosen&&replayData){
    renderer.setActorState(replayData,{...chosen,texture_index:effectiveTextureIndex()});
    applyGuestRenderer();
   }
  },
  getSelection(){return chosen?{...chosen}:null;},
  attach(value){renderer=value;loaded='';pending='';guestLoaded='';guestPending='';failedModelKey='';failedGuestKey='';++modelSerial;++guestSerial;renderer.onActorState(projection);applyRenderer();},
  unavailable(){sample=null;renderer?.setActorState(null,chosen||{});projection(null);},
  clear(){++serial;++modelSerial;++guestSerial;++writeSerial;scope='';chosen=null;sample=null;catalog=null;loaded='';pending='';guestLoaded='';guestPending='';dirty=false;busy=false;canWrite=false;refreshRequest=null;nextCatalogRefresh=0;catalogFailed=false;failedModelKey='';failedGuestKey='';for(const n of [model,texture,home,garden])n.replaceChildren();file.value='';setText(status,'');lock();renderer?.setActorState(null,{});projection(null);},
 };
}
