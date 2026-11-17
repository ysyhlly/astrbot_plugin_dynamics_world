/* Small vector illustrations. Object identity/state still comes from the world snapshot. */
const NS='http://www.w3.org/2000/svg';
export function shape(tag,attrs={}){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));return n;}
const rect=(x,y,width,height,fill,rx=5,extra={})=>shape('rect',{x,y,width,height,rx,fill,...extra});
const path=(d,stroke,extra={})=>shape('path',{d,fill:'none',stroke,'stroke-width':2,'stroke-linecap':'round','stroke-linejoin':'round',...extra});
export function roomFloor(svg){
  const defs=shape('defs');
  const gradient=shape('linearGradient',{id:'room-floor-gradient',x2:'100%',y2:'100%'});gradient.append(shape('stop',{offset:0,'stop-color':'var(--room-floor-a)'}),shape('stop',{offset:1,'stop-color':'var(--room-floor-b)'}));
  const pattern=shape('pattern',{id:'room-floor-boards',width:140,height:76,patternUnits:'userSpaceOnUse'});pattern.append(path('M0 0H140 M0 38H140 M0 76H140 M70 0V38 M0 38V76','var(--room-floor-line)',{'stroke-width':1,opacity:.45}));
  const shadow=shape('filter',{id:'room-soft-shadow',x:'-50%',y:'-50%',width:'200%',height:'220%'});shadow.append(shape('feDropShadow',{dx:0,dy:5,stdDeviation:5,'flood-color':'var(--room-shadow)','flood-opacity':.22}));
  const glow=shape('radialGradient',{id:'room-lamp-glow'});glow.append(shape('stop',{offset:0,'stop-color':'#efcf85','stop-opacity':.6}),shape('stop',{offset:1,'stop-color':'#efcf85','stop-opacity':0}));
  defs.append(gradient,pattern,shadow,glow);svg.append(defs);
  svg.append(rect(32,30,836,474,'var(--room-wall-shadow)',20),rect(38,24,824,472,'var(--room-wall)',18),rect(52,40,796,442,'url(#room-floor-gradient)',10));
  svg.append(rect(52,40,796,442,'url(#room-floor-boards)',10),path('M56 478V44H844','var(--room-wall-highlight)',{'stroke-width':3,opacity:.8}));
  const label=shape('text',{x:450,y:468,'text-anchor':'middle',class:'room-floor-wordmark'});label.textContent='LIVING SPACE';svg.append(label);
}
function caption(group,name,width,dy,dx=0){
  const max=12,label=name.length>max?name.slice(0,max-1)+'…':name,w=Math.max(50,Math.min(160,label.length*11+22));
  const tag=shape('g',{class:'room-object-caption',transform:`translate(${dx},${dy})`});tag.append(rect(-w/2,-12,w,24,'var(--room-caption)',12));
  const text=shape('text',{'text-anchor':'middle',y:4,class:'room-caption-text'});text.textContent=label;tag.append(text);group.append(tag);
}
export function furnitureArt(entry,design){
  const g=shape('g',{class:'room-illustration',filter:'url(#room-soft-shadow)'});let w=110,h=65,captionY=54,captionX=0;
  const wood='var(--room-wood)',edge='var(--room-wood-edge)',cloth='var(--room-cloth)',paper='var(--room-linen)';
  if(entry.kind==='bed'){
    w=145;h=180;captionY=114;
    g.append(rect(-w/2,-h/2,w,h,edge,11),rect(-68,-88,136,22,wood,7),rect(-63,-64,126,145,paper,8));
    g.append(rect(-50,-53,100,35,'var(--room-pillow)',12),path('M-42 -37Q0 -46 42 -37','var(--room-seam)',{opacity:.45}));
    g.append(rect(-64,-7,128,86,cloth,5),rect(-64,-8,128,17,'var(--room-cloth-fold)',4));
    g.append(path('M-48 18V65 M47 17V64 M-57 72Q0 82 57 72','var(--room-seam)',{opacity:.35}));
  }else if(entry.kind==='desk'){
    w=190;h=104;captionY=78;
    g.append(rect(-89,-43,178,100,edge,8),rect(-95,-52,190,100,wood,9));
    g.append(path('M-78 -31H75 M-80 27H70 M-82 1Q-28 -4 28 1T81 0','var(--room-grain)',{opacity:.35,'stroke-width':1}));
    g.append(rect(-76,38,62,10,'var(--room-wood-light)',3),rect(14,38,62,10,'var(--room-wood-light)',3));
  }else if(entry.kind==='chair'){
    w=60;h=68;captionY=56;
    g.append(rect(-30,-32,60,21,edge,10),rect(-25,-24,50,15,wood,7),rect(-28,-10,56,46,edge,11),rect(-22,-5,44,34,cloth,9));
    g.append(path('M-25 27L-29 39 M25 27L29 39',edge,{'stroke-width':6}));
    if(entry.position==='near_window')captionY=-49;
  }else if(entry.kind==='bookcase'){
    w=172;h=65;captionY=56;
    g.append(rect(-86,-32,172,65,edge,7),rect(-79,-26,158,52,wood,4));
    for(const x of [-53,0,53]){g.append(rect(x-22,-19,43,38,'var(--room-glass)',3,{opacity:.5}),path(`M${x-20} 0H${x+20}`,'var(--room-wood-light)',{opacity:.7}));}
    g.append(path('M-27 -24V24 M27 -24V24',edge));
  }else if(entry.kind==='lamp'){
    w=44;h=44;captionY=-47;
    g.append(shape('ellipse',{cx:0,cy:9,rx:19,ry:12,fill:edge}),path('M0 8V-13',wood,{'stroke-width':6}));
    g.append(path('M-20 -14Q0 -29 20 -14L13 0H-13Z','var(--room-lamp-edge)',{fill:['warm','bright','dim'].includes(design.lighting)?'var(--room-lamp-lit)':'var(--room-lamp-off)','stroke-width':1.5}));
    g.append(shape('circle',{cx:0,cy:-7,r:3,fill:['warm','bright','dim'].includes(design.lighting)?'#fff4c8':'#89958a'}));
  }else if(entry.kind==='window'){
    w=28;h=126;captionY=0;captionX=-72;
    g.append(rect(-14,-63,28,126,'var(--room-window-frame)',5),rect(-8,-56,16,112,'var(--room-glass)',2),path('M-8 -16H8 M-8 20H8','var(--room-window-frame)',{'stroke-width':4}));
    g.append(path('M-5 -51L5 -39 M-5 -5L5 7 M-5 30L5 42','var(--room-glass-glint)',{opacity:.7,'stroke-width':1}));
    if(design.curtains==='closed')g.append(rect(-20,-61,40,122,'var(--room-curtain)',5),path('M-11 -54V54 M0 -54V54 M11 -54V54','var(--room-curtain-fold)',{opacity:.65}));
    if(design.curtains==='half')g.append(rect(-20,-61,40,62,'var(--room-curtain)',5));
    if(design.curtains==='open')g.append(rect(-20,-68,40,18,'var(--room-curtain)',5),rect(-20,50,40,18,'var(--room-curtain)',5));
    if(entry.position==='left_wall')captionX=72;
    if(entry.position==='back_wall'){g.setAttribute('transform','rotate(90)');w=126;h=28;captionY=42;captionX=0;}
  }else{
    g.append(rect(-55,-32,110,64,edge,7),rect(-48,-25,96,50,wood,4),path('M-44 0H44',edge),rect(-6,-15,12,4,'var(--room-wood-light)',2));
  }
  const wrapper=shape('g');wrapper.append(g,rect(-w/2-7,-h/2-7,w+14,h+14,'transparent',10,{class:'room-hit'}));caption(wrapper,entry.name,w,captionY,captionX);
  return wrapper;
}
function coverColor(entry){
  const value=(entry.appearance||'').slice(0,40),match=value.match(/深紫灰|深蓝|藏蓝|银灰|银色|黄色|金黄|紫色|浅蓝|蓝色|黑色|绿色|红色|白色/);
  return ({深紫灰:'#766b7f',深蓝:'#536e89',藏蓝:'#536e89',银灰:'#9caeb3',银色:'#9caeb3',黄色:'#dec66d',金黄:'#dec66d',紫色:'#907b96',浅蓝:'#9ab7c8',蓝色:'#799eae',黑色:'#53625d',绿色:'#7c9d80',红色:'#b98178',白色:'#e7e7da'})[match?.[0]]|| (entry.kind==='book'?'#8b7994':'#738b91');
}
export function itemArt(entry){
  const wrapper=shape('g'),g=shape('g',{class:'room-illustration',filter:'url(#room-soft-shadow)'}),item=entry.item||{},color=coverColor(entry);
  if(entry.kind==='computer'){
    g.append(rect(-31,-22,62,36,'#667c80',4),rect(-26,-17,52,25,item.powered?'#accdc2':'#52696b',2),path('M-33 14H33L39 23H-39Z','#82989a',{fill:'#bac6c5','stroke-width':1}));
    g.append(rect(-8,16,16,4,'#8b9d9c',1),shape('circle',{cx:26,cy:8,r:2,fill:item.powered?'#bce6b9':'#8b9d9c'}));
  }else if(entry.kind==='water'){
    g.append(path('M10 -10Q27 -12 25 5Q23 17 10 15','#769da1',{'stroke-width':4}),rect(-12,-20,27,46,'#d0e2df',9,{opacity:.85}));
    if(Number.isFinite(item.servings)&&item.capacity>0){const height=32*Math.max(0,Math.min(1,item.servings/item.capacity));g.append(rect(-8,21-height,19,height,'#7aa9ab',4,{opacity:.78}));}
    g.append(rect(-14,-24,30,8,'#9baaa7',4),path('M-5 -13V15','#f3faf5',{'stroke-width':2,opacity:.8}));
  }else if(entry.kind==='umbrella'){
    g.append(path('M0 -25L10 18H-10Z',color,{fill:color,'stroke-width':2}),path('M0 18V25Q0 34 7 32','#7a7665',{'stroke-width':4}));
  }else if(item.open){
    g.append(path('M-30 -19Q-15 -23 0 -16Q15 -23 30 -19V23Q14 18 0 24Q-14 18 -30 23Z',color,{fill:'var(--room-paper)', 'stroke-width':2}));
    for(const y of [-8,0,8])g.append(path(`M-24 ${y}H-7 M7 ${y}H24`,'var(--room-page-line)',{'stroke-width':1}));g.append(path('M0 -15V23',color,{opacity:.5}));
  }else{
    g.append(rect(-19,-25,38,50,color,4),rect(-15,-21,30,42,'var(--room-paper)',2),rect(-17,-24,34,45,color,3),path('M-11 -20V17','#ffffff',{opacity:.2,'stroke-width':1}));
    if(/线圈|素描/.test(entry.appearance+' '+entry.name))for(const y of [-18,-9,0,9])g.append(shape('ellipse',{cx:-18,cy:y,rx:4,ry:2,fill:'none',stroke:'#c4cecb','stroke-width':1.5}));
    if(/绑带/.test(entry.appearance||''))g.append(path('M-17 3H17','#cbb599',{'stroke-width':3}));
    if(/红色五角星/.test(entry.appearance||''))g.append(shape('path',{d:'M0 -12L3 -4H11L5 1L7 9L0 4L-7 9L-5 1L-11 -4H-3Z',fill:'#bb6e5d'}));
  }
  wrapper.append(g,rect(-35,-32,70,65,'transparent',9,{class:'room-hit'}));
  const label=shape('g',{class:'room-item-caption',transform:'translate(0,46)'});label.append(rect(-60,-12,120,24,'var(--room-caption)',12));const t=shape('text',{'text-anchor':'middle',y:4,class:'room-caption-text'});t.textContent=entry.name;label.append(t);wrapper.append(label);return wrapper;
}
export function icon(kind){
  const svg=shape('svg',{viewBox:'0 0 24 24',width:22,height:22,fill:'none',stroke:'currentColor','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'});
  const drawings={book:'M5 3h13v18H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM6 3v14h12M9 7h6M9 10h4',room:'M3 11 12 3l9 8M5 10v11h14V10M9 21v-7h6v7',move:'M4 18 9 6l6 12 5-7M3 19h4M18 10h4',check:'M5 12l4 4L19 6',pause:'M8 5v14M16 5v14',clock:'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16ZM12 8v5l3 2',settings:'M4 7h16M4 17h16M8 4v6M16 14v6',warning:'M12 3 2 21h20L12 3ZM12 9v5M12 17v1'};
  svg.append(shape('path',{d:drawings[kind]||drawings.book}));return svg;
}
