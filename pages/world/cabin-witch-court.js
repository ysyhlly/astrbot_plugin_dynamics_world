// A small tribunal residence. The pointed vault, rose light and clock court are open cutaways.
export const courtColors = {
  ink:0x302636,bark:0x4b3749,walnut:0x645064,oak:0x88737e,honey:0xb59c8c,
  chalk:0xf4dfc0,plaster:0xc8b9bd,clay:0x713851,rose:0xa65b78,
  pine:0x443449,teal:0x694760,sage:0x9f7c9a,pale:0xd4b7b6,
  slate:0x343449,sea:0x51506c,mint:0x777392,brass:0xd6aa70,
  mortar:0x655a68,stone:0x978993,lightStone:0xc6b6b3,brick:0x926477,
};
const P=courtColors;
function lancet(k,root,x,y,z,w,h){
  const {block:b,beam}=k;
  b(root,w,h*.70,.08,x,y+h*.35,z,P.ink);
  for(let i=0;i<5;i++)b(root,w*(1-i*.17),h*.065,.082,x,y+h*(.72+i*.06),z,P.teal);
  for(const side of [-1,1]){
    b(root,.075,h*.69,.10,x+side*w*.52,y+h*.35,z+.03,P.oak);
    beam(root,[x+side*w*.52,y+h*.69,z+.03],[x,y+h*1.02,z+.03],.083,.09,P.honey);
  }
  for(let r=0;r<5;r++)for(let c=0;c<3;c++){
    b(root,w*.27,h*.118,.027,x+(c-1)*w*.295,y+h*(.10+r*.125),z+.061,
      [0x9b7495,0xb9a9bc,0x845773,0xc39ba5][(r+c*2)%4]);
  }
}
function dial(k,parent,x,y,z,size){
  const {block:b,beam}=k;
  for(const [w,h,c,depth] of [[.98,.55,P.ink,0],[.75,.82,P.ink,0],[.52,.98,P.ink,0],[.83,.43,P.brass,.052],[.63,.68,P.brass,.052],[.43,.82,P.brass,.052],
    [.70,.33,0xe9d4b4,.092],[.50,.59,0xe9d4b4,.092],[.34,.68,0xe9d4b4,.092]])b(parent,w*size,h*size,.10,x,y,z+depth,c);
  for(let i=0;i<12;i++){
    const a=i*Math.PI/6;b(parent,.045*size,.061*size,.025,x+Math.sin(a)*.30*size,y+Math.cos(a)*.30*size,z+.159,P.walnut);
  }
  beam(parent,[x,y,z+.169],[x-.17*size,y+.16*size,z+.169],.045*size,.024,P.ink);
  beam(parent,[x,y,z+.175],[x+.19*size,y+.095*size,z+.175],.033*size,.027,P.clay);
}
export function buildWitchCourt(k,anchors){
  const {block:b,beam,art,glow,snow}=k, scene=k.space('tribunal'), window=k.space('lancet sash',anchors.window);
  b(scene,10.22,3.49,.24,0,1.84,-3.72,P.stone);b(scene,.24,3.49,7.48,-5,1.84,0,0xaa9ba4);
  // Bonded stone above a dark dado; a few warmer stones catch the window light.
  for(let row=0;row<8;row++){
    const y=.35+row*.41;
    for(let col=0;col<11;col++){
      const lo=Math.max(-4.98,-5.46+col*.97+(row%2)*.46),hi=Math.min(4.98,-4.52+col*.97+(row%2)*.46);
      if(hi>lo)b(scene,hi-lo,.38,.055,(lo+hi)/2,y,-3.573,row<2?P.walnut:[0xb7aab2,0xcbbbba,0xb9afb7][(col+row*2)%3]);
    }
  }
  for(const y of [.24,1.00,3.48]){b(scene,10.20,.11,.20,0,y,-3.54,P.walnut);b(scene,.20,.11,7.38,-4.82,y,0,P.walnut);}
  // Pilasters and ogee ribs give the room a different silhouette from the timber gable.
  for(const x of [-4.92,-1.75,1.37,4.93]){
    b(scene,.25,3.70,.32,x,1.97,-3.51,P.walnut);
    for(const [y,w,h,c] of [[.27,.42,.23,P.slate],[1.07,.33,.12,P.brass],[3.45,.43,.17,P.honey],[3.67,.48,.12,P.stone]])b(scene,w,h,.38,x,y,-3.50,c);
  }
  for(const z of [-3.5,-.2,3.57]){
    b(scene,.29,3.66,.27,-4.86,1.94,z,P.walnut);
    b(scene,.40,.18,.43,-4.85,3.53,z,P.honey);b(scene,.39,.19,.39,-4.85,.3,z,P.slate);
  }
  for(const [cx,w,peak] of [[-3.34,3.36,4.43],[-.26,3.34,5.42],[3.20,3.56,4.64]]){
    for(let i=0;i<11;i++){
      const dx=(i-5)*w/11, lift=(1-Math.abs(i-5)/6)*(peak-3.63);
      b(scene,w/11+.012,lift,.33,cx+dx,3.60+lift/2,-3.72,P.plaster);
      b(scene,w/11+.054,.13,.76,cx+dx,3.63+lift,-3.79,i%2?P.sea:P.slate);
      b(scene,w/11+.025,.042,.092,cx+dx,3.60+lift,-3.36,P.brass);
    }
  }
  for(let i=0;i<14;i++)b(scene,.61,.13,.53,-4.98,3.72,-3.53+i*.51,i%3?P.sea:P.mint);
  const center=-.30,cy=4.30;
  // A twelve-light rose window with leaded glass and a garnet centre.
  for(const [w,h,d,col] of [[1.48,.66,.09,P.ink],[1.13,1.02,.09,P.ink],[.70,1.29,.09,P.ink],
    [1.32,.51,.15,P.brass],[.99,.87,.15,P.brass],[.54,1.13,.15,P.brass],[1.15,.40,.22,P.pine],[.78,.75,.22,P.pine],[.44,.91,.22,P.pine]]){
    b(scene,w,h,.074,center,cy,-3.55+d,col);
  }
  for(let i=0;i<12;i++){
    const a=i*Math.PI/6, x=center+.45*Math.cos(a), y=cy+.385*Math.sin(a);
    glow(scene,.16,.137,.035,x,y,-3.25,[0xbb7398,0x90a4c9,0xe2b678][i%3]);
  }
  glow(scene,.24,.19,.04,center,cy,-3.245,0xce6e97);b(scene,.091,.32,.047,center,cy,-3.214,P.brass);
  for(const sx of [-1.08,1.08])b(window,.12,1.83,.27,sx,0,.1,P.slate);
  b(window,2.43,.13,.49,0,-.905,.18,P.honey);
  for(const side of [-1,1])beam(window,[side*1.11,.83,.17],[0,1.28,.17],.095,.12,P.walnut);
  b(window,2.58,.074,.08,0,1.03,.35,P.brass);
  const portrait=k.space('magical-girl window',scene,[-4.83,2.31,-.16,Math.PI/2]);
  lancet(k,portrait,0,-.94,0,1.57,2.03);
  art(portrait,'portrait',1.26,1.33,0,-.057,.11);
  for(const z of [-2.62,1.63]){
    const pane=k.space('cloister lancet',scene,[-4.82,1.42,z,Math.PI/2]);lancet(k,pane,0,0,0,.73,1.72);
  }
  // Sealed bundles, an inkwell and a suspended reading lens on the testimony desk.
  const desk=k.space('testimony bundles',anchors.desk);
  for(const [i,c] of [P.clay,P.honey,P.teal].entries())b(desk,.49,.053,.31,-1.13,1.47+i*.057,.20,c);
  b(desk,.09,.018,.10,-1.13,1.626,.22,0xab4f71);
  b(desk,.12,.12,.12,-.83,1.50,.02,P.ink);beam(desk,[-.82,1.55,.02],[-.69,1.84,.055],.028,.027,P.brass);

  // Polished slate squares and a brass procession line run below the existing
  // mattress, seats and rug contact heights.
  for(let z=0;z<9;z++)for(let x=0;x<12;x++){
    b(scene,.785,.010,.775,-4.40+x*.80,.135,-3.18+z*.79,(x+z)%2?0xb9aab1:0x958697);
  }
  for(const x of [-4.81,4.81])b(scene,.043,.012,7.17,x,.138,0,P.brass);
  // The courthouse stands on two plinths and a slate processional court.
  b(scene,18.11,.26,14.92,0,-.67,1.47,P.slate);b(scene,17.94,.18,14.68,0,-.463,1.47,P.walnut);
  b(scene,17.83,.11,14.58,0,-.31,1.47,0xa198a2);
  for(let z=0;z<12;z++)for(let x=0;x<15;x++){
    const xx=-8.21+x*1.16+(z%2)*.25, zz=-5.24+z*1.17;
    if(Math.abs(xx)<5.05&&zz<3.90&&zz>-3.92)continue;
    if(Math.abs(xx)>8.46||zz>8.37)continue;
    b(scene,1.11,.027,1.11,xx,-.238,zz,[0xa499a1,0xb1a4aa,0x9e98a5,0xafa4ab][(x+z*3)%4]);
  }
  // Iron perimeter and low viewing bays beside the pond and vegetable beds.
  for(const side of [-1,1]){
    for(let i=0;i<12;i++){
      const x=side*(1.62+i*.59),low=i>=2&&i<=6,h=low?.42:.83;
      b(scene,.079,h,.08,x,-.24+h/2,7.31,P.ink);b(scene,.15,.07,.12,x,-.19+h,7.31,P.brass);
      if(i<11)b(scene,.59,.044,.062,x+side*.295,low?.04:.31,7.31,P.walnut);
    }
    for(let i=0;i<15;i++){
      const z=-4.90+i*.82;b(scene,.10,.76,.10,side*8.22,.13,z,P.ink);
      if(i<14)b(scene,.075,.057,.84,side*8.22,.37,z+.41,P.walnut);
    }
  }
  // Formal pointed gateway, high enough for the visitor walk and its existing lantern.
  for(const x of [-1.53,1.53]){
    b(scene,.28,2.74,.46,x,1.08,6.93,P.walnut);b(scene,.44,.27,.60,x,-.105,6.93,P.stone);
    b(scene,.40,.15,.54,x,2.42,6.93,P.honey);
    beam(scene,[x,2.48,6.93],[0,3.24,6.93],.20,.32,P.slate);
    beam(scene,[x,2.39,7.13],[0,3.14,7.13],.07,.08,P.brass);
  }
  b(scene,.25,.22,.38,0,3.25,6.93,P.brass);snow(scene,.28,.05,.40,0,3.40,6.93);
  // Rear clocktower, with stepped buttresses, four faces and a weather vane.
  const tower=k.space('witness clocktower',scene,[7.28,-.25,-3.70,0]);
  b(tower,1.78,.24,1.60,0,.12,0,P.slate);b(tower,1.30,2.30,1.11,0,1.39,0,P.stone);
  for(const x of [-.66,.66])for(const z of [-.53,.53]){
    b(tower,.23,2.66,.24,x,1.46,z,P.walnut);b(tower,.30,.19,.31,x,.46,z,P.honey);
  }
  const face=k.space('clock face',tower,[0,0,0,0]);dial(k,face,0,3.06,.65,1.08);
  const east=k.space('east clock',tower,[0,0,0,Math.PI/2]);dial(k,east,0,3.06,.71,1.00);
  b(tower,1.47,1.08,1.31,0,3.01,0,P.pine);b(tower,1.65,.15,1.46,0,3.60,0,P.honey);
  for(let i=0;i<7;i++){const w=1.73-i*.21;b(tower,w,.155,w*.92,0,3.75+i*.15,0,i%2?P.sea:P.slate);}
  b(tower,.065,.41,.065,0,4.88,0,P.brass);b(tower,.42,.073,.065,.08,5.02,0,P.brass);
  lancet(k,tower,0,.46,.582,.68,1.63);
  const banner=k.space('clocktower ribbon',tower,[.69,1.47,0,Math.PI/2]);
  b(banner,.55,.96,.035,0,0,0,P.clay);b(banner,.62,.065,.08,0,.51,.02,P.brass);
  for(let i=0;i<3;i++)b(banner,.46-i*.13,.085,.036,0,-.52-i*.074,.003,P.rose);
  b(banner,.26,.053,.028,0,.04,.043,P.brass);b(banner,.052,.34,.028,0,.04,.043,P.brass);
  snow(tower,1.62,.039,1.45,0,3.70,0);
  // Open cloister along the outer rose border: narrow piers frame the garden
  // while the sightline into the lower planting beds stays open.
  for(let i=0;i<4;i++){
    const z=-1.60+i*1.47;
    b(scene,.22,.18,.26,8.12,-.13,z,P.honey);b(scene,.16,1.02,.18,8.12,.47,z,P.walnut);
    b(scene,.24,.10,.27,8.12,1.02,z,P.honey);
    if(i<3){
      beam(scene,[8.12,1.09,z],[8.12,1.53,z+.735],.105,.11,P.slate);
      beam(scene,[8.12,1.53,z+.735],[8.12,1.09,z+1.47],.105,.11,P.slate);
    }
    for(const [dx,dy,dz] of [[-.13,.27,.09],[-.18,.43,.19],[-.10,.63,.20]]){
      b(scene,.17,.13,.15,8.12+dx,dy,z+dz,0x737b68);
      b(scene,.108,.11,.104,8.12+dx-.061,dy+.10,z+dz,P.rose);
    }
  }
  const shrine=k.space('evidence balance',scene,[-6.80,-.26,-3.72,.12]);
  b(shrine,1.73,.23,.97,0,.11,0,P.slate);
  for(const x of [-.55,.55])b(shrine,.17,.66,.20,x,.54,0,P.walnut);
  b(shrine,1.59,.11,.86,0,.92,0,P.honey);
  // A separate witness table faces the front aisle; the gardener retains her bench.
  const lectern=k.space('evidence lectern',scene,[5.84,-.255,5.48,0]);
  b(lectern,1.03,.12,.66,0,.062,0,P.slate);b(lectern,.63,.69,.44,0,.45,0,P.pine);
  b(lectern,.48,.44,.036,0,.45,.237,P.clay);b(lectern,1.14,.11,.72,0,.842,0,P.honey);
  b(lectern,.17,.052,.034,0,.46,.262,P.brass);b(lectern,.048,.18,.034,0,.46,.262,P.brass);
  const scale=k.space('court scales',lectern,[0,.902,0,0]);
  b(scale,.49,.065,.31,0,.04,0,P.slate);b(scale,.065,.70,.067,0,.40,0,P.brass);
  b(scale,.87,.062,.063,0,.71,0,P.brass);
  for(const x of [-.31,.31]){
    for(const sign of [-1,1])beam(scale,[x,.67,0],[x+sign*.12,.42,0],.022,.021,P.honey);
    b(scale,.29,.043,.22,x,.39,0,P.brass);
  }
  for(const z of [-4.24,-3.32]) b(shrine,.15,.48,.13,0,1.21,z+3.72,P.clay);
  for(const x of [-.42,.42]){b(shrine,.09,.29,.09,x,1.11,.04,P.chalk);glow(shrine,.052,.13,.054,x,1.31,.04,0xffb770);}
}
