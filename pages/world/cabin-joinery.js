/* Hand-built cutaway cottage: actual joinery, bevelled furniture and draped textiles.
 * Everything shares the room's resource registry and static/local batch lifecycle. */
import {CylinderGeometry, SphereGeometry, TorusGeometry} from 'three';
import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';

export function createCabinJoinery(THREE, {box, sub, material, tex, geometries}) {
  const oak=tex('wood',0x9e7351,.82,2,1), paleOak=tex('wood',0xc29d72,.84,2,1);
  const cream=tex('fabric',0xeee3ca,.96,2,2), sage=tex('fabric',0x849986,.97,2,2);
  const brass=material(0xb89960,.4), trim=0xeadbc1, dark=0x695640;
  let serial=0;
  const geo=(key,build)=>{key='joinery:'+key;if(!geometries.has(key))geometries.set(key,build());return geometries.get(key);};
  function mesh(parent,geometry,x,y,z,mat){
    const m=new THREE.Mesh(geometry,typeof mat==='number'?material(mat):mat);
    m.position.set(x,y,z);m.castShadow=m.receiveShadow=true;parent.add(m);return m;
  }
  function rounded(parent,w,h,d,x,y,z,mat,r=.035){
    r=Math.min(r,w*.24,h*.24,d*.24);
    return mesh(parent,geo([w,h,d,r].join(':'),()=>new RoundedBoxGeometry(w,h,d,2,r)),x,y,z,mat);
  }
  function cylinder(parent,rt,rb,h,x,y,z,mat,n=10){
    return mesh(parent,geo(['c',rt,rb,h,n].join(':'),()=>new CylinderGeometry(rt,rb,h,n)),x,y,z,mat);
  }
  function ball(parent,w,h,d,x,y,z,mat){
    const m=mesh(parent,geo('sphere',()=>new SphereGeometry(1,12,8)),x,y,z,mat);m.scale.set(w,h,d);return m;
  }
  function ring(parent,r,t,x,y,z,mat){return mesh(parent,geo(['torus',r,t].join(':'),()=>new TorusGeometry(r,t,6,16)),x,y,z,mat);}
  function beam(parent,a,b,width,depth,mat){
    const aa=new THREE.Vector3(...a),bb=new THREE.Vector3(...b),v=bb.clone().sub(aa);
    const m=rounded(parent,width,v.length(),depth,...aa.clone().add(bb).multiplyScalar(.5).toArray(),mat,.012);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize());return m;
  }
  function architecture(walls,windowGroup){
    // Recessed sage wainscot and warm exposed timber distinguish structure from plaster.
    box(walls,9.85,.76,.065,0,.66,-3.585,0x91a08b);
    box(walls,.065,.76,7.27,-4.865,.66,0,0x91a08b);
    for(let x=-4.6;x<4.9;x+=.55)box(walls,.035,.72,.035,x,.66,-3.54,0xb4bba0);
    for(let z=-3.3;z<3.6;z+=.55)box(walls,.035,.72,.035,-4.82,.66,z,0xb4bba0);
    for(const [y,h,d] of [[.26,.13,.12],[1.05,.075,.13],[1.1,.035,.17]]){
      box(walls,10,h,d,0,y,-3.54,trim);
      box(walls,d,h,7.3,-4.82,y,0,trim);
    }
    for(const [x,z] of [[-4.93,-3.63],[4.96,-3.63],[-4.93,3.61]]){
      rounded(walls,.25,3.6,.26,x,1.88,z,oak,.025);
      rounded(walls,.33,.15,.34,x,.32,z,paleOak,.015);
      rounded(walls,.34,.16,.34,x,3.52,z,paleOak,.015);
    }
    rounded(walls,10.47,.22,.36,0,3.7,-3.66,oak,.025);
    rounded(walls,.36,.22,7.6,-4.95,3.7,0,oak,.025);
    box(walls,10.42,.045,.43,0,3.85,-3.67,trim);
    box(walls,.43,.045,7.65,-4.95,3.85,0,trim);
    for(const x of [-4.8,4.8])beam(walls,[x,3.04,-3.52],[x+(x<0?.6:-.6),3.6,-3.52],.12,.14,oak);
    for(const z of [-3.5,3.5])beam(walls,[-4.78,3.03,z],[-4.78,3.59,z+(z<0?.57:-.57)],.13,.13,oak);
    // Only the rear roof strip is retained in the cutaway; the room remains visible.
    const roof=sub(walls,0,3.95,-3.76);roof.rotation.x=-.3;
    box(roof,10.7,.09,.83,0,0,0,dark);
    for(let row=0;row<3;row++)for(let col=0;col<24;col++){
      const x=-5.13+col*.445+(row%2)*.12;
      rounded(roof,.435,.045,.33,x,.075+row*.009,-.26+row*.255,[0x657b78,0x718782,0x5b726f][(col+row)%3],.014);
    }
    // Deep stepped window casing and sill, with bracketed ledge.
    for(const x of [-1.075,1.075]){
      rounded(windowGroup,.14,1.82,.25,x,0,.09,paleOak,.015);
      box(windowGroup,.04,1.68,.06,x+(x<0?.09:-.09),0,.245,trim);
    }
    for(const y of [-.88,.88])rounded(windowGroup,2.32,.13,.28,0,y,.1,paleOak,.015);
    rounded(windowGroup,2.57,.09,.57,0,-.94,.18,paleOak,.02);
    rounded(windowGroup,2.46,.06,.38,0,.99,.13,trim,.015);
    for(const x of [-.86,.86])beam(windowGroup,[x,-1.15,-.005],[x,-.97,.32],.085,.08,paleOak);
    cylinder(windowGroup,.035,.035,2.58,0,1.025,.36,brass).rotation.z=Math.PI/2;
    for(const x of [-1.34,1.34])ball(windowGroup,.065,.065,.065,x,1.025,.36,brass);
    const latch=rounded(windowGroup,.035,.16,.035,.09,-.09,.245,brass,.007);latch.rotation.z=.18;
    // Framed botanical relief on the previously empty west wall.
    const art=sub(walls,-4.84,2.42,.14);art.rotation.y=Math.PI/2;
    rounded(art,1.42,1.42,.07,0,0,0,paleOak,.02);
    box(art,1.28,1.28,.02,0,0,.045,0xf0e5cc);
    box(art,1.05,1.05,.01,0,0,.06,0xd7d9bc);
    const disc=cylinder(art,.23,.23,.012,.21,.23,.074,0xd9b78c,24);disc.rotation.x=Math.PI/2;
    beam(art,[-.18,-.44,.09],[.03,.37,.09],.02,.014,0x697e63);
    for(const [x,y,angle] of [[-.23,-.22,.7],[.04,-.09,-.7],[-.13,.1,.7],[.08,.25,-.6]]){
      const leaf=ball(art,.075,.17,.012,x,y,.09,0x7c9375);leaf.rotation.z=angle;
    }
  }
  function curtain(parent){
    // A pleated surface pinched at the tie; normals catch light on real folds.
    const nx=16,ny=20,pos=[],uv=[],indices=[];
    for(let j=0;j<=ny;j++)for(let i=0;i<=nx;i++){
      const u=i/nx,v=j/ny,y=.94-v*1.8;
      const pinch=1;
      pos.push((u-.5)*.31*pinch,y,.065+Math.cos(u*Math.PI*8)*.048*pinch);
      uv.push(u,v);
    }
    for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
      const a=j*(nx+1)+i,b=a+nx+1;indices.push(a,b,a+1,b,b+1,a+1);
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();
    geometries.set('joinery:curtain'+serial++,g);
    // The reverse side is a separate folded surface, avoiding DoubleSide shadow artifacts.
    mesh(parent,g,0,0,0,sage);
    const back=g.clone();back.setIndex(indices.slice().reverse());back.computeVertexNormals();geometries.set('joinery:curtain'+serial++,back);mesh(parent,back,0,0,-.008,sage);
    rounded(parent,.31,.045,.08,0,-.45,.09,brass,.008);
    beam(parent,[.08,-.47,.12],[.1,-.64,.13],.014,.014,brass);
    ball(parent,.025,.05,.025,.1,-.66,.13,brass);
    for(const x of [-.12,-.04,.04,.12])ring(parent,.035,.009,x,.98,.04,brass).rotation.y=Math.PI/2;
  }
  function bed(parent){
    rounded(parent,2.4,.23,3.35,0,.48,0,oak,.045);
    for(const x of [-1.04,1.04])for(const z of [-1.4,1.4]){
      cylinder(parent,.085,.065,.4,x,.28,z,oak);
      cylinder(parent,.09,.09,.06,x,.18,z,brass);
    }
    rounded(parent,2.24,.29,3.14,0,.75,0,cream,.11);
    for(const x of [-1.17,1.17]){
      rounded(parent,.14,1.22,.15,x,.79,-1.62,oak,.035);
      ball(parent,.1,.085,.1,x,1.44,-1.62,paleOak);
    }
    rounded(parent,2.3,.14,.16,0,1.34,-1.63,paleOak,.03);
    rounded(parent,2.26,.09,.12,0,.84,-1.63,paleOak,.02);
    for(let x=-.95;x<1;x+=.24)rounded(parent,.115,.43,.09,x,1.08,-1.63,paleOak,.02);
    for(const [x,z,angle] of [[-.54,-1.1,-.07],[.49,-1.13,.06]]){
      const p=sub(parent,x,.96,z);p.rotation.y=angle;
      rounded(p,.97,.19,.59,0,0,0,cream,.09);
      rounded(p,.99,.035,.6,0,-.025,0,0xd4cbb7,.015);
      rounded(p,.93,.16,.55,0,.018,0,cream,.07);
    }
    // Single continuous draped quilt: the top stays under the existing book/cat anchors.
    const pos=[],uv=[],idx=[],nx=32,nz=30;
    for(let j=0;j<=nz;j++)for(let i=0;i<=nx;i++){
      const u=i/nx,v=j/nz,x=(u-.5)*2.44,z=-.47+v*2.16;
      const edge=Math.pow(Math.max(0,(Math.abs(x)-1.08)/.14),1.4)*.27;
      const end=Math.pow(Math.max(0,(z-1.53)/.16),1.4)*.19;
      const fold=.012*Math.sin(u*35+v*3)*Math.sin(v*8);
      pos.push(x,1.04-edge-end+fold,z);uv.push(u*2,v*2);
    }
    for(let j=0;j<nz;j++)for(let i=0;i<nx;i++){const a=j*(nx+1)+i,b=a+nx+1;idx.push(a,b,a+1,b,b+1,a+1);}
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(idx);g.computeVertexNormals();geometries.set('joinery:quilt',g);
    mesh(parent,g,0,0,0,tex('quilt',0x8da4a3,.98,1,1));
    rounded(parent,2.22,.1,.25,0,1.05,-.42,cream,.04);
    const throwMat=tex('fabric',0xc59873,.96,3,1);
    rounded(parent,2.21,.065,.53,0,1.073,1.12,throwMat,.025);
    for(let x=-1;x<1.1;x+=.105){
      box(parent,.012,.002,.48,x,1.1065,1.12,0xdfc6a2,{castShadow:false});
      box(parent,.025,.018,.12,x,1.074,1.43,0xc59873,{castShadow:false});
    }
    for(const z of [-1.2,0,1.2])box(parent,.012,.025,.16,1.205,.49,z,0xc6aa80,{castShadow:false});
  }
  function desk(parent,chair){
    rounded(parent,3.28,.16,1.3,0,1.35,0,paleOak,.045);
    rounded(parent,3.08,.13,1.13,0,1.23,0,oak,.018);
    for(const x of [-1.43,1.43])for(const z of [-.47,.47]){
      cylinder(parent,.072,.045,1.14,x,.69,z,oak,8);
      cylinder(parent,.049,.049,.09,x,.175,z,brass,8);
    }
    rounded(parent,.8,.35,1.03,.95,1.03,0,paleOak,.025);
    rounded(parent,.7,.25,.045,.95,1.04,.54,oak,.012);
    for(const x of [.84,1.06])cylinder(parent,.025,.025,.05,x,1.05,.584,brass).rotation.x=Math.PI/2;
    rounded(parent,.24,.035,.035,.95,1.05,.61,brass,.008);
    beam(parent,[-1.43,.48,-.47],[1.43,.48,-.47],.065,.065,oak);
    rounded(chair,.85,.13,.8,0,.72,0,paleOak,.05);
    rounded(chair,.73,.09,.66,0,.82,-.025,sage,.04);
    for(const x of [-.32,.32])for(const z of [-.28,.28])beam(chair,[x*1.18,.15,z*1.24],[x,.72,z],.075,.075,oak);
    for(const x of [-.35,.35])beam(chair,[x,.7,.29],[x,1.42,.39],.075,.08,oak);
    rounded(chair,.87,.13,.12,0,1.42,.39,paleOak,.04);
    for(const x of [-.2,0,.2])beam(chair,[x,.86,.31],[x,1.36,.38],.055,.045,paleOak);
    for(const x of [-.34,.34])beam(chair,[x,.38,-.31],[x,.38,.31],.045,.045,oak);
  }
  function mug(parent){
    cylinder(parent,.105,.087,.21,0,.11,0,0x88a293,14);
    const lip=ring(parent,.097,.012,0,.22,0,cream);lip.rotation.x=Math.PI/2;
    cylinder(parent,.087,.087,.006,0,.215,0,0x584533,14);
    ring(parent,.065,.018,.12,.125,0,0x88a293);
    cylinder(parent,.14,.14,.016,0,.009,0,cream,16);
  }
  function lamp(parent){
    cylinder(parent,.19,.21,.045,0,0,0,brass,16);
    cylinder(parent,.028,.033,.48,0,.25,0,brass);
    cylinder(parent,.16,.26,.28,0,.58,0,cream,16);
    for(const [y,r] of [[.44,.263],[.72,.165]]){const rim=ring(parent,r,.012,0,y,0,brass);rim.rotation.x=Math.PI/2;}
    for(let i=0;i<16;i++){const t=i*Math.PI/8;beam(parent,[Math.cos(t)*.255,.445,Math.sin(t)*.255],[Math.cos(t)*.158,.715,Math.sin(t)*.158],.009,.009,0xd9c9a8);}
  }
  function plant(parent){
    cylinder(parent,.32,.32,.045,0,.12,0,0xb3866c,16);
    cylinder(parent,.28,.21,.48,0,.38,0,0xc79f80,16);
    const rim=ring(parent,.28,.035,0,.63,0,0xd6b394);rim.rotation.x=Math.PI/2;
    cylinder(parent,.25,.25,.012,0,.62,0,0x645442,16);
    beam(parent,[0,.63,0],[.04,1.7,0],.028,.027,0x6e7c55);
    for(const [x,y,z,angle] of [[-.24,1.2,0,-.9],[.22,1.42,.02,.8],[-.12,1.69,0,-.6],[.1,1.02,.2,.9],[.29,1.59,-.08,.85]]){
      beam(parent,[.025,y-.12,0],[x,y,z],.014,.014,0x6e7c55);
      const leaf=ball(parent,.11,.25,.043,x,y+.04,z,0x78966c);leaf.rotation.z=angle;leaf.rotation.y=z*3;
    }
  }
  function cookware(pot,kettle){
    cylinder(pot,.15,.13,.17,0,.085,0,0x708578,16);
    const rim=ring(pot,.144,.012,0,.177,0,0xb5b4a2);rim.rotation.x=Math.PI/2;
    cylinder(pot,.13,.13,.008,0,.166,0,0xd8b986,16);
    for(const x of [-.19,.19])ring(pot,.048,.013,x,.12,0,0x5b695d);
    ball(kettle,.105,.095,.105,0,.09,0,0xb5896c);
    cylinder(kettle,.07,.082,.025,0,.18,0,brass,12);
    ball(kettle,.026,.025,.026,0,.211,0,dark);
    ring(kettle,.075,.014,-.075,.13,0,dark);
    beam(kettle,[.07,.1,0],[.16,.19,0],.038,.034,0xb5896c);
  }
  function accents({wardrobe,leftDoor,rightDoor,kitchen,table,stool,shelf}){
    for(const [y,w,d] of [[.25,1.98,1.2],[3.1,2.0,1.2],[3.2,2.12,1.29]])rounded(wardrobe,w,.08,d,0,y,0,paleOak,.025);
    for(const [door,dir] of [[leftDoor,1],[rightDoor,-1]]){
      for(const [y,h] of [[1.59,1.7],[.39,.59]]){
        for(const x of [.09,.75])rounded(door,.035,h,.025,dir*x,y,.115,trim,.006);
        for(const yy of [y-h/2,y+h/2])rounded(door,.68,.035,.025,dir*.42,yy,.115,trim,.006);
      }
      for(const y of [.28,2.3])rounded(door,.06,.14,.045,dir*.04,y,.07,brass,.009);
      ring(door,.055,.011,dir*.72,1.18,.18,brass);
    }
    for(const z of [-.37,.37]){
      for(const zz of [z-.29,z+.29])box(kitchen,.025,.48,.024,.385,.51,zz,trim);
      for(const y of [.27,.75])box(kitchen,.025,.024,.6,.385,y,z,trim);
      ball(kitchen,.026,.026,.026,.42,.68,z+.2,brass);
    }
    // Rectangular ceramic backsplash tiles instead of another flat coloured wall.
    for(let y=1.13;y<1.65;y+=.16)for(let z=-.58;z<.72;z+=.22)rounded(kitchen,.025,.145,.204,-.345,y,z,(Math.round(y*100)+Math.round(z*100))%3?0xdadbc2:0xb1c0ac,.006);
    for(const x of [-.61,.61])beam(table,[x,.62,-.4],[x,.62,.4],.06,.06,oak);
    rounded(stool,.45,.085,.45,0,.75,0,paleOak,.045);
    for(const x of [-.59,.59])beam(shelf,[x,-.31,-.12],[x,-.06,.15],.06,.065,brass);
  }
  return {architecture,curtain,bed,desk,mug,lamp,plant,cookware,accents,rounded,cylinder,ring};
}
