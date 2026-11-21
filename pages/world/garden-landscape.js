/* The gate walk branches to a water garden and a kitchen garden. Fixtures use
 * world coordinates; living plants keep their own growth and weather roots. */
const T = {
  bark:0x674749, walnut:0x8a5748, oak:0xae7955, honey:0xd29a66, cream:0xf2d6a2,
  slate:0x415e6b, teal:0x3c7272, copper:0xb96951, ochre:0xd39b55, iron:0x4c5359,
  brick:0xb47963, darkBrick:0x875a50, stone:0xa2978a, lightStone:0xc8bba2,
  moss:0x788b69, leaf:0x658a62, darkLeaf:0x406955, sunLeaf:0x94a673,
  water:0x599d9c, deep:0x337987, shallows:0x8fb8a5, glitter:0xbde0c7,
};

export function buildGardenLandscape({G, instances, row, group, beam, garden, white, colorMaterial, earth}) {
  const fixed=[], stones=[], soil=[];
  const put=(list,x,y,z,w,h,d,c,rotation)=>list.push(row(x,y,z,w,h,d,c,rotation));
  const cubes=(name,rows,parent=garden,shadow=true,material=white)=>instances(name,G.voxel,material,rows,parent,shadow);
  // Run-length rows put pigment on the upper face without a draw per texel.
  function mosaic(rows,pattern,inks,x,y,z,pitch,thickness) {
    pattern.forEach((line,r)=>{
      for(let col=0;col<line.length;){
        let end=col+1;
        while(end<line.length&&line[end]===line[col])end++;
        const tint=inks[line[col]];
        if(tint!==undefined){
          put(rows,x+((col+end)/2-line.length/2)*pitch,y,z+(r+.5-pattern.length/2)*pitch,
            (end-col)*pitch,thickness,pitch,tint);
        }
        col=end;
      }
    });
  }

  // The top faces of the paving stay below the actor's feet. Narrow branch
  // paths serve the benches, the washing line and the potting table.
  put(stones,.67,-.20,4.13,2.47,.20,.74,T.stone);
  put(stones,1.04,-.07,3.78,2.14,.17,.58,T.lightStone);
  const stoneShades=[0xbca990,0xcbbba0,0xaca89a,0xceba98,0xb8a68e];
  for (let r=0;r<9;r++) {
    const z=4.44+r*.49, shift=.58*Math.max(0,1-r/3);
    put(stones,shift,-.24,z,1.98,.06,.50,0x838775);
    const widths=r%2?[.37,.78,.78]:[.77,.78,.38];
    let left=shift-.965;
    widths.forEach((w,c)=>{
      const x=left+w/2; left+=w+.016;
      put(stones,x,-.207,z,w,.061,.45,stoneShades[(r*3+c)%5]);
      if ((r+c)%3===0) put(stones,x-w*.21,-.173,z-.10,w*.27,.008,.034,0xa2a28b);
    });
  }
  for (const sign of [-1,1]) {
    for (let i=0;i<10;i++) {
      const x=sign*(1.22+i*.56), z=5.56+Math.sin(i*.82)*.09;
      const besideBench=i===2||i===3;
      put(stones,x,-.221,besideBench?5.44:z,.46,.067,besideBench?.23:.35,stoneShades[(i+2)%5]);
    }
    put(stones,sign*1.29,-.215,6.84,.56,.066,.35,T.lightStone);
    put(stones,sign*1.84,-.215,6.75,.46,.066,.35,T.stone);
  }

  // A bonded brick footing, timber coping and dark soil make each border read
  // from above, without extending beyond the existing ecology/inspection bounds.
  for (const cx of [-6.48,6.48]) {
    put(soil,cx,-.145,.83,2.58,.22,6.4,0xffffff);
    for(const sign of [-1,1]){
      const x=cx+sign*1.29;
      put(fixed,x,-.08,.83,.17,.31,6.5,T.darkBrick);
      for(let i=0;i<12;i++)put(fixed,x,.013,-2.16+i*.54,.18,.12,.51,i%3?T.brick:0xc9906f);
      put(fixed,x,.112,.83,.21,.072,6.58,T.honey);
      for(const z of [-2.38,-.26,1.89,4.03]){
        put(fixed,x,.085,z,.235,.38,.21,T.walnut);
        put(fixed,x,.296,z,.27,.064,.25,T.honey);
      }
      const z=.83+sign*3.20;
      put(fixed,cx,-.06,z,2.62,.26,.16,T.brick);
      put(fixed,cx,.112,z,2.74,.072,.20,T.honey);
    }
    for(let r=0;r<6;r++)for(let c=0;c<4;c++){
      const x=cx-.92+c*.58,z=-1.82+r*.94;
      put(soil,x,-.03,z,.38,.042,.62,(c+r)%2?0xd5c3a3:0xe7d6bc);
    }
  }

  const flowerGrowthGroup=group(0,-.034,0);
  const flowerBlossomGroup=group(0,0,0,flowerGrowthGroup);
  const foliage=[],flowers=[];
  let flowerHeads=0;
  function leaf(list,x,y,z,sign,color,size=1) {
    put(list,x+sign*.07*size,y+.04*size,z,.16*size,.09*size,.14*size,color);
    put(list,x+sign*.16*size,y+.096*size,z,.11*size,.085*size,.105*size,color);
  }
  function flowerHead(x,y,z,kind,tone) {
    flowerHeads++;
    if(kind==='spire'){
      for(let i=0;i<4;i++){
        const sign=i%2?1:-1, w=.21-i*.029;
        put(flowers,x+sign*.050,y+i*.125,z,w,.135,w,tone[i%tone.length]);
        put(flowers,x+sign*.08,y+i*.125-.014,z+w*.50,w*.53,.052,.024,0xe6c4a4);
      }
    }else if(kind==='tulip'){
      put(flowers,x,y,z,.205,.17,.194,tone[0]);
      put(flowers,x-.084,y+.104,z,.091,.104,.158,tone[1]);
      put(flowers,x+.084,y+.107,z+.016,.084,.116,.142,tone[1]);
      put(flowers,x,y+.049,z+.095,.134,.108,.067,tone[2]);
    }else{
      for (const [dx,dz] of [[-.11,0],[.11,0],[0,-.11],[0,.11]]) {
        put(flowers,x+dx,y+.022,z+dz,.17,.061,.17,tone[0]);
        put(flowers,x+dx*1.53,y+.050,z+dz*1.53,.09,.044,.09,tone[1]);
      }
      put(flowers,x,y+.074,z,.12,.071,.12,tone[2]);
    }
  }
  for(const [bank,cx] of [-6.48,6.48].entries()){
    const towardsFence=bank?1:-1;
    for(let drift=0;drift<6;drift++)for(let layer=0;layer<3;layer++){
      const kind=layer===2?'spire':layer===1?'tulip':'daisy';
      const h=layer===2?.69:layer===1?.53:.35;
      const tone=kind==='spire'?(drift%2?[0x956397,0xb688bc,0xcb9cc4]:[0x677eb3,0x869bc8,0xb3acd5]):
        kind==='tulip'?(drift%3?[0xb75155,0xe47d69,0xf59c78]:[0xcd803d,0xf0ac57,0xf8c273]):
        drift%2?[0xf3ce79,0xffdfa2,0x985e42]:[0xe6d9b1,0xffedc7,0xbc8840];
      const heads=layer===2?2:3;
      for(let k=0;k<heads;k++){
        const x=cx+towardsFence*((layer-1)*.73+(k%2?-.125:.12))+.095*Math.sin(drift*2.3+layer+k);
        const z=-1.78+drift*.99+(k===2?.19:k===1?-.16:.0)+(layer%2)*.09+.073*Math.sin(drift*1.7+k);
        const height=h+.066*((k+drift)%3);
        put(foliage,x,height/2,z,.047,height,.047,T.darkLeaf);
        leaf(foliage,x,height*.29,z,-1,T.leaf,1.10);
        leaf(foliage,x,height*.51,z,1,(k+layer)%2?T.sunLeaf:T.leaf,1.15);
        put(foliage,x,.117,z+.105,.16,.105,.22,T.darkLeaf);
        flowerHead(x,height,z,kind,tone);
      }
    }
  }
  cubes('Herbaceous borders: stems and stepped leaves',foliage,flowerGrowthGroup,false);
  cubes('Daisy drifts, tulip cups and foxglove bells',flowers,flowerBlossomGroup,false);

  // Low irregular shore, shallow shelves and a recessed blue pool. Only the
  // exposed bank cells carry rocks, so water runs up to their edges.
  const pondX=-3.75,pondZ=6.35,cell=.245;
  const spans=[[-3,3],[-5,4],[-5,5],[-6,5],[-5,5],[-4,3]];
  const water=[],edge=new Set();
  const inPond=(x,z)=>z>=0&&z<spans.length&&x>=spans[z][0]&&x<=spans[z][1];
  for(let z=0;z<spans.length;z++) {
    const [lo,hi]=spans[z];
    let start=lo,previous;
    for(let x=lo;x<=hi+1;x++){
      let tint;
      if(x<=hi) {
        const nearEdge=!inPond(x-1,z)||!inPond(x+1,z)||!inPond(x,z-1)||!inPond(x,z+1);
        tint=nearEdge?T.shallows:(x>-3&&x<4&&z>=2&&z<=4?T.deep:T.water);
        for(const [dx,dz] of [[-1,0],[1,0],[0,-1],[0,1]]){
          if(!inPond(x+dx,z+dz))edge.add((x+dx)+','+(z+dz));
        }
      }
      if(previous!==undefined&&tint!==previous){
        put(water,pondX+(start+x-1)*cell/2,-.214,pondZ+(z-2.5)*cell,(x-start)*cell,.062,cell,previous);
        start=x;
      }
      previous=tint;
    }
  }
  let stoneIndex=0;
  for(const key of edge){
    const [a,b]=key.split(',').map(Number),x=pondX+a*cell,z=pondZ+(b-2.5)*cell;
    const height=.10+.025*(stoneIndex%4);
    put(stones,x,-.24+height/2,z,cell*.96,height,cell*.97,[T.stone,T.lightStone,0x94968a][stoneIndex%3]);
    if(stoneIndex++%4===0)put(stones,x-.014,-.24+height+.007,z+.02,.145,.017,.119,T.moss);
  }
  const waterMaterial=colorMaterial(0xffffff,{roughness:.45,metalness:.03,emissive:0x396969,emissiveIntensity:.12});
  cubes('Pond: shallows and blue channel',water,garden,false,waterMaterial);
  for(const [dx,dz,w] of [[-.85,.13,.22],[.53,-.05,.26],[.32,.38,.24],[-.16,-.39,.18],[-.48,.29,.12]]) {
    put(fixed,pondX+dx,-.177,pondZ+dz,w,.008,.036,T.glitter);
  }
  // A stone spring feeds the pond via a short stepped chute.
  const springX=pondX-1.45,springZ=pondZ-.26;
  for(const [x,y,w,h,d,c] of [[-.16,.03,.42,.56,.54,T.stone],[-.16,.37,.48,.12,.61,T.lightStone],
    [-.13,.48,.36,.11,.49,T.moss],[.09,.16,.32,.11,.30,T.walnut],[.25,.096,.18,.075,.23,T.oak]]) {
    put(stones,springX+x,y,springZ,w,h,d,c);
  }
  put(fixed,springX+.11,.224,springZ,.32,.023,.16,T.water);
  put(fixed,springX+.28,.157,springZ,.065,.13,.156,T.shallows);
  put(fixed,springX+.32,-.035,springZ,.060,.27,.130,T.glitter);
  for (const [dx,dz] of [[.30,.10],[.40,-.09],[.48,.02]]) put(fixed,springX+dx,-.166,springZ+dz,.102,.016,.045,T.glitter);

  const aquatic=[];
  for(const [x,z,width] of [[-.69,-.32,.37],[.48,.29,.30],[-.17,.41,.26]]){
    put(aquatic,pondX+x,-.163,pondZ+z,width,.035,width*.61,0x638763);
    put(aquatic,pondX+x-.01,-.161,pondZ+z,width*.66,.037,width,0x85a070);
  }
  for(const [dx,dz] of [[0,-.09],[0,.09],[-.09,0],[.09,0]]){
    put(aquatic,pondX-.69+dx,-.095,pondZ-.32+dz,.13,.069,.12,0xe7999e);
    put(aquatic,pondX-.69+dx*.54,-.050,pondZ-.32+dz*.54,.087,.055,.08,0xffc3a9);
  }
  put(aquatic,pondX-.69,-.016,pondZ-.32,.077,.045,.077,T.ochre);
  for(const [dx,dz] of [[-.91,-.65],[-1.24,.28],[.78,-.59]]){
    for(let i=0;i<4;i++){
      const x=pondX+dx+(i%2)*.11,z=pondZ+dz+Math.floor(i/2)*.095,h=.38+i*.08;
      put(aquatic,x,-.19+h/2,z,.037,h,.037,T.leaf);
      put(aquatic,x,-.17+h,z,.064,.15,.065,T.walnut);
      leaf(aquatic,x,.02,z,i%2?1:-1,T.sunLeaf,.77);
    }
  }
  // The cat's existing viewing spot sits on the dry side of this landing.
  for(let i=0;i<4;i++)put(fixed,-2.32,-.243,5.85+i*.15,.51,.056,.132,i%2?T.oak:T.honey);
  cubes('Pond reeds and stepped waterlilies',aquatic,garden,false);
  const koi=[];
  for(const [i,tint] of [0xdf8659,0xc76352].entries()){
    const fish=group(pondX+(i?.43:-.37),-.159,pondZ+(i?.19:-.12));
    const scales=[];
    const pattern=[
      '....s.....s.....','ss..sw...ws.....','.ss.swowwowwwe..',
      '..swwoowwoooowwe','..swwoowwwowowwe','.ss.swowwwwowe..',
      'ss..sw...ws.....','....s.....s.....',
    ];
    mosaic(scales,pattern,{s:0xb98268,w:0xf8dbaa,o:tint,e:0x634849},0,.014,0,.035,.022);
    cubes('Pixel koi',scales,fish,false);
    koi.push(fish);
  }
  const moonShimmer=cubes('Moon stripe on water',[row(pondX+.1,-.173,pondZ,.49,.009,.045)],garden,false,
    colorMaterial(0xbcd4d3,{emissive:0xd5e2d3,emissiveIntensity:.72}));
  moonShimmer.visible=false;

  // Rear tomato frame, middle root vegetables, low leafy greens at the front.
  const vegX=3.50,vegZ=6.35,vegGrowthGroup=group(vegX,-.07,vegZ);
  const vegFruitGroup=group(0,0,0,vegGrowthGroup);
  const greens=[],produce=[];
  put(soil,vegX,-.16,vegZ,2.38,.165,1.56,0xffffff);
  for (const side of [-1,1]) {
    put(fixed,vegX+side*1.18,-.064,vegZ,.105,.21,1.66,T.walnut);
    put(fixed,vegX,-.064,vegZ+side*.78,2.46,.21,.105,T.oak);
  }
  for (const z of [-.48,0,.48]) put(soil,vegX,-.072,vegZ+z,2.15,.105,.29,0xe3c9a2);
  for(const x of [-.90,.90]){
    for(const z of [-.69,-.20])fixed.push(beam([vegX+x,-.04,vegZ+z],[vegX+x,.94,vegZ-.47],.066,.073,T.honey));
  }
  for(const y of [.28,.56,.92])put(fixed,vegX,y,vegZ-.47,1.90,.053,.073,y>.9?T.walnut:T.oak);
  for(let i=0;i<4;i++){
    const x=-.76+i*.49;
    put(greens,x,.38,-.48,.043,.76,.043,T.darkLeaf);
    for(let j=0;j<3;j++)leaf(greens,x,.16+j*.18,-.48,j%2?1:-1,T.leaf,.82);
    for(const [dx,dy] of [[-.07,.42],[.08,.57],[-.02,.27]]){
      const tint=(i+Math.round(dy*10))%3?0xc95841:0xe08b42;
      put(produce,x+dx,dy,-.391,.145,.089,.143,tint);
      put(produce,x+dx,dy+.006,-.391,.106,.146,.111,tint);
      put(produce,x+dx-.036,dy+.026,-.317,.037,.026,.014,0xe89d62);
      put(produce,x+dx,dy+.091,-.391,.091,.033,.088,T.darkLeaf);
    }
    put(produce,x,.077,.035,.155,.12,.145,i%2?0xb85162:0xe4924e);
    for(const sign of [-1,1]){
      leaf(greens,x,.12,.035,sign,i%2?T.leaf:T.sunLeaf,.72);
      put(greens,x+sign*.060,.229,.042,.029,.128,.032,T.darkLeaf);
      put(greens,x+sign*.084,.281,.042,.065,.045,.048,T.sunLeaf);
    }
    put(greens,x,.111,.46,.213,.13,.20,T.leaf);
    const rosette=['..aa...','.abbba.','abclbba','ablccla','abblcba','.abllaa','..aaa..'];
    mosaic(greens,rosette,{a:T.darkLeaf,b:T.leaf,c:0x91a975,l:0xc1bf88},x,.188,.46,.042,.032);
    put(greens,x-.026,.218,.46,.067,.034,.073,0xa7b483);
    for(const sign of [-1,1]) {
      put(greens,x+sign*.115,.085,.46,.14,.10,.21,T.leaf);
      put(greens,x,.07,.46+sign*.11,.22,.09,.12,T.darkLeaf);
    }
  }
  for(const [dx,dz,ink] of [[1.00,-.31,T.copper],[1.00,.48,T.leaf]]){
    put(fixed,vegX+dx,.13,vegZ+dz,.037,.36,.044,T.walnut);
    put(fixed,vegX+dx,.293,vegZ+dz,.19,.107,.035,T.cream);
    put(fixed,vegX+dx,.292,vegZ+dz+.024,.075,.043,.018,ink);
  }
  cubes('Tomato vines, carrot tops and lettuces',greens,vegGrowthGroup,false);
  cubes('Tomato clusters and coloured roots',produce,vegFruitGroup,false);

  // Potting bench and water butt are on the east service strip, off the walk.
  const bx=7.15,bz=5.43;
  for(const x of [-.27,.27])for(const z of [-.68,.68])put(fixed,bx+x,.10,bz+z,.105,.72,.105,T.walnut);
  put(fixed,bx,.46,bz,.74,.10,1.61,T.honey);
  put(fixed,bx,.0,bz,.59,.068,1.39,T.teal);
  for (const z of [-.65,.65])put(fixed,bx+.26,.78,bz+z,.081,.66,.085,T.walnut);
  put(fixed,bx+.26,1.06,bz,.10,.115,1.45,T.oak);
  for(const z of [-.46,-.14,.18]){
    put(fixed,bx+.19,.91,bz+z,.049,.19,.042,T.honey);
    put(fixed,bx+.18,.78,bz+z,.058,.15,.101,T.slate);
  }
  for(const [x,z,w,h] of [[-.18,-.36,.20,.19],[.06,-.52,.24,.24],[-.16,.48,.23,.20]]){
    put(fixed,bx+x,.515+h/2,bz+z,w,h,w,T.copper);
    put(fixed,bx+x,.535+h,bz+z,w+.04,.052,w+.04,T.brick);
    put(fixed,bx+x,.569+h,bz+z,w*.79,.017,w*.79,T.bark);
  }
  put(fixed,bx,.551,bz+.09,.45,.09,.35,T.walnut);
  for (const z of [0,.15])for(const x of [-.13,.13]) put(fixed,bx+x,.631,bz+z,.094,.095,.081,T.sunLeaf);
  const tubX=7.37,tubZ=4.26;
  put(fixed,tubX,.07,tubZ,.52,.64,.48,T.teal);
  for(const y of [-.15,.29])put(fixed,tubX,y,tubZ,.56,.065,.51,T.slate);
  put(fixed,tubX,.415,tubZ,.60,.075,.54,T.oak);
  put(fixed,tubX-.32,.06,tubZ,.17,.06,.065,T.ochre);
  put(fixed,tubX-.389,.007,tubZ,.06,.075,.065,T.ochre);

  cubes('Terrace joinery, landings and potting station',fixed);
  cubes('Garden paving, pond banks and spring masonry',stones);
  cubes('Raised soil and planted furrows',soil,garden,false,earth);
  function moveFish(time,motion) {
    for(const [i,fish] of koi.entries()){
      const angle=motion>0?time*.32+i*2.90:i*2.90, rx=.37+i*.08,rz=.14;
      fish.position.x=pondX+(i?.34:-.37)+Math.sin(angle)*rx*motion;
      fish.position.z=pondZ+(i?.14:-.095)+Math.cos(angle)*rz*motion;
      fish.rotation.y=Math.atan2(Math.sin(angle)*rz,Math.cos(angle)*rx);
    }
  }
  return {flowerGrowthGroup,flowerBlossomGroup,flowerHeads,vegGrowthGroup,vegFruitGroup,
    pondX,pondZ,waterMaterial,moonShimmer,moveFish};
}
