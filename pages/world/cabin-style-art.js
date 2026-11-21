// Pixel art drawn on integer texels. Each motif also works in the low-res camera.
const sea = {ink:'#203769',dark:'#244984',blue:'#3768c7',mid:'#53a5df',foam:'#bde9e9',white:'#fff3dc',gold:'#edb764',coral:'#e67570',skin:'#f5c7a5'};
const court = {ink:'#302238',dark:'#48344e',plum:'#684369',wine:'#9a4364',pink:'#d9819c',lilac:'#aba2cc',stone:'#928395',gold:'#d9af70',white:'#f6dfbd'};

function painter(w,h){
  const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
  const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;
  function rect(x,y,width,height,color){ctx.fillStyle=color;ctx.fillRect(x,y,width,height);}
  function polygon(points,color){
    const ys=points.map(p=>p[1]);
    for(let y=Math.min(...ys);y<Math.max(...ys);y++){
      const hits=[];
      for(let i=0;i<points.length;i++){
        const [x1,y1]=points[i],[x2,y2]=points[(i+1)%points.length];
        if((y1<=y+.5&&y2>y+.5)||(y2<=y+.5&&y1>y+.5))hits.push(x1+(y+.5-y1)*(x2-x1)/(y2-y1));
      }
      hits.sort((a,b)=>a-b);
      for(let i=0;i+1<hits.length;i+=2){const left=Math.ceil(hits[i]-.5);rect(left,y,Math.ceil(hits[i+1]-.5)-left,1,color);}
    }
  }
  function glyph(x,y,rows,colors,scale=1){
    rows.forEach((line,j)=>{for(let i=0;i<line.length;i++){const c=colors[line[i]];if(c)rect(x+i*scale,y+j*scale,scale,scale,c);}});
  }
  function star(x,y,r,color){rect(x-r,y,r*2+1,1,color);rect(x,y-r,1,r*2+1,color);if(r>2)rect(x-1,y-1,3,3,color);}
  function border(width,height,base,edge,inside){rect(0,0,width,height,base);rect(1,1,width-2,height-2,edge);rect(3,3,width-6,height-6,inside);}
  return {canvas,rect,polygon,glyph,star,border};
}
const whale=[
 '....b.b...........','.....b...bbb.......','........bddddb.....','......bbddddddb....',
 '.bb..bdddddeddbo...','bbdbbdddddddfffb...','..bddddddddffffb...','...bdddfffffffb....',
 '...bbfffffffbb.....','..bb..bbffbb.......','.......bbbd........','.........bd........',
];
const scales=[
 '.......g.......','......ggg......','..ggggggggggg..','..g....g....g..',
 '.g.g...g...g.g.','.g.g...g...g.g.','g...g..g..g...g','ggggg..g..ggggg',
 '.ppp...g...ppp.','.......g.......','......ggg......','....ggggggg....',
];
function wave(p,x,y,width,c,step=8){
  for(let i=0;i<width;i++){const k=i%step;p.rect(x+i,y+(k<2?0:k<4?1:k<6?2:1),1,1,c);}
}
function rose(p,x,y,scale=1){
  p.glyph(x,y,['..rrr...','.rsssr..','rsspssr.','rsppssr.','.rsssr..','..rrr.ll','...glll.','...gg...'],{r:court.wine,s:court.pink,p:court.white,g:'#5b6a66',l:'#748575'},scale);
}
function courtPortrait(p){
  const a=court;
  p.border(64,64,a.ink,a.gold,a.plum);
  p.polygon([[6,57],[6,22],[15,14],[31,5],[49,15],[58,23],[58,57]],a.lilac);
  p.polygon([[8,56],[8,24],[24,12],[32,8],[53,22],[56,25],[56,57]],a.dark);
  for(const [x,y] of [[14,22],[47,19],[50,31],[19,13],[9,37]])p.star(x,y,2,a.gold);
  p.polygon([[13,52],[18,28],[23,19],[36,15],[45,22],[46,41],[50,51],[44,55],[21,55]],a.ink);
  p.polygon([[18,48],[21,28],[29,21],[39,21],[43,28],[41,39],[46,50],[39,49],[25,47]],a.plum);
  p.polygon([[23,28],[29,23],[38,24],[41,29],[39,37],[34,40],[28,38],[24,34]],'#efc2aa');
  p.polygon([[20,28],[26,20],[37,19],[43,25],[40,31],[36,26],[32,31],[32,25],[26,29]],a.lilac);
  p.rect(26,31,4,2,a.wine);p.rect(35,31,4,2,a.wine);p.rect(27,31,1,1,a.white);p.rect(36,31,1,1,a.white);
  p.polygon([[16,58],[21,48],[27,41],[36,41],[43,48],[48,58]],a.wine);
  p.polygon([[24,44],[29,41],[32,45],[35,41],[40,45],[35,48],[32,49],[28,47]],a.white);
  p.star(32,49,2,a.gold);p.rect(22,55,21,2,a.gold);rose(p,17,22);rose(p,44,48);
}
function seaCloth(kind,p){
  const a=sea;
  if(kind==='cabinet'){
    p.border(24,36,a.ink,a.gold,a.blue);p.star(12,9,3,a.white);
    p.glyph(3,15,whale,{b:a.ink,d:a.foam,e:a.ink,f:a.white,o:a.coral});
    for(const y of [27,30])wave(p,4,y,16,a.mid);
  }else if(kind==='quilt'){
    p.border(64,48,a.ink,a.white,a.blue);
    for(const y of [5,10,32,37,41])wave(p,4,y,56,y%2?a.foam:a.mid);
    p.glyph(13,10,whale,{b:a.ink,d:'#77c7e7',e:a.ink,f:a.white,o:a.coral},2);
    for(const [x,y] of [[7,19],[53,15],[57,25]])p.star(x,y,2,a.gold);
  }else{
    p.border(64,48,a.ink,a.gold,a.dark);
    for(const x of [5,53])for(const y of [7,17,27,37])wave(p,x,y,6,a.foam);
    p.polygon([[32,5],[36,19],[51,24],[36,28],[32,43],[28,28],[13,24],[28,20]],a.foam);
    p.polygon([[32,8],[32,24],[29,20]],a.coral);p.polygon([[32,24],[47,24],[35,27]],a.gold);
    p.polygon([[32,24],[32,39],[35,28]],a.mid);p.polygon([[32,24],[17,24],[28,21]],a.blue);
    p.rect(30,22,5,5,a.white);
  }
}
function courtCloth(kind,p){
  const a=court;
  if(kind==='cabinet'){
    p.border(24,36,a.ink,a.gold,a.plum);
    p.polygon([[5,29],[5,12],[12,5],[19,12],[19,29]],a.wine);
    p.glyph(5,12,scales,{g:a.gold,p:a.white});rose(p,8,25);
  }else if(kind==='quilt'){
    p.border(64,48,a.ink,a.gold,a.wine);
    for(let y=5;y<43;y++)for(let x=5;x<59;x++){
      const d=Math.abs(x%16-8)+Math.abs(y%16-8);
      if(d===7)p.rect(x,y,1,1,a.pink);else if(d===1)p.rect(x,y,1,1,a.white);
    }
    p.polygon([[32,5],[47,24],[32,42],[17,24]],a.gold);
    p.polygon([[32,8],[44,24],[32,39],[20,24]],a.plum);
    p.glyph(25,17,scales,{g:a.white,p:a.pink});
  }else{
    p.border(64,48,a.ink,a.gold,a.dark);
    for(const [x,y] of [[5,5],[50,5],[5,34],[50,34]])rose(p,x,y);
    p.polygon([[32,5],[51,24],[32,43],[13,24]],a.wine);
    p.polygon([[32,8],[48,24],[32,40],[16,24]],a.plum);
    p.glyph(25,17,scales,{g:a.gold,p:a.white});
  }
}
function panorama(style,p){
  const seaView=style==='whale_coast';
  if(seaView){
    // Transparent upper pixels reveal the live sun, rainbank, stars or moon.
    p.rect(0,21,56,21,'#589baa');p.rect(0,25,56,17,'#4787a0');
    p.polygon([[0,24],[0,21],[6,20],[11,18],[17,21],[22,21],[22,24]],'#76969b');
    p.polygon([[0,36],[12,33],[20,35],[29,40],[32,42],[0,42]],'#ddbe92');
    for(const [x,y,w] of [[24,24,8],[40,27,12],[12,30,12],[31,33,8],[45,37,10]])p.rect(x,y,w,1,'#cce5d3');
    p.rect(34,13,1,12,'#4f5a66');p.polygon([[33,14],[33,23],[25,23]],'#fff1cb');
    p.polygon([[36,16],[41,22],[36,22]],'#d77f72');p.polygon([[26,24],[42,24],[39,27],[30,27]],'#425269');
    p.rect(7,16,3,5,'#eee4c5');p.rect(7,17,3,1,'#cc7265');p.rect(6,15,5,2,'#57687a');
  }else{
    p.rect(0,23,56,19,'#8d869d');p.rect(0,27,56,15,'#696784');
    for(const [x,y,w] of [[1,15,8],[15,19,5],[30,12,9],[49,17,6]]){
      p.rect(x,y,w,19,'#594d69');p.polygon([[x-1,y],[x+w/2|0,y-6],[x+w+1,y]],'#463f56');
      p.rect(x+2,y+3,2,3,'#e3b87e');
    }
    p.polygon([[0,37],[14,29],[22,31],[34,26],[55,34],[56,42],[0,42]],'#52556c');
    for(let x=0;x<56;x+=5){p.rect(x,32,2,10,'#3f3c51');p.rect(x,31,1,2,'#9b859b');}
    p.rect(0,36,56,1,'#74617b');
  }
}
export function styleCanvas(style,kind){
  const size={quilt:[64,48],rug:[64,48],cabinet:[24,36],portrait:[64,64],view:[56,42]}[kind];
  const p=painter(...size);
  if(kind==='portrait') courtPortrait(p);
  else if(kind==='view')panorama(style,p);
  else (style==='whale_coast'?seaCloth:courtCloth)(kind,p);
  return p.canvas;
}
