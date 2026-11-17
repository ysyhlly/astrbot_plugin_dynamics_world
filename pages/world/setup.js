import {apiGet,apiPost} from './api.js';
import {msg,setText,setSharedScope,tr} from './series-ui.js';
const $=id=>document.getElementById(id);
let data=null,first=true,busy=false,ticket=0,poll=null,textureDirty=false;
const text=(tag,value)=>{const n=document.createElement(tag);setText(n,value);return n;};
const positions={left_wall:'左侧墙边',right_wall:'右侧墙边',back_wall:'后墙旁',center:'房间中央',near_window:'窗边',bedside:'床边',desk_left:'书桌左侧',desk_right:'书桌右侧',bookshelf:'书架上',entry_rack:'收纳架'};
const furniture=[['bed','床','left_wall'],['desk','书桌','right_wall'],['chair','椅子','center'],['bookcase','书柜','back_wall'],['lamp','台灯','desk_right'],['window','窗户','right_wall'],['fixture','收纳架','left_wall']];
const node=text('section','');node.id='view-setup';node.className='wb-view wb-hidden';node.setAttribute('role','tabpanel');node.setAttribute('aria-labelledby','tab-setup');
node.innerHTML=`<div class="setup-toolbar"><p id="setupStatus" role="status" aria-live="polite" data-series-text="读取安装状态…">读取安装状态…</p><button id="setupRefresh" class="wb-button" type="button" data-series-text="刷新检查">刷新检查</button></div>
<section class="wb-panel"><header><h2 data-series-text="1 · 检查配套能力">1 · 检查配套能力</h2></header><div class="wb-panel-body"><div id="setupChecks" class="setup-checks"></div><p class="dw-meta" data-series-text="Chat Dynamics 负责原生聊天协作。视觉工坊是可选能力，缺少它仍可维护世界与日常。">Chat Dynamics 负责原生聊天协作。视觉工坊是可选能力，缺少它仍可维护世界与日常。</p><button id="setupGrant" class="wb-button" type="button" data-setup-write data-series-text="授权世界参考图目录">授权世界参考图目录</button></div></section>
<section class="wb-panel"><header><h2 data-series-text="2 · 选择角色、模型与会话">2 · 选择角色、模型与会话</h2></header><div class="wb-panel-body"><div class="wb-grid-2">
<label class="wb-field"><span data-series-text="世界画风预设">世界画风预设</span><select id="setupPreset" data-setup-write></select></label><label class="wb-field"><span data-series-text="已有角色">已有角色</span><select id="setupCard" data-setup-write></select></label>
<label class="wb-field"><span data-series-text="生活模型">生活模型</span><select id="setupProvider" data-setup-write></select></label><label class="wb-field"><span data-series-text="会话标识">会话标识</span><input id="setupUmo" type="text" maxlength="300" placeholder="平台:GroupMessage:群号" data-setup-write /></label></div>
<p class="dw-meta" data-series-text="保存会同步所选角色的人格并绑定这一个会话，不覆盖其他会话。切换正在运行的生活角色前需先关闭接入。">保存会同步所选角色的人格并绑定这一个会话，不覆盖其他会话。切换正在运行的生活角色前需先关闭接入。</p><button id="setupConfigure" class="wb-button primary" type="button" data-setup-write data-series-text="保存角色与模型绑定">保存角色与模型绑定</button>
<details><summary data-series-text="创建新角色或导入入门预设">创建新角色或导入入门预设</summary><p id="setupPresetHint" class="dw-meta"></p><label class="wb-field"><span data-series-text="新角色名称">新角色名称</span><input id="setupNewName" type="text" maxlength="60" data-setup-write /></label><label class="wb-field"><span data-series-text="角色设定">角色设定</span><textarea id="setupNewPrompt" rows="4" maxlength="6000" data-setup-write></textarea></label><button id="setupCreate" class="wb-button" type="button" data-setup-write data-series-text="建立新角色">建立新角色</button><p class="dw-meta" data-series-text="预设只在明确新建时导入，不替换已有角色、世界书或官方参考图片。">预设只在明确新建时导入，不替换已有角色、世界书或官方参考图片。</p></details></div></section>
<section class="wb-panel"><header><h2 data-series-text="3 · 建立起始世界与房间">3 · 建立起始世界与房间</h2></header><div class="wb-panel-body"><p id="setupWorldState"></p><div class="wb-row"><label class="wb-field wb-grow"><span data-series-text="新起始地点名称">新起始地点名称</span><input id="setupPlaceName" type="text" value="住所" maxlength="60" data-setup-write /></label><button id="setupStarter" class="wb-button" type="button" data-setup-write data-series-text="建立轻量起始地图">建立轻量起始地图</button></div><p class="dw-meta" data-series-text="轻量地图无需浏览器下载。已有地图不会被覆盖；完整地形可到世界地图页生成。">轻量地图无需浏览器下载。已有地图不会被覆盖；完整地形可到世界地图页生成。</p>
<label class="wb-field"><span data-series-text="住所地点">住所地点</span><select id="setupPlace" data-setup-write></select></label><div class="wb-row"><button id="setupRooms" class="wb-button" type="button" data-setup-write data-series-text="初始化房间和物品">初始化房间和物品</button><button id="setupLocate" class="wb-button" type="button" data-setup-write data-series-text="确认初始位置">确认初始位置</button></div>
<details><summary data-series-text="登记房间家具，启用自主布置">登记房间家具，启用自主布置</summary><p class="dw-meta" data-series-text="先确认房间及初始家具；已有布置不重置。勾选需要登记的家具，可修改名称和初始位置。">先确认房间及初始家具；已有布置不重置。勾选需要登记的家具，可修改名称和初始位置。</p><label class="wb-field"><span data-series-text="房间">房间</span><select id="setupRoom" data-setup-write></select></label><div id="setupFurniture"></div><button id="setupFurnish" class="wb-button" type="button" data-setup-write data-series-text="保存初始家具">保存初始家具</button></details></div></section>
<section class="wb-panel"><header><h2 data-series-text="4 · 可选地图资源">4 · 可选地图资源</h2></header><div class="wb-panel-body"><p id="setupBrowserState"></p><button id="setupBrowser" class="wb-button" type="button" data-setup-write data-series-text="安装 Chromium">安装 Chromium</button><p class="dw-meta" data-series-text="仅详细地形生成需要 Chromium；安装会联网下载浏览器，不会改动系统软件包。">仅详细地形生成需要 Chromium；安装会联网下载浏览器，不会改动系统软件包。</p><hr /><p id="setupTextureState"></p><button id="setupDownloadTextures" class="wb-button" type="button" data-setup-write data-series-text="一键下载地图纹理">一键下载地图纹理</button><div class="wb-row"><label class="wb-field wb-grow"><span data-series-text="新生成地图的纹理">新生成地图的纹理</span><select id="setupTexture" data-setup-write></select></label><button id="setupSelectTexture" class="wb-button" type="button" data-setup-write data-series-text="保存纹理选择">保存纹理选择</button></div><p class="dw-meta" data-series-text="纹理按固定版本下载并校验，保存在数据目录，升级后保留。失败可续传重试，既有地图不会自动重绘。">纹理按固定版本下载并校验，保存在数据目录，升级后保留。失败可续传重试，既有地图不会自动重绘。</p></div></section>
<section class="wb-panel"><header><h2 data-series-text="5 · 开启聊天与日常">5 · 开启聊天与日常</h2></header><div class="wb-panel-body"><p id="setupRuntime"></p><div class="wb-row"><button id="setupEnable" class="wb-button primary" type="button" data-setup-write data-series-text="开启接入">开启接入</button><button id="setupDisable" class="wb-button" type="button" data-setup-write data-series-text="关闭接入">关闭接入</button></div><p class="dw-meta" data-series-text="关闭接入保留全部数据。开启后按已有日常规则推进，不会因安装引导自动向群发送测试消息。">关闭接入保留全部数据。开启后按已有日常规则推进，不会因安装引导自动向群发送测试消息。</p></div></section>`;
$('worldContent').append(node);
const tab=text('button',msg('安装引导'));tab.type='button';tab.className='wb-tab';tab.dataset.view='setup';tab.id='tab-setup';tab.setAttribute('role','tab');tab.setAttribute('aria-selected','false');tab.setAttribute('aria-controls','view-setup');tab.tabIndex=-1;$('wbTabs').append(tab);
const options=(id,rows,empty)=>{const n=$(id),old=n.value;n.replaceChildren();for(const row of [{id:'',name:empty},...rows]){const o=text('option',row.name);o.value=row.id;n.append(o);}n.value=old;};
function message(value,error=false){$('setupStatus').textContent=value;$('setupStatus').classList.toggle('error',error);}
function drawChecks(){
  const c=data.compatibility,media=c.visual_media;
  const labels={ready:tr('就绪'),missing:tr('未安装或未启用'),update_required:tr('需要更新配套插件'),unconfigured:tr('尚未配置图片模型'),unavailable:tr('服务暂不可用'),tools_unavailable:tr('生图工具未全部启用')};
  const rows=[['Chat Dynamics',labels[c.chat_dynamics.state]],['视觉工坊',labels[media.state]],[tr('参考图读取'),media.reference_access?tr('已授权'):tr('尚未授权')],[tr('旧插件冲突'),c.legacy_conflicts.length?c.legacy_conflicts.join('、'):tr('无冲突')]];
  $('setupChecks').replaceChildren(...rows.map(([name,value])=>{const card=text('div','');card.append(text('strong',name),text('p',value));return card;}));
}
function controls(){
  for(const n of node.querySelectorAll('[data-setup-write]'))n.disabled=busy||data?.can_write===false;
  if(!data)return;
  const w=data.world,readonly=busy||data.can_write===false,c=data.compatibility;
  $('setupGrant').disabled=readonly||!c.visual_media.grant_supported||c.visual_media.reference_access;
  $('setupStarter').disabled=readonly||w.has_map||!w.scope_bound;
  $('setupRooms').disabled=readonly||w.has_rooms||!w.has_map;
  $('setupLocate').disabled=readonly||!w.has_map||w.position!=='unknown';
  $('setupFurnish').disabled=readonly||!$('setupRoom').value||(w.designed_rooms||[]).includes($('setupRoom').value);
  $('setupBrowser').disabled=readonly||!data.browser.module_available||data.browser.installed||data.browser_install.state==='running';
  $('setupDownloadTextures').disabled=readonly||data.textures.state==='running';
  $('setupEnable').disabled=readonly||data.config.runtime_enabled||c.chat_dynamics.state!=='ready'||!!c.legacy_conflicts.length;
  $('setupDisable').disabled=readonly||!data.config.runtime_enabled;
}
function render(){
  drawChecks();options('setupCard',data.cards,msg('请选择角色'));options('setupProvider',data.providers,msg('请选择生活模型'));
  if(first){options('setupPreset',data.presets,msg('请选择预设'));$('setupPreset').value=data.visual?.profile?.style_preset||data.config.visual_style_default||'generic';
    $('setupCard').value=data.cards.find(c=>c.persona_id===data.config.persona_id)?.id||data.cards[0]?.id||'';$('setupProvider').value=data.config.narrative_provider_id||data.providers[0]?.id||'';
    $('setupUmo').value=$('dwScope').value||data.selected_umo||data.config.narrative_sessions?.[0]||'';first=false;}
  options('setupPlace',data.world.places||[],msg('请选择住所地点'));if(!$('setupPlace').value)$('setupPlace').value=data.world.places?.[0]?.id||'';
  options('setupRoom',data.world.rooms||[],msg('请选择房间'));if(!$('setupRoom').value)$('setupRoom').value=data.world.rooms?.find(r=>r.name==='房间')?.id||data.world.rooms?.[0]?.id||'';
  $('setupWorldState').textContent=[data.world.has_map?tr('地图已建立'):tr('尚无地图'),data.world.has_rooms?tr('房间与物品已建立'):tr('尚无房间'),data.world.has_furniture?tr('已有家具登记'):tr('尚未登记家具')].join(' · ');
  $('setupBrowserState').textContent=['running','failed','cancelled'].includes(data.browser_install.state)?data.browser_install.message:data.browser.installed?tr('Chromium 已安装'):data.browser.module_available?tr('Chromium 尚未安装'):tr('缺少 Playwright，请修复插件依赖安装');
  $('setupTextureState').textContent=tr("已校验 {0}/{1} 张纹理 · 总大小约 {2} MB{3}", data.textures.completed, data.textures.total, (data.textures.download_bytes/1048576).toFixed(1), data.textures.message?' · '+data.textures.message:'');
  options('setupTexture',data.textures.files.filter(f=>f.available).map(f=>({id:f.name,name:f.name})),msg('不使用纹理'));if(!textureDirty)$('setupTexture').value=data.textures.selected||'';
  $('setupRuntime').textContent=data.config.runtime_enabled?tr('聊天与持续日常已开启'):tr('当前为编辑模式，设定准备好后再开启接入。');controls();
  if(data.browser_install.state==='running'||data.textures.state==='running')poll=setTimeout(()=>load(false),2500);
}
async function load(show=true){const own=++ticket;clearTimeout(poll);try{data=await apiGet('setup',{umo:$('setupUmo').value||$('dwScope').value||''});if(own!==ticket)return;render();if(show)message(data.can_write?tr('检查完成。'):tr('当前面板为只读。'));}catch(e){message(e.message,true);}}
async function send(body){if(busy)return;busy=true;controls();message(tr('正在处理…'));try{const request={umo:$('setupUmo').value.trim(),...body};const result=await apiPost('setup',request);if(body.action==='select_texture')textureDirty=false;if(body.action==='configure')setSharedScope(request.umo);await load(false);if(['configure','create_character','activate'].includes(body.action))document.dispatchEvent(new Event('world-setup-saved'));message(result.message||tr('操作已完成，状态已刷新。'));return result;}catch(e){message(e.message,true);}finally{busy=false;controls();}}
$('setupRefresh').onclick=()=>load();$('setupUmo').onchange=()=>load();$('setupRoom').onchange=controls;
$('setupGrant').onclick=()=>send({action:'grant_references'});
$('setupConfigure').onclick=()=>send({action:'configure',config_revision:data.config_revision,card_id:$('setupCard').value,provider_id:$('setupProvider').value,preset:$('setupPreset').value});
function showPreset(){const p=data?.presets.find(p=>p.id===$('setupPreset').value);$('setupPresetHint').textContent=p?.description||'';$('setupNewName').value=p?.character?.name||'';$('setupNewPrompt').value=p?.character?.system_prompt||'';}
$('setupPreset').onchange=showPreset;
$('setupCreate').onclick=async()=>{const r=await send({action:'create_character',preset:$('setupPreset').value,name:$('setupNewName').value.trim(),prompt:$('setupNewPrompt').value.trim()});if(r)$('setupCard').value=r.card_id;};
$('setupStarter').onclick=()=>send({action:'starter_world',place_name:$('setupPlaceName').value.trim()});
$('setupRooms').onclick=()=>send({action:'initialize_rooms',place_id:$('setupPlace').value});
$('setupLocate').onclick=()=>send({action:'initial_location',place_id:$('setupPlace').value});
for(const [kind,name,position] of furniture){const row=text('div','');row.className='setup-furniture-row';row.dataset.kind=kind;
  const label=text('label','');const check=document.createElement('input');check.type='checkbox';check.checked=kind!=='fixture';check.dataset.setupWrite='';label.append(check,text('span',name));
  const input=document.createElement('input');input.type='text';input.value=name;input.maxLength=40;input.setAttribute('aria-label',name+'名称');input.dataset.setupWrite='';
  const select=document.createElement('select');select.setAttribute('aria-label',name+tr('位置'));select.dataset.setupWrite='';for(const [id,value] of Object.entries(positions)){if(kind==='lamp'?!['desk_left','desk_right','bookshelf','bedside','entry_rack'].includes(id):!['left_wall','right_wall','back_wall','center','near_window','bedside'].includes(id))continue;const o=text('option',value);o.value=id;select.append(o);}select.value=position;row.append(label,input,select);$('setupFurniture').append(row);}
