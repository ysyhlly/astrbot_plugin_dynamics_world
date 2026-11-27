import {tr} from './series-ui.js';
import {apiGet,apiPost} from './api.js';
const $=id=>document.getElementById(id);
let scene=null,scope='',contextKey='',base=0,profile=null,catalog=[],latest=null,refresh=null,busy=false,dirty=new Set(),serial=0;
const cache=new Map();
const clone=value=>JSON.parse(JSON.stringify(value));
function message(value,error=false){$('visStatus').textContent=value;$('visStatus').classList.toggle('error',error);}
function options(id,rows,empty='请选择'){const node=$(id),value=node.value;node.replaceChildren();const add=(key,label)=>{const o=document.createElement('option');o.value=key;o.textContent=label;node.append(o);};add('',empty);for(const row of rows)add(row.id,row.name);node.value=value;}
function assetOptions(){for(const id of ['visStyle1','visStyle2','visRoomAsset']){const role=id==='visRoomAsset'?'layout':'style';options(id,catalog.filter(a=>a.role===role).map(a=>({id:a.asset_id,name:a.label})),role==='style'?'不使用参考图':'请选择房间底图');}}
function mark(section){dirty.add(section);message('有未保存修改；自动刷新不会覆盖你的编辑。');controls();}
function controls(){
  const writable=latest?.can_write!==false;
  for(const n of $('visualEditor').querySelectorAll('[data-visual-write]'))n.disabled=busy||!writable;
  $('visRoom').disabled=busy||dirty.has('room');$('visItem').disabled=busy||dirty.has('item');
  $('visReload').disabled=busy;
  $('visSaveStyle').disabled=busy||!writable||!dirty.has('style');
  $('visSaveRoom').disabled=busy||!writable||!dirty.has('room');
  $('visSaveItem').disabled=busy||!writable||!dirty.has('item');
  $('visClearRoom').disabled=busy||!writable||!profile?.rooms?.[$('visRoom').value];
  $('visClearItem').disabled=busy||!writable||!profile?.items?.[$('visItem').value];
  $('visReadonly').hidden=writable;
}
async function preview(selectId,hostId){
  const host=$(hostId),id=$(selectId).value,own=serial,asset=catalog.find(a=>a.asset_id===id);
  host.replaceChildren();
  if(!asset){host.textContent=id?'参考素材缺失，请重新选择。':'尚未选择参考图';return;}
  const key=asset.asset_id+':'+asset.sha256;
  host.textContent='正在读取预览…';
  try{
    let data=cache.get(key);
    if(!data){data=await apiGet('visual_asset',{umo:scope,asset_id:id});cache.set(key,data);if(cache.size>32)cache.delete(cache.keys().next().value);}
    if(own!==serial||$(selectId).value!==id)return;
    host.replaceChildren();const image=document.createElement('img');image.src=data.data_url;image.alt=asset.label;image.loading='lazy';
    const caption=document.createElement('figcaption');caption.textContent=`${asset.label} · ${data.width} × ${data.height}`;
    const button=document.createElement('button');button.type='button';button.className='vis-image-button';button.title='放大查看参考图';button.append(image);
    button.onclick=()=>{$('visLargeImage').src=data.data_url;$('visLargeImage').alt=asset.label;$('visImageTitle').textContent=asset.label;$('visImageDialog').showModal();};
    host.append(button,caption);
    if(/^https?:\/\//.test(asset.source_url||'')){const a=document.createElement('a');a.href=asset.source_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='查看来源';host.append(a);}
  }catch(e){if(own===serial&&$(selectId).value===id)host.textContent='预览读取失败：'+e.message;}
}
function previews(){if(!$('sceneVisual').closest('details').open)return;preview('visStyle1','visStylePreview1');preview('visStyle2','visStylePreview2');preview('visRoomAsset','visRoomPreview');}
function missingOption(id,value){if(!value)return;const node=$(id);if(![...node.options].some(o=>o.value===value)){const option=document.createElement('option');option.value=value;option.textContent='已绑定的素材缺失';node.append(option);}node.value=value;}
function roomFields(){const spec=profile?.rooms?.[$('visRoom').value];$('visRoomAsset').value=spec?.asset_id||'';missingOption('visRoomAsset',spec?.asset_id);$('visLayout').value=spec?.layout||'';previews();controls();}
function itemFields(){const spec=profile?.items?.[$('visItem').value],item=scene?.items.find(i=>i.id===$('visItem').value);$('visAppearance').value=spec?.appearance||'';$('visPlacement').value=spec?.placement||'';$('visHomeRoom').value=spec?.home_room_id||item?.room_id||'';controls();}
function fill(){
  const room=$('visRoom').value,item=$('visItem').value;
  assetOptions();$('visStyle1').value=profile.styles[0]||'';$('visStyle2').value=profile.styles[1]||'';
  options('visPreset',(latest.presets||[]).map(p=>({id:p.id,name:p.name})),'选择画风预设');$('visPreset').value=profile.style_preset||'generic';
  missingOption('visStyle1',profile.styles[0]);missingOption('visStyle2',profile.styles[1]);
  options('visRoom',scene.rooms);options('visItem',scene.items);options('visHomeRoom',scene.rooms);
  $('visRoom').value=scene.rooms.some(r=>r.id===room)?room:scene.room_id||scene.rooms[0]?.id||'';
  $('visItem').value=scene.items.some(i=>i.id===item)?item:scene.items[0]?.id||'';
  roomFields();itemFields();previews();controls();
}
export function resetVisual(){serial++;scope='';contextKey='';scene=null;profile=null;latest=null;dirty.clear();cache.clear();if($('visualEditor')){$('visualEditor').hidden=true;$('visImageDialog')?.close();}}
export function renderVisual(value,currentScope){
  if(!value?.visual_profile)return;
  const topologyChanged=JSON.stringify([scene?.rooms,scene?.items?.map(i=>[i.id,i.name])])!==JSON.stringify([value.rooms,value.items?.map(i=>[i.id,i.name])]);
  const key=currentScope+'|'+(value.map_mode||value.visual_profile.mode||'virtual');
  scene=value;latest=value.visual_profile;
  if(contextKey!==key){serial++;scope=currentScope;contextKey=key;dirty.clear();profile=null;$('visRoom').value='';$('visItem').value='';$('visFile').value='';$('visImageDialog').close();}
  $('visualEditor').hidden=false;
  const nextCatalog=JSON.stringify(latest.assets);
  const changedCatalog=JSON.stringify(catalog)!==nextCatalog;
  catalog=latest.assets||[];
  if(!profile||!busy&&!dirty.size&&(base!==latest.revision||topologyChanged)){base=latest.revision;profile=clone(latest.profile);fill();message('当前设定已保存。');}
  else if(dirty.size&&latest.revision!==base&&!busy)message('设定已在其他页面更新。你的草稿仍保留，请重新载入后再修改。',true);
  else if(changedCatalog&&!busy){assetOptions();previews();}
  controls();
}
async function save(section,body){
  const own=serial,umo=scope;
  if(busy||!umo)return;
  busy=true;controls();message('正在保存…');
  try{
    const result=await apiPost('visual',{umo,expected_revision:base,...body});
    if(own!==serial)return;
    base=result.revision;
    if(body.action==='style'){profile.styles=body.asset_ids;profile.style_preset=body.preset;}
    if(body.action==='room')profile.rooms[body.target_id]={asset_id:body.asset_id,layout:body.layout};
    if(body.action==='item')profile.items[body.target_id]={appearance:body.appearance,home_room_id:body.home_room_id,placement:body.placement};
    if(body.action==='remove')delete profile[body.kind][body.target_id];
    dirty.delete(section);message(dirty.size?'这部分已保存，其余草稿尚未保存。':'已保存，新设定会用于后续生图。');
    await refresh();
  }catch(e){if(own===serial)message(e.message+'；未覆盖你的草稿。',true);}
  finally{busy=false;controls();}
}
export function bindVisual(reload){
  refresh=reload;
  $('sceneVisual').innerHTML=`<div id="visualEditor" hidden>
    <div class="vis-toolbar"><p id="visStatus" role="status" aria-live="polite"></p><button class="wb-button" id="visReload" type="button" data-series-text="放弃草稿并重新载入">放弃草稿并重新载入</button></div>
    <p id="visReadonly" hidden data-series-text="面板当前只读，可以查看参考图和已有设定。">面板当前只读，可以查看参考图和已有设定。</p>
    <section class="vis-section"><h3 data-series-text="画风参考">画风参考</h3><label class="wb-field"><span data-series-text="画风预设">画风预设</span><select id="visPreset" data-visual-write></select></label><p class="dw-meta" data-series-text="最多两张，只参考画法和色彩，不复制图片中的地点或人物。预设只改变画风规则，不覆盖角色卡、世界书或参考图。">最多两张，只参考画法和色彩，不复制图片中的地点或人物。预设只改变画风规则，不覆盖角色卡、世界书或参考图。</p>
      <div class="vis-grid"><div><label class="wb-field"><span data-series-text="参考图一">参考图一</span><select id="visStyle1" data-visual-write></select></label><figure id="visStylePreview1" class="vis-preview"></figure></div><div><label class="wb-field"><span data-series-text="参考图二（可选）">参考图二（可选）</span><select id="visStyle2" data-visual-write></select></label><figure id="visStylePreview2" class="vis-preview"></figure></div></div>
      <button class="wb-button primary" id="visSaveStyle" type="button" data-visual-write data-series-text="保存画风参考">保存画风参考</button></section>
    <section class="vis-section"><h3 data-series-text="固定房间布局">固定房间布局</h3><div class="vis-grid"><div>
      <label class="wb-field"><span data-series-text="房间">房间</span><select id="visRoom"></select></label><label class="wb-field"><span data-series-text="房间底图">房间底图</span><select id="visRoomAsset" data-visual-write></select></label>
      <label class="wb-field"><span data-series-text="布局描述">布局描述</span><textarea id="visLayout" rows="7" maxlength="600" data-visual-write placeholder="床、窗户、书桌的位置与固定视角"></textarea></label></div><figure id="visRoomPreview" class="vis-preview"></figure></div>
      <div class="wb-row"><button class="wb-button primary" id="visSaveRoom" type="button" data-visual-write data-series-text="保存房间布局">保存房间布局</button><button class="wb-button" id="visClearRoom" type="button" data-visual-write data-series-text="解除房间绑定">解除房间绑定</button></div></section>
    <section class="vis-section"><h3 data-series-text="物品外观与默认摆放">物品外观与默认摆放</h3><div class="vis-grid">
      <label class="wb-field"><span data-series-text="物品">物品</span><select id="visItem"></select></label><label class="wb-field"><span data-series-text="默认摆放房间">默认摆放房间</span><select id="visHomeRoom" data-visual-write></select></label>
      <label class="wb-field"><span data-series-text="固定外观">固定外观</span><textarea id="visAppearance" rows="4" maxlength="200" data-visual-write placeholder="颜色、材质、形状和辨识特征"></textarea></label>
      <label class="wb-field"><span data-series-text="默认摆放位置">默认摆放位置</span><textarea id="visPlacement" rows="4" maxlength="120" data-visual-write placeholder="例如：书桌左侧，水壶旁边"></textarea></label></div>
      <p class="dw-meta" data-series-text="这里只编辑视觉设定，不会移动物品或改变开关机、水量、笔记等生活状态。">这里只编辑视觉设定，不会移动物品或改变开关机、水量、笔记等生活状态。</p>
      <div class="wb-row"><button class="wb-button primary" id="visSaveItem" type="button" data-visual-write data-series-text="保存物品外观">保存物品外观</button><button class="wb-button" id="visClearItem" type="button" data-visual-write data-series-text="解除物品外观绑定">解除物品外观绑定</button></div></section>
    <section class="vis-section"><h3 data-series-text="上传或替换参考图">上传或替换参考图</h3><p class="dw-meta" data-series-text="默认勾选“上传并立即应用”，上传完成后将自动保存并生效；取消勾选时需手动点击上方保存按钮。旧图保留在选项中，可随时选回。">默认勾选“上传并立即应用”，上传完成后将自动保存并生效；取消勾选时需手动点击上方保存按钮。旧图保留在选项中，可随时选回。</p><div class="vis-grid">
      <label class="wb-field"><span data-series-text="用途">用途</span><select id="visUploadRole" data-visual-write><option value="style" data-series-text="画风参考">画风参考</option><option value="layout" data-series-text="当前所选房间底图">当前所选房间底图</option></select></label>
      <label class="wb-field"><span data-series-text="素材名称">素材名称</span><input id="visUploadLabel" type="text" maxlength="100" data-visual-write /></label>
      <label class="wb-field"><span data-series-text="图片（PNG / JPEG / WebP，最多 8 MB）">图片（PNG / JPEG / WebP，最多 8 MB）</span><input id="visFile" type="file" accept="image/png,image/jpeg,image/webp" data-visual-write /></label>
      <label class="wb-field"><span data-series-text="来源链接（可选）">来源链接（可选）</span><input id="visUploadSource" type="url" maxlength="300" placeholder="https://…" data-visual-write /></label></div>
      <div class="wb-row"><label class="wb-check"><input id="visUploadAutoApply" type="checkbox" checked data-visual-write /><span>上传并立即应用</span></label><button class="wb-button primary" id="visUpload" type="button" data-visual-write data-series-text="上传参考图">上传参考图</button></div></section>
    </div><dialog id="visImageDialog" class="vis-dialog" aria-labelledby="visImageTitle"><header><h3 id="visImageTitle"></h3><button type="button" class="wb-button" id="visCloseImage" data-series-text="关闭预览">关闭预览</button></header><img id="visLargeImage" alt="" /></dialog>`;
  $('visCloseImage').onclick=()=>$('visImageDialog').close();
  $('sceneVisual').closest('details').addEventListener('toggle',previews);
  for(const id of ['visPreset','visStyle1','visStyle2'])$(id).onchange=()=>{mark('style');previews();};
  $('visRoom').onchange=roomFields;$('visItem').onchange=itemFields;
  $('visRoomAsset').onchange=()=>{mark('room');previews();};$('visLayout').oninput=()=>mark('room');
  for(const id of ['visAppearance','visPlacement'])$(id).oninput=()=>mark('item');$('visHomeRoom').onchange=()=>mark('item');
  $('visSaveStyle').onclick=()=>save('style',{action:'style',preset:$('visPreset').value,asset_ids:[...new Set([$('visStyle1').value,$('visStyle2').value].filter(Boolean))]});
  $('visSaveRoom').onclick=()=>save('room',{action:'room',target_id:$('visRoom').value,asset_id:$('visRoomAsset').value,layout:$('visLayout').value.trim()});
  $('visSaveItem').onclick=()=>save('item',{action:'item',target_id:$('visItem').value,home_room_id:$('visHomeRoom').value,appearance:$('visAppearance').value.trim(),placement:$('visPlacement').value.trim()});
  for(const [id,kind,target,section] of [['visClearRoom','rooms','visRoom','room'],['visClearItem','items','visItem','item']])$(id).onclick=async()=>{await save(section,{action:'remove',kind,target_id:$(target).value});if(!dirty.has(section)){section==='room'?roomFields():itemFields();}};
  $('visReload').onclick=async()=>{const own=serial;busy=true;controls();try{const fresh=await apiGet('visual',{umo:scope});if(own!==serial)return;latest=fresh;catalog=fresh.assets;profile=clone(fresh.profile);base=fresh.revision;dirty.clear();fill();message('已重新载入保存的设定。');}catch(e){message(e.message,true);}finally{busy=false;controls();}};
  $('visFile').onchange=()=>{const file=$('visFile').files[0];if(file&&!$('visUploadLabel').value)$('visUploadLabel').value=file.name.replace(/\.[^.]+$/,'').slice(0,100);};
  $('visUpload').onclick=async()=>{
    const file=$('visFile').files[0],role=$('visUploadRole').value,own=serial,umo=scope;
    if(!file){message('请先选择图片。',true);return;}
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>8*1024*1024){message('请选择不超过 8 MB 的 PNG、JPEG 或 WebP 图片。',true);return;}
    if(role==='layout'&&!$('visRoom').value){message('请先选择要替换底图的房间。',true);return;}
    busy=true;controls();message('正在上传和校验图片…');
    try{
      const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('无法读取图片'));reader.readAsDataURL(file);});
      if(own!==serial)return;
      const asset=await apiPost('visual_asset',{umo,role,label:$('visUploadLabel').value.trim(),source_url:$('visUploadSource').value.trim(),image_base64:encoded});
      if(own!==serial)return;
      catalog.push(asset);assetOptions();
      if(role==='layout'){$('visRoomAsset').value=asset.asset_id;dirty.add('room');}
      else{$('visStyle1').value=asset.asset_id;dirty.add('style');}
      previews();$('visFile').value='';
      const autoApply=$('visUploadAutoApply')?.checked!==false;
      if(autoApply){
        busy=false;
        if(role==='layout'){
          await save('room',{action:'room',target_id:$('visRoom').value,asset_id:$('visRoomAsset').value,layout:$('visLayout').value.trim()});
        }else{
          await save('style',{action:'style',preset:$('visPreset').value,asset_ids:[...new Set([$('visStyle1').value,$('visStyle2').value].filter(Boolean))]});
        }
        return;
      }
      message(role==='layout'?'已上传。点击“保存房间布局”应用新底图；旧图仍可选回。':'已上传。点击“保存画风参考”应用新图片；旧图仍可选回。');
    }catch(e){if(own===serial)message(e.message,true);}
    finally{busy=false;controls();}
  };
}
