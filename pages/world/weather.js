import {tr} from './series-ui.js';
import {apiPost} from "./api.js";
const $=id=>document.getElementById(id);
let revision=null,reference=null,loadedKey="",snapshot=null;
let credentialRevision=null,credentialKey="";
export function resetWeather(){credentialRevision=null;credentialKey="";$("qweatherPrivateKey").value="";$("weatherProviderInfo").textContent="";$("weatherAttribution").textContent="";$("weatherLicense").textContent="";revision=null;reference=null;loadedKey="";snapshot=null;$("weatherEffect").className="";$("weatherNow").textContent=tr("等待天气");$("weatherSource").textContent=tr("世界环境");$("weatherDetails").textContent="";$("weatherSun").textContent="";$("weatherForecast").replaceChildren();$("weatherStatus").textContent="";}
function node(tag,value){const n=document.createElement(tag);n.textContent=value;return n;}
export function city(){
  if(!$("realName").value.trim()||!$("realLatitude").value.trim()||!$("realLongitude").value.trim())throw new Error(tr("请搜索城市或填写地点名称和经纬度"));
  return {name:$("realName").value.trim(),latitude:Number($("realLatitude").value),longitude:Number($("realLongitude").value)};
}
function referenceLabel(){ $("weatherReference").textContent=reference?tr("天气参考：{0} ({1}, {2})", reference.name, reference.latitude, reference.longitude):tr("未设置参考城市：现实地图跟随角色地点，虚拟地图使用模拟天气。"); }
export function renderWeather(env,scope){
  snapshot=env;
  if(!env)return;
  const names={met:"MET Norway",open_meteo:"Open-Meteo",qweather:tr("和风天气")};
  const c=env.current,ready=env.available&&!env.stale;
  const stamp=value=>value?new Intl.DateTimeFormat("zh-CN",{timeZone:env.timezone||"UTC",hour:"2-digit",minute:"2-digit"}).format(new Date(value*1000)):"—";
  $("weatherSource").textContent=`${env.source||tr("世界环境")}${env.location?" · "+env.location:""}`;
  $("weatherNow").textContent=c?`${c.label} · ${c.temperature}°C · ${c.is_day?tr("白天"):tr("夜间")}${env.stale?tr("（已过期）"):""}`:"—";
  $("weatherDetails").textContent=c?tr("体感 {0}°C · 降水 {1} mm · 风速 {2} km/h", c.apparent_temperature??"—", c.precipitation??"—", c.wind_speed??"—"):"";
  $("weatherSun").textContent=c?tr("{0} · 日出 {1} / 日落 {2}{3}", env.timezone, stamp(env.sunrise), stamp(env.sunset), env.sun_times_estimated?tr("（模拟）"):env.sun_source?"（"+env.sun_source+"）":""):"";
  const messages={off:tr("天气已关闭"),no_map:tr("先生成或配置地图，再启用世界环境"),needs_location:tr("请设置现实地图或天气参考城市"),pending:tr("正在读取地点天气…"),unconfigured:tr("所选天气服务尚未配置凭据"),unavailable:tr("暂时无法获取天气，稍后自动重试"),stale:tr("数据已过期，仅供历史参考；不用于当前日常推演"),ready:env.mode==="simulated"?tr("世界模拟 · 根据世界种子、气候和时间生成"):env.provider==="qweather"?tr("和风天气数据"):tr("预报模型数据 · 非实时实测")};
  const failure=env.error&&env.status!=="ready";
  const retry=failure&&env.retry_at>Date.now()/1000?tr(" · 下次自动重试：{0}（本地时间）", new Date(env.retry_at*1000).toLocaleString("zh-CN",{hour12:false})):"";
  $("weatherStatus").textContent=(failure?`${env.status==="stale"?messages.stale+" · ":""}${env.error}`:messages[env.status]||"")+retry+(env.updated_at&&env.mode==="real"?tr(" · 更新 {0}", stamp(env.updated_at)):"");
  $("weatherProviderInfo").textContent=env.mode==="real"?`${env.fallback_active?tr("正在使用备用源"):tr("实际天气源")}：${names[env.provider]||tr("待获取")}${env.fallback_active?tr(" · 主源 {0} 尚不可用{1}", names[env.settings.provider], env.primary_error?"："+env.primary_error:""):""}${env.provider==="met"?tr(" · 温度与降水按预报时段更新，体感与降水概率缺失时显示 —"):""}`:"";
  const attribution=$("weatherAttribution");attribution.textContent=env.mode==="real"?tr("数据来源：{0} · 查看来源与署名", names[env.provider]||env.source):"";
  if(env.source_url)attribution.href=env.source_url;else attribution.removeAttribute("href");
  const license=$("weatherLicense");license.textContent=env.mode==="real"&&["met","open_meteo"].includes(env.provider)?"CC BY 4.0":"";license.href="https://creativecommons.org/licenses/by/4.0/";
  $("weatherForecast").replaceChildren(...(env.forecast||[]).filter((x,i)=>env.mode==="simulated"||i%3===0).slice(0,8).map(p=>{
    const item=node("div","");item.append(node("span",stamp(p.time)),node("strong",`${p.label} ${p.temperature}°`),node("small",tr("{0}% 降水概率", p.precipitation_probability??"—")));return item;
  }));
  $("weatherEffect").className=ready&&env.settings.effects?`dw-weather-effect ${c.effect} ${c.is_day?"day":"night"}`:"";
  const key=scope+":"+env.revision;
  if(loadedKey!==key){
    loadedKey=key;revision=env.revision;reference=env.settings.reference;
    $("weatherMode").value=env.settings.mode;$("weatherClimate").value=env.settings.climate;
    $("weatherTimezone").value=env.settings.timezone;$("weatherEffects").value=env.settings.effects?"on":"off";referenceLabel();
    $("weatherProvider").value=env.settings.provider;$("weatherFallback").value=env.settings.fallback;
  }
  const credentials=env.credentials||{};const ck=scope+":"+credentials.revision;
  if(credentialKey!==ck){credentialKey=ck;credentialRevision=credentials.revision;
    $("qweatherHost").value=credentials.host||"";$("qweatherDeveloper").value=credentials.developer_id||"";
    $("qweatherProject").value=credentials.project_id||"";$("qweatherKeyId").value=credentials.key_id||"";
    $("qweatherPrivateKey").value="";$("qweatherStatus").textContent=credentials.configured?tr("凭据已保存；实际连接结果在天气状态中显示"):tr("尚未配置，可先使用 MET / Open-Meteo");
  }
}
export function bindWeather(refresh,status){
  $("weatherUseCity").onclick=()=>{try{reference=city();$("weatherTimezone").value=$("realTimezone").value.trim();$("weatherMode").value="real";referenceLabel();}catch(e){status(e.message,true);}};
  $("weatherClearCity").onclick=()=>{reference=null;referenceLabel();};
  $("weatherSave").onclick=async()=>{
    const controls=["weatherSave","weatherMode","weatherProvider","weatherFallback","weatherClimate","weatherTimezone","weatherEffects","weatherUseCity","weatherClearCity"].map($);
    controls.forEach(n=>n.disabled=true);
    try{
      if(revision===null||!snapshot)throw new Error(tr("请先选择有效会话"));
      await apiPost("weather",{action:"configure",umo:$("dwScope").value.trim(),expected_revision:revision,settings:{mode:$("weatherMode").value,climate:$("weatherClimate").value,timezone:$("weatherTimezone").value.trim(),effects:$("weatherEffects").value==="on",reference,provider:$("weatherProvider").value,fallback:$("weatherFallback").value}});
      await refresh();
    }catch(e){status(e.message,true);}finally{controls.forEach(n=>n.disabled=false);}
  };
  async function saveCredentials(clear){
    const controls=["qweatherSave","qweatherClear","qweatherHost","qweatherDeveloper","qweatherProject","qweatherKeyId","qweatherPrivateKey"].map($);
    controls.forEach(n=>n.disabled=true);
    try{
      if(!snapshot||credentialRevision===null)throw new Error(tr("请先选择有效会话"));
      const credentials=clear?{clear:true}:{host:$("qweatherHost").value.trim(),developer_id:$("qweatherDeveloper").value.trim(),project_id:$("qweatherProject").value.trim(),key_id:$("qweatherKeyId").value.trim(),private_key:$("qweatherPrivateKey").value.trim()};
      await apiPost("weather",{action:"credentials",umo:$("dwScope").value.trim(),credentials_revision:credentialRevision,credentials});
      $("qweatherPrivateKey").value="";await refresh();
    }catch(e){status(e.message,true);}finally{controls.forEach(n=>n.disabled=false);}
  }
  $("qweatherSave").onclick=()=>saveCredentials(false);
  $("qweatherClear").onclick=()=>{if(confirm(tr("清除整个插件保存的和风天气凭据？")))saveCredentials(true);};
  $("realSearchButton").onclick=async()=>{
    $("realSearchButton").disabled=true;$("realSearchStatus").textContent=tr("正在搜索…");$("realResults").replaceChildren();
    const scope=$("dwScope").value.trim();
    try{
      const data=await apiPost("weather",{action:"search",umo:scope,query:$("realSearch").value.trim()});
      if(scope!==$("dwScope").value.trim())return;
      $("realSearchStatus").textContent=data.results.length?tr("选择结果填入坐标；保存后才会应用。"):tr("未找到城市，可改用手动坐标。");
      $("realResults").replaceChildren(...data.results.map(p=>{const b=node("button",p.name);b.className="wb-button";b.onclick=()=>{
        $("realName").value=p.name;$("realLatitude").value=p.latitude;$("realLongitude").value=p.longitude;$("realTimezone").value=p.timezone;
      };return b;}));
    }catch(e){$("realSearchStatus").textContent=e.message;}finally{$("realSearchButton").disabled=false;}
  };
}