$('setupFurnish').onclick=()=>{const rows=[...$('setupFurniture').children].filter(r=>r.querySelector('input[type=checkbox]').checked).map(r=>({kind:r.dataset.kind,name:r.querySelector('input[type=text]').value.trim(),position:r.querySelector('select').value,movable:!['window','fixture'].includes(r.dataset.kind)}));send({action:'register_furniture',scene_revision:data.world.scene_revision,room_id:$('setupRoom').value,furniture:rows,lighting:rows.some(r=>r.kind==='lamp')?'warm':null,curtains:rows.some(r=>r.kind==='window')?'open':null});};
$('setupBrowser').onclick=()=>send({action:'install_browser'});$('setupDownloadTextures').onclick=()=>send({action:'download_textures'});$('setupSelectTexture').onclick=()=>send({action:'select_texture',texture:$('setupTexture').value});
$('setupTexture').onchange=()=>{textureDirty=true;};
$('setupEnable').onclick=()=>send({action:'activate',enabled:true,config_revision:data.config_revision});$('setupDisable').onclick=()=>send({action:'activate',enabled:false,config_revision:data.config_revision});
document.addEventListener('world-view',event=>{if(event.detail==='setup')load().then(()=>{if(!$('setupNewPrompt').value)showPreset();});else clearTimeout(poll);});
window.addEventListener('series-languagechange',()=>{if(data&&!busy&&!node.classList.contains('wb-hidden'))drawChecks();});
