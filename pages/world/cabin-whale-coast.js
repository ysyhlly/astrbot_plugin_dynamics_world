// A whitewashed keeper's house with a foamy tidal shelf and a working pier.
export const coastColors = {
  ink:0x23365a,bark:0x35476d,walnut:0x47638b,oak:0x88a7b5,honey:0xc7b599,
  chalk:0xfff3da,plaster:0xe0ebe0,clay:0x376ab1,rose:0x6ca3ce,
  pine:0x264f82,teal:0x407cae,sage:0x72adbe,pale:0xb6d9d2,
  slate:0x233c67,sea:0x39659a,mint:0x668bb3,brass:0xe4ad68,
  mortar:0x646f82,stone:0x8997a2,lightStone:0xbfc8c5,brick:0xc88977,
};
const P=coastColors, blue=0x4379bf, white=0xf1ebd9, red=0xcd6f67;
export function buildWhaleCoast(k, anchors) {
  const {block:b,beam,art,glow,snow}=k, scene=k.space('coast'), window=k.space('porthole',anchors.window);
  // Horizontal lap siding, deep-blue skirting and a low saltbox roof.
  b(scene,10.2,3.44,.22,0,1.84,-3.72,P.plaster);b(scene,.22,3.44,7.46,-5,1.84,0,0xc1d4cc);
  for(let n=0;n<12;n++){
    const y=.32+n*.279;
    b(scene,9.96,.248,.07,0,y,-3.578,n<3?[P.pine,blue,P.teal][n]:n%3?0xdce7dc:0xe6eddd);
    b(scene,.075,.248,7.25,-4.855,y,0,n<3?[P.pine,blue,P.teal][n]:n%3?0xc4d9d3:0xd1ded5);
  }
  for(const [x,z] of [[-4.94,-3.62],[4.94,-3.62],[-4.94,3.61]]){
    b(scene,.30,3.53,.30,x,1.91,z,P.pine);b(scene,.39,.19,.40,x,.32,z,P.brass);
    b(scene,.42,.16,.42,x,3.54,z,white);
  }
  b(scene,10.55,.17,.40,0,3.64,-3.66,P.pine);b(scene,.37,.17,7.72,-4.99,3.64,0,P.pine);
  // Rounded pilot-house crown, brass-framed porthole and separately cut eaves.
  const ledges=[[9.92,.17],[8.55,.15],[6.92,.18],[5.15,.17],[3.42,.16]];
  let y=3.72;
  for(const [width,rise] of ledges){
    b(scene,width,rise,.32,0,y+rise/2,-3.72,white);
    b(scene,width+.37,.085,.77,0,y+rise,-3.79,P.sea);y+=rise;
  }
  for(let i=0;i<15;i++)b(scene,.37,.105,.50,-4.93,3.78,-3.53+i*.5,i%2?P.sea:P.mint);
  for(const side of [-1,1]){
    beam(scene,[side*4.84,3.07,-3.48],[side*4.32,3.57,-3.48],.13,.14,P.oak);
    b(scene,1.11,.14,.25,side*3.35,3.65,-3.43,P.brass);
  }
  const eyeX=.67;
  for(const [w,h,z,c] of [[1.27,.54,-3.50,P.pine],[.90,.87,-3.50,P.pine],[1.12,.39,-3.43,P.brass],
    [.72,.74,-3.43,P.brass],[.94,.27,-3.36,0x5398b9],[.54,.58,-3.36,0x7ab9c5]])b(scene,w,h,.10,eyeX,4.11,z,c);
  b(scene,.063,.53,.04,eyeX,4.12,-3.284,white);
  for(const x of [-1.08,1.08])b(window,.17,1.84,.24,x,0,.10,white);
  for(const y of [-.87,.87])b(window,2.36,.15,.26,0,y,.105,P.pine);
  b(window,2.62,.095,.53,0,-.92,.18,P.brass);
  b(window,2.60,.065,.08,0,1.035,.35,P.pine);
  for(const side of [-1,1]){
    b(window,.23,.14,.075,side*.16,.948,.32,P.pine);
    b(window,.12,.20,.075,side*.28,.948,.32,blue);
  }
  b(window,.13,.16,.08,0,.948,.36,P.brass);b(window,.076,.10,.05,0,.948,.405,blue);
  for(const x of [-.86,.86])beam(window,[x,-1.16,.02],[x,-.94,.30],.10,.095,P.oak);
  // Signal flags string along the back: free of the sash and bookshelf.
  for(const [i,x] of [1.97,2.35,2.73,3.11,3.49,3.87].entries()){
    b(scene,.41,.027,.03,x,3.22,-3.46,P.walnut);
    for(let j=0;j<3;j++)b(scene,.25-j*.067,.076,.035,x,3.15-j*.075,-3.45,[red,white,blue,P.brass][i%4]);
  }
  const portrait=k.space('keeper portrait',scene,[-4.84,2.27,.43,Math.PI/2]);
  b(portrait,1.35,2.25,.075,0,0,0,P.pine);
  art(portrait,'whaleOriginal',1.18125,2.10,0,0,.043);
  for(const yy of [-1.14,1.14])b(portrait,1.47,.078,.14,0,yy,.013,P.brass);
  // A rope float on the west bulkhead and a sextant on the chart table.
  const float=k.space('life ring',scene,[-4.80,2.05,2.41,Math.PI/2]);
  for(const [x,y,w,h,c] of [[0,.29,.42,.13,red],[0,-.29,.42,.13,red],[.29,0,.13,.42,red],[-.29,0,.13,.42,red],
    [-.20,.20,.16,.16,white],[.20,.20,.16,.16,white],[-.20,-.20,.16,.16,white],[.20,-.20,.16,.16,white]])b(float,w,h,.09,x,y,0,c);
  const desk=k.space('sextant',anchors.desk);
  b(desk,.40,.043,.30,-1.06,1.457,.20,P.pine);
  beam(desk,[-1.20,1.48,.18],[-1.04,1.79,.18],.030,.036,P.brass);
  beam(desk,[-1.04,1.79,.18],[-.87,1.50,.18],.030,.036,P.brass);
  b(desk,.28,.035,.045,-1.02,1.52,.18,P.brass);
  b(desk,.13,.073,.11,-1.08,1.72,.18,P.teal);
  // The wave shelves form one dry island, with successive blue depths beyond it.
  b(scene,19.70,.30,15.69,0,-.85,1.48,0x285a82);
  b(scene,19.60,.16,15.58,0,-.63,1.48,0x427f9b);
  b(scene,19.38,.07,15.41,0,-.51,1.48,0x448fa9);
  for(const [x,z,w,d,c] of [[0,8.86,18.86,.68,0x337f9f],[-6.06,7.98,5.92,.33,0x579fb1],
    [6.60,7.85,4.66,.44,0x65aab6],[9.02,1.0,.78,11.70,0x3986a2],[-9.06,-.44,.71,10.94,0x428eaa]])
    b(scene,w,.014,d,x,-.468,z,c);
  b(scene,16.74,.20,11.92,0,-.38,.36,0xb39b7e);
  b(scene,16.41,.080,11.83,0,-.297,.35,0xe2c991);
  b(scene,15.42,.16,1.37,-.15,-.357,6.85,0xdfc693);
  for(const side of [-1,1]){
    for(let i=0;i<9;i++){
      const z=-4.80+i*1.32,x=side*(8.09+(i%3)*.12);
      b(scene,.76,.12,.97,x,-.39,z,i%2?0xdac59a:0xceb590);
      b(scene,.25,.023,.76,x+side*.49,-.468,z,0xc5dfcc);
    }
    for(let i=0;i<16;i++){
      const x=side*(1.55+(i%8)*.94),z=7.58+Math.floor(i/8)*.67+Math.sin(i)*.16;
      b(scene,.34+(i%4)*.11,.018,.058,x,-.461,z,i%3?0xa7d9d6:0xe6efdf);
    }
  }
  // Wooden landing reaches the existing gate and mailbox.
  for(let i=0;i<11;i++)b(scene,2.05,.105,.186,.07,-.220,6.94+i*.202,i%3?0xb9946e:0xcba67b);
  for(const x of [-1.06,1.19])for(const z of [7.48,8.86]){
    b(scene,.15,.83,.15,x,-.02,z,P.walnut);b(scene,.19,.08,.19,x,.43,z,P.brass);
  }
  for(const side of [-1,1])for(let i=0;i<6;i++){
    const x=side*(1.55+i*1.22),z=7.27;
    b(scene,.15,.81,.15,x,.125,z,P.walnut);b(scene,.19,.08,.19,x,.55,z,white);
    if(i<5){beam(scene,[x,.35,z],[x+side*.61,.24,z],.045,.045,P.brass);beam(scene,[x+side*.61,.24,z],[x+side*1.22,.35,z],.045,.045,P.brass);}
  }
  // Pilot light tower. The viewing gallery and Fresnel lamp are separately readable.
  const tower=k.space('lighthouse',scene,[7.20,-.255,-3.70,0]);
  for(const [w,h,y,tint] of [[1.63,.23,.11,P.stone],[1.34,.67,.53,white],[1.16,.67,1.18,red],
    [1.06,.67,1.84,white],[.96,.60,2.47,red],[1.02,.20,2.86,white],[1.62,.13,3.02,P.pine]])b(tower,w,h,w,0,y,0,tint);
  for(const x of [-.65,.65])for(const z of [-.65,.65])b(tower,.06,.33,.06,x,3.24,z,P.pine);
  for(const z of [-.65,.65])b(tower,1.36,.052,.059,0,3.41,z,P.pine);
  for(const x of [-.65,.65])b(tower,.059,.052,1.36,x,3.41,0,P.pine);
  glow(tower,.66,.49,.66,0,3.40,0,0xffce77);
  for(const x of [-.37,.37])for(const z of [-.37,.37])b(tower,.075,.56,.075,x,3.41,z,P.pine);
  for(const [w,h,y,c] of [[1.15,.11,3.73,P.pine],[.87,.14,3.84,red],[.58,.16,3.99,red],[.31,.15,4.13,P.brass]])
    b(tower,w,h,w,0,y,0,c);
  snow(tower,.92,.035,.86,0,3.80,0);
  b(tower,.38,.50,.038,0,.45,.692,P.pine);b(tower,.21,.27,.035,0,2.0,.555,P.sea);
  // Moored whale skiff and its sail sit west of the bank, outside the walking lane.
  const boat=k.space('whale skiff',scene,[5.55,-.44,8.27,Math.PI/2+.08]);
  for(const [w,d,y,col] of [[.63,2.53,.05,P.pine],[.88,2.08,.16,blue],[.71,1.75,.27,white]])b(boat,w,.15,d,0,y,0,col);
  b(boat,.57,.05,1.41,0,.36,0,P.oak);b(boat,.085,1.71,.085,0,1.15,-.17,P.walnut);
  for(let i=0;i<8;i++){const width=.12+i*.085;b(boat,width,.15,.045,width/2,1.85-i*.15,-.17,i===5?blue:white);}
  b(boat,.12,.14,.11,0,2.04,-.17,red);
  for(const side of [-1,1])beam(boat,[0,.18,-1.06],[side*.42,.46,-1.34],.14,.18,blue);
  b(boat,.12,.081,.14,-.41,.21,.54,P.ink);
  // A pixel whale breaks the surface beyond the quay; the horizon remains open.
  const whale=k.space('offshore whale',scene,[-4.72,-.46,8.38,.19]);
  for(const [x,y,w,h,d,c] of [[-.41,.115,.96,.29,.65,0x427cc5],[.09,.16,.95,.37,.72,blue],
    [.56,.13,.58,.30,.65,blue],[.84,.095,.25,.20,.48,0x649ecf],[-.98,.09,.36,.16,.28,P.sea],
    [-1.17,.16,.27,.16,.20,blue]])b(whale,w,h,d,x,y,0,c);
  for(const side of [-1,1]){
    beam(whale,[-1.16,.18,0],[-1.39,.28,side*.33],.13,.21,blue);
    b(whale,.18,.09,.16,-1.44,.27,side*.35,P.mint);
    b(whale,.39,.055,.13,.54,.079,side*.31,white);b(whale,.079,.068,.038,.54,.185,side*.334,P.ink);
    b(whale,.31,.075,.21,-.17,.073,side*.40,P.sea);
  }
  for(const [x,y,w,h] of [[.08,.51,.071,.20],[.03,.64,.11,.071],[-.05,.69,.08,.059],[.16,.61,.09,.07],[.24,.65,.06,.05]])
    b(whale,w,h,.068,x,y,0,0xc6e4df);
  // A clear-span gate suspends the existing porch lamp between two masts.
  for(const x of [-1.54,1.54]){
    b(scene,.16,3.10,.17,x,1.25,6.91,P.walnut);b(scene,.22,.22,.23,x,.68,6.91,white);
    beam(scene,[x,2.15,6.91],[x*.56,2.75,6.91],.085,.09,P.brass);
  }
  b(scene,3.35,.14,.32,0,2.95,6.91,P.pine);b(scene,2.40,.09,.24,0,3.065,6.91,white);
  for(let i=0;i<7;i++)b(scene,.14,.16,.06,-1.14+i*.37,2.81,6.99,[red,white,blue][i%3]);
  snow(scene,2.40,.042,.26,0,3.13,6.91);
  const spy=k.space('harbour telescope',scene,[-2.32,-.25,5.42,-.78]);
  for(const [dx,dz] of [[-.20,.14],[.22,.14],[0,-.22]])beam(spy,[dx,.06,dz],[0,.74,0],.063,.065,P.walnut);
  b(spy,.15,.14,.17,0,.77,0,P.brass);
  beam(spy,[0,.79,-.25],[0,.94,.31],.145,.14,P.pine);
  b(spy,.195,.19,.077,0,.94,.31,P.brass);
}
