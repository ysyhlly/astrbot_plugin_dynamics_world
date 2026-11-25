import {apiGet,apiPost,getSeriesTimezone,readyBridge} from './api.js';
import {msg,setText,tr} from './series-ui.js';
import {messages} from './series-messages.js';
import {CABIN_STYLES,cabinPlan} from './cabin-plans.js?v=homes.1';

const words={
  '小屋外观':['Cabin style','小屋の外観','Стиль домика'],
  '田园木屋':['Garden cottage','田園の木の家','Садовый домик'],
  'DeepSeek 鲸鱼娘海边小屋':['DeepSeek Whale Girl coast house','DeepSeek 鯨娘の海辺の家','Морской домик китовой девушки DeepSeek'],
  '魔女审判小屋':['Magical Girl Witch Trials house','魔法少女の魔女裁判の小屋','Домик суда над ведьмой'],
  '绘制潮汐图':['Chart the tides','潮汐図を描く','Составить карту приливов'],
  '海堤观鲸':['Watch for whales','防波堤で鯨を観察','Наблюдать за китами'],
  '核对证词':['Compare testimonies','証言を照合','Сверить показания'],
  '复核证物重量':['Weigh the exhibits','証拠品の重さを確認','Взвесить улики'],
  '主题日程：{0}':['Theme schedule: {0}','テーマの日程：{0}','Расписание: {0}'],
  '当前仅预览外观':['Previewing the appearance only','外観のみプレビュー中','Только предпросмотр'],
  '已保存外观，等待可用的日程空档':['Style saved; awaiting an available time slot','外観を保存。空き時間を待っています','Стиль сохранён, ожидается свободное время'],
  '外观保存失败，已重新读取':['Could not save. Reloaded the selection.','保存できず、選択を再読み込みしました','Не удалось сохранить. Выбор обновлён.'],
};
for(const [key,[en,ja,ru]] of Object.entries(words))messages[key]={zh:key,en,ja,ru};

export function createCabinStylePicker(getRenderer){
  const root=document.createElement('div');root.className='cabin-style-picker';
  const label=document.createElement('label');label.htmlFor='cabinStyleChoice';setText(label,msg('小屋外观'));
  const select=document.createElement('select');select.id=label.htmlFor;
  for(const {id,name} of CABIN_STYLES){const option=document.createElement('option');option.value=id;setText(option,msg(name));select.append(option);}
  const status=document.createElement('small');status.setAttribute('role','status');status.hidden=true;
  const credit=document.createElement('a');credit.className='cabin-art-credit';
  credit.href=new URL('./whale-art-credit.txt',import.meta.url).href;
  credit.textContent='© 上善无形 / ZipZipPipe · CC BY-NC-SA 4.0';credit.hidden=true;
  credit.target='_blank';credit.rel='noopener';
  root.append(label,select,status,credit);
  let target=null,scopeToken=0,style='cottage',revision=null,canWrite=false,loading=false,saving=false,replay=false,details=null;
  function paint(value){
    style=cabinPlan(value).id;select.value=style;
    credit.hidden=style!=='whale_coast';
    if(!replay)getRenderer()?.setCabinStyle(style);
  }
  function note(value){
    status.hidden=!value;
    if(value)setText(status,value);
  }
  function updateInfo(){
    if(style==='cottage'){note(null);return;}
    if(!details?.bound||!canWrite){note(msg('当前仅预览外观'));return;}
    const tz=String(details?.timezone||'').trim()||getSeriesTimezone();
    const plan=(details.upcoming||[]).map(a=>{
      const fmt={timeZone:tz,hour:'2-digit',minute:'2-digit'};
      const date=new Intl.DateTimeFormat('en-CA',{timeZone:fmt.timeZone});
      if(date.format(a.start*1000)!==date.format(Date.now()))Object.assign(fmt,{month:'2-digit',day:'2-digit'});
      const hm=new Intl.DateTimeFormat('en-GB',fmt).format(a.start*1000);
      return hm+' '+tr(a.activity);
    });
    note(plan.length?msg('主题日程：{0}',plan.join(' · ')):msg('已保存外观，等待可用的日程空档'));
  }
  function enable(){select.disabled=loading||saving||replay;}
  function accept(data){details=data;revision=data.revision;canWrite=data.can_write===true;paint(data.style);updateInfo();}
  async function bind(scope,force=false){
    scope=String(scope||'').trim();
    if(scope===target && (!force||loading||saving))return;
    const changed=scope!==target,ticket=++scopeToken;target=scope;
    if(changed){saving=false;details=null;revision=null;canWrite=false;paint('cottage');note(null);}
    loading=true;enable();
    try{await readyBridge();const data=await apiGet('cabin_style',{umo:scope});if(ticket===scopeToken)accept(data);}
    catch{if(ticket===scopeToken){canWrite=false;updateInfo();}}
    finally{if(ticket===scopeToken){loading=false;enable();}}
  }
  select.addEventListener('change',async()=>{
    if(loading||saving||replay){select.value=style;return;}
    const previous=style,ticket=scopeToken,scope=target,next=select.value;
    try{paint(next);}catch{paint(previous);return;}
    if(!canWrite||revision===null){updateInfo();return;}
    saving=true;enable();
    try{
      const result=await apiPost('cabin_style',{umo:scope,style:next,expected_revision:revision});
      if(ticket===scopeToken)accept(result);
    }catch{
      if(ticket===scopeToken){
        try{const fresh=await apiGet('cabin_style',{umo:scope});if(ticket===scopeToken)accept(fresh);}
        catch{if(ticket===scopeToken)paint(previous);}
        if(ticket===scopeToken)note(msg('外观保存失败，已重新读取'));
      }
    }finally{if(ticket===scopeToken){saving=false;enable();}}
  });
  window.addEventListener('series-languagechange',updateInfo);
  return {root,bind,attach(){getRenderer()?.setCabinStyle(style);},
    observe(scope,scene){if(scope===target&&!saving&&!loading&&revision!==null&&Number.isInteger(scene?.cabin_style_revision)&&scene.cabin_style_revision>revision)void bind(scope,true);},
    replay(frameStyle){
      replay=frameStyle!==null;enable();
      const shown=replay?cabinPlan(frameStyle).id:style;
      select.value=shown;credit.hidden=shown!=='whale_coast';getRenderer()?.setCabinStyle(shown);
    },
    get id(){return style;}};
}
