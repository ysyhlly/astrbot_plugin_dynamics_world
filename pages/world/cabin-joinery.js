/* Cutaway timber cottage. Large forms define the silhouette at garden scale.
 * The painted planes stay crisp in close-ups and follow their furniture roots. */
import {BED_FRAME} from './cabin-bed.js';

const C = {
  ink: 0x34313b, bark: 0x59404a, walnut: 0x855448, oak: 0xb87c52, honey: 0xdca365,
  chalk: 0xffe3ad, plaster: 0xe9c998, clay: 0xae5546, rose: 0xd87b5d,
  pine: 0x315c61, teal: 0x447e7a, sage: 0x81a98d, pale: 0xc3cc9b,
  slate: 0x334658, sea: 0x446575, mint: 0x63858b, brass: 0xe1ad63,
  mortar: 0x6a6670, stone: 0x98878a, lightStone: 0xbca99e, brick: 0xab6556,
};
export {C as COTTAGE_COLORS};

export function createCabinJoinery(THREE, {box, sub, tex, geometries}) {
  // One vertex-coloured material lets the existing baker merge adjacent colours
  // in a single draw, while its local roots keep hinges and movable pieces live.
  const paint = new THREE.MeshStandardMaterial({vertexColors:true, roughness:.92});
  function block(parent, w, h, d, x, y, z, tint) {
    const key = 'cottage-tint:' + tint;
    if (!geometries.has(key)) {
      const geometry = new THREE.BoxGeometry(1,1,1);
      const color = new THREE.Color(tint);
      const rgb = [];
      for (let n=0;n<geometry.attributes.position.count;n++) rgb.push(color.r,color.g,color.b);
      geometry.setAttribute('color',new THREE.Float32BufferAttribute(rgb,3));
      geometries.set(key,geometry);
    }
    const mesh = new THREE.Mesh(geometries.get(key),paint);
    mesh.position.set(x,y,z);
    mesh.scale.set(w,h,d);
    mesh.castShadow=mesh.receiveShadow=true;
    parent.add(mesh);
    return mesh;
  }
  function panel(parent, kind, w, h, x, y, z, flat=false) {
    const key = 'cottage-print:' + w + '/' + h;
    if (!geometries.has(key)) geometries.set(key,new THREE.PlaneGeometry(w,h));
    const face = new THREE.Mesh(geometries.get(key),tex(kind,0xffffff,.98));
    face.position.set(x,y,z);
    if (flat) face.rotation.x=-Math.PI/2;
    face.receiveShadow=true;
    parent.add(face);
    return face;
  }
  function brace(parent, a, b, w, d, tint) {
    const from = new THREE.Vector3(...a), to = new THREE.Vector3(...b);
    const axis = to.clone().sub(from);
    const m = block(parent,w,axis.length(),d,...from.lerp(to,.5).toArray(),tint);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),axis.normalize());
  }
  function foundation(parent) {
    block(parent,10.42,.35,7.91,0,-.18,0,C.mortar);
    for (let level=0;level<2;level++) {
      for (const [side, length] of [['front',10.36],['east',7.86]]) {
        const min=-length/2, max=length/2;
        for (let i=0,lo=min-.36*level;lo<max;lo+=.72,i++) {
          const left=Math.max(min,lo), right=Math.min(max,lo+.69);
          if (right<=left) continue;
          const mid=(left+right)/2, span=right-left, y=-.26+.165*level;
          const color=[C.stone,C.lightStone,0xa28d88,0x918886][(i+level*2)%4];
          if (side==='front') block(parent,span,.145,.14,mid,y,3.94,color);
          else block(parent,.14,.145,span,5.18,y,mid,color);
        }
      }
    }
    block(parent,10.42,.1,7.9,0,.005,0,C.bark);
    block(parent,10.16,.07,7.63,0,.075,0,C.walnut);
    for (const z of [-3.61,3.64]) block(parent,10,.055,.16,0,.115,z,C.honey);
    for (const x of [-4.9,4.9]) block(parent,.16,.055,7.4,x,.115,0,C.honey);
  }
  function architecture(walls, windowGroup) {
    const rear = -3.72, west=-5;
    block(walls,10.2,3.45,.22,0,1.83,rear,C.plaster);
    block(walls,.22,3.45,7.45,west,1.83,0,0xd6b787);
    // Tongue-and-groove skirting with a continuous timber cap.
    for (let i=0;i<25;i++) {
      block(walls,.384,.82,.09,-4.8+i*.4,.64,-3.566,[C.teal,0x4e8078,0x4d7873][i%3]);
    }
    for (let i=0;i<18;i++) block(walls,.09,.82,.386,-4.845,.64,-3.39+i*.4,i%3?C.teal:0x538077);
    for (const [y,h,tint] of [[.23,.15,C.bark],[1.08,.10,C.walnut],[1.15,.045,C.honey]]) {
      block(walls,10,h,.17,0,y,-3.54,tint);
      block(walls,.17,h,7.4,-4.82,y,0,tint);
    }
    for (const [x,z] of [[-4.95,-3.62],[4.96,-3.62],[-4.95,3.62]]) {
      block(walls,.25,3.46,.27,x,1.9,z,C.walnut);
      block(walls,.32,.25,.34,x,.29,z,C.stone);
      block(walls,.36,.16,.37,x,3.48,z,C.honey);
    }
    block(walls,10.52,.22,.36,0,3.6,-3.67,C.bark);
    block(walls,.36,.22,7.72,-4.95,3.6,0,C.bark);
    for (const x of [-4.83,4.83]) brace(walls,[x,2.9,-3.52],[x-Math.sign(x)*.68,3.54,-3.52],.16,.16,C.walnut);
    for (const z of [-3.49,3.49]) brace(walls,[-4.79,2.92,z],[-4.79,3.54,z-Math.sign(z)*.62],.14,.15,C.walnut);

    // North gable and its exposed cut. Each rise has roof bedding, fascia and
    // overlapping slates. The matching strip on the west wall leaves the sightline open.
    const roofColors=[C.sea,C.slate,0x52727c,0x40586a];
    for (let step=0;step<10;step++) {
      const rise=(step+1)*.19, top=3.60+rise;
      for (const sign of [-1,1]) {
        const x=sign*(4.75-step*.5);
        block(walls,.5,rise,.24,x,3.60+rise/2,rear,step%3?C.plaster:0xe3c295);
        block(walls,.54,.15,1.10,x,top,-3.72,C.bark);
        block(walls,.52,.065,.10,x,top+.033,-3.14,C.honey);
        for (let tile=0;tile<3;tile++) {
          const z=-4.12+tile*.395;
          block(walls,.55,.1,.37,x,top+.11,z,roofColors[(step+tile*2+(sign>0?1:0))%4]);
        }
      }
    }
    block(walls,.36,.16,1.18,0,5.69,-3.73,C.mint);
    for (let course=0;course<3;course++) {
      const x=-5.30+course*.39,y=3.62+course*.145;
      block(walls,.43,.15,7.1,x,y,.38,C.bark);
      for (let tile=0;tile<14;tile++) {
        const z=-2.93+tile*.51;
        block(walls,.43,.11,.486,x,y+.105,z,roofColors[(tile+course*2)%4]);
      }
    }
    for (const x of [-3.0,-1.5,0,1.5,3.0]) {
      const h=1.88-Math.abs(x)*.38;
      block(walls,.12,h,.09,x,3.61+h/2,-3.555,C.walnut);
    }
    for (const sign of [-1,1]) brace(walls,[sign*3.65,3.66,-3.53],[sign*1.15,4.59,-3.53],.105,.09,C.walnut);
    // Stepped amber transom, mullions and a deep casing below the ridge.
    for (const [w,h,z,color] of [[1.13,.59,-3.49,C.bark],[.80,.88,-3.49,C.bark],[.94,.45,-3.422,C.brass],
                                  [.64,.73,-3.422,C.brass],[.78,.32,-3.364,0x4d737c],[.48,.58,-3.364,0x699194]]) {
      block(walls,w,h,.095,0,4.48,z,color);
    }
    block(walls,.07,.63,.07,0,4.48,-3.285,C.brass);
    block(walls,.83,.065,.07,0,4.48,-3.285,C.brass);

    for (const x of [-1.08,1.08]) block(windowGroup,.15,1.87,.25,x,0,.09,C.walnut);
    for (const y of [-.88,.88]) block(windowGroup,2.32,.16,.25,0,y,.10,C.oak);
    block(windowGroup,2.59,.095,.56,0,-.90,.18,C.honey);
    for (const x of [-.86,.86]) brace(windowGroup,[x,-1.15,0],[x,-.96,.31],.09,.1,C.walnut);
    block(windowGroup,2.55,.075,.08,0,1.03,.35,C.bark);
    for (const x of [-1.31,1.31]) block(windowGroup,.105,.12,.12,x,1.03,.35,C.brass);

    const art=sub(walls,-4.86,2.32,-1.28);
    art.rotation.y=Math.PI/2;
    block(art,1.58,1.52,.055,0,0,0,C.bark);
    panel(art,'almanac',1.43,1.37,0,0,.032);
    for (const y of [-.77,.77]) block(art,1.68,.075,.1,0,y,.03,C.honey);
    // A small herb-drying rail sits between the wall hanging and the stove.
    const herbs=sub(walls,-4.86,2.25,1.25);
    herbs.rotation.y=Math.PI/2;
    block(herbs,1.08,.10,.11,0,.37,.02,C.walnut);
    for (const [i,x] of [-.34,0,.34].entries()) {
      block(herbs,.055,.18,.075,x,.29,.08,C.brass);
      block(herbs,.035,.35,.04,x,.10,.10,C.oak);
      for (let j=0;j<3;j++) {
        const tint=[C.sage,0x7c8279,0x779984][i];
        block(herbs,.12,.21,.09,x+(j-1)*.073,-.04-Math.abs(j-1)*.07,.12,tint);
      }
      block(herbs,.10,.065,.09,x,.10,.13,C.brass);
    }
  }
  function entry(frame, pivot) {
    block(frame,1.6,.06,.22,0,.014,.29,C.honey);
    block(frame,1.32,.028,.57,0,.02,-.11,C.teal);
    for (const z of [-.32,.1]) block(frame,1.2,.012,.055,0,.04,z,C.brass);
    // The front wall is cut below the eye line. Its half-door still swings
    // outward on the character/cat threshold hinge.
    for (const x of [-.74,.75]) {
      block(frame,.15,.99,.19,x,.49,.35,C.walnut);
      block(frame,.20,.105,.23,x,1.02,.35,C.honey);
    }
    for (let i=0;i<7;i++) block(pivot,.18,.72,.09,.115+i*.195,.39,0,i%2?C.teal:C.pine);
    for (const y of [.14,.67]) block(pivot,1.38,.115,.11,.69,y,.03,C.oak);
    block(pivot,1.41,.075,.17,.69,.79,0,C.honey);
    for (const y of [.20,.64]) block(pivot,.30,.045,.035,.18,y,.102,C.ink);
    block(pivot,.10,.075,.065,1.20,.60,.10,C.brass);
  }
  function curtain(parent) {
    for (let i=0;i<5;i++) {
      const x=-.128+i*.064, z=i%2?.09:.055, height=1.73+(i%2)*.055;
      block(parent,.064,height,.068,x,.05,z,i%2?C.clay:C.rose);
      for (const y of [-.70,.70]) block(parent,.064,.06,.024,x,y,z+.042,C.chalk);
      block(parent,.055,.10,.085,x,.944,z,C.brass);
    }
  }
  function bed(parent) {
    for (const x of [-1.12,1.12]) for (const z of [-1.51,1.51]) {
      const h=z<0?1.24:.54;
      block(parent,.18,h,.18,x,.14+h/2,z,C.walnut);
      block(parent,.235,.12,.235,x,.14+h,z,C.honey);
    }
    block(parent,2.37,.30,3.18,0,.45,0,C.walnut);
    block(parent,BED_FRAME.width,.085,BED_FRAME.depth,0,.635,0,C.honey);
    block(parent,2.30,.26,3.10,0,.805,0,C.chalk);
    block(parent,2.23,.56,.15,0,1.05,-1.52,C.pine);
    block(parent,1.79,.15,.15,0,1.37,-1.52,C.teal);
    block(parent,1.30,.09,.18,0,1.48,-1.52,C.honey);
    for (const x of [-.77,-.38,0,.38,.77]) {
      block(parent,.08,.16,.035,x,1.13,-1.425,C.brass);
      block(parent,.16,.065,.036,x,1.13,-1.423,C.brass);
    }
    for (const x of [-.55,.53]) {
      block(parent,.96,.13,.59,x,.969,-1.09,C.plaster);
      block(parent,.84,.08,.49,x,1.052,-1.09,C.chalk);
      block(parent,.12,.016,.49,x-.27,1.095,-1.09,C.honey);
    }
    block(parent,2.34,.11,2.13,0,.985,.50,C.clay);
    panel(parent,'quilt',2.31,2.07,0,BED_FRAME.quiltY,.50,true);
    for (const x of [-1.18,1.18]) {
      block(parent,.09,.20,2.09,x,.924,.50,C.clay);
      block(parent,.095,.055,2.09,x,.840,.50,C.brass);
    }
    block(parent,2.39,.18,.11,0,.944,1.57,C.clay);
    for (let i=0;i<13;i++) block(parent,.095,.085,.055,-1.08+i*.18,.837,1.60,i%2?C.chalk:C.brass);
    block(parent,2.32,.085,.19,0,1.039,-.54,C.chalk);
  }
  function desk(parent,chair) {
    block(parent,3.25,.11,1.29,0,1.37,0,C.honey);
    block(parent,3.14,.14,1.22,0,1.255,0,C.walnut);
    for (const x of [-1.39,1.33]) {
      for (const z of [-.46,.46]) {
        block(parent,.14,1.04,.14,x,.67,z,C.pine);
        block(parent,.175,.105,.175,x,.21,z,C.honey);
      }
      block(parent,.115,.105,1.00,x,.45,0,C.teal);
    }
    block(parent,2.73,.10,.11,0,.46,-.46,C.teal);
    block(parent,.87,.54,1.10,1.03,.97,-.02,C.pine);
    for (const y of [.84,1.095]) {
      block(parent,.77,.21,.055,1.03,y,.56,C.teal);
      block(parent,.22,.06,.07,1.03,y+.03,.61,C.brass);
    }
    for (const x of [-.34,.34]) for (const z of [-.29,.29]) {
      block(chair,.09,.58,.09,x,.43,z,C.walnut);
    }
    block(chair,.88,.13,.80,0,.74,0,C.honey);
    block(chair,.75,.08,.66,0,.833,-.035,C.teal);
    for (const x of [-.35,.35]) block(chair,.095,.74,.1,x,1.07,.32,C.walnut);
    block(chair,.82,.18,.09,0,1.36,.32,C.teal);
    for (const x of [-.19,.19]) block(chair,.07,.29,.07,x,1.09,.32,C.honey);
    block(chair,.90,.065,.16,0,1.48,.32,C.honey);
  }
  function rug(parent) {
    block(parent,3.65,.038,2.18,0,0,0,C.bark);
    panel(parent,'rug',3.64,2.17,0,.022,0,true);
    for (const x of [-1.86,1.86]) for (let i=0;i<17;i++) {
      block(parent,.11,.018,.054,x,.006,-.99+i*.125,i%3?C.chalk:C.brass);
    }
  }
  function shelf(parent) {
    block(parent,1.75,.10,.49,0,0,0,C.honey);
    block(parent,1.61,.13,.11,0,-.07,-.15,C.walnut);
    for (const x of [-.64,.64]) brace(parent,[x,-.30,-.14],[x,-.06,.17],.09,.095,C.pine);
    const covers=[C.clay,C.chalk,C.pine,C.brass,0x86516a,C.teal];
    for (let i=0;i<6;i++) {
      const h=[.45,.52,.39,.57,.47,.40][i], x=-.64+i*.185;
      block(parent,.15,h,.29,x,.06+h/2,0,covers[i]);
      block(parent,.10,.055,.02,x,.15,.151,i===1?C.clay:C.chalk);
      block(parent,.12,.027,.025,x,h+.005,.151,C.brass);
    }
    block(parent,.35,.09,.29,.56,.10,.01,C.teal);
    block(parent,.29,.08,.24,.59,.19,.01,C.rose);
  }
  // Only the cut-away east side lacks a wall to support a relocated shelf.
  function shelfStand(parent) {
    for (const x of [-.70,.70]) {
      block(parent,.10,2.24,.12,x,-1.13,-.10,C.pine);
      block(parent,.16,.115,.46,x,-2.22,-.015,C.walnut);
    }
    block(parent,1.46,.075,.40,0,-1.90,-.02,C.honey);
  }
  function wallLantern(walls,glass) {
    const hook=sub(walls,-4.86,2.61,-2.68);
    hook.rotation.y=Math.PI/2;
    block(hook,.22,.27,.10,0,.31,0,C.walnut);
    block(hook,.08,.075,.33,0,.392,.13,C.brass);
    block(hook,.045,.14,.05,0,.29,.275,C.bark);
    block(hook,.33,.075,.26,0,.18,.275,C.pine);
    box(hook,.255,.31,.21,0,-.012,.275,0xffffff,{material:glass});
    for (const x of [-.13,.13]) for (const z of [.165,.385]) block(hook,.028,.32,.025,x,-.012,z,C.walnut);
    block(hook,.32,.075,.25,0,-.205,.275,C.brass);
    const light=new THREE.PointLight(0xffb878,0,6.4,2);
    light.position.set(0,-.08,.54);
    hook.add(light);
    return light;
  }
  function wardrobe(parent,leftDoor,rightDoor) {
    for (const x of [-.78,.78]) for (const z of [-.42,.42]) block(parent,.17,.18,.17,x,.22,z,C.walnut);
    block(parent,1.9,.16,1.12,0,.36,0,C.bark);
    for (const x of [-.89,.89]) block(parent,.14,2.69,1.12,x,1.74,0,C.pine);
    block(parent,1.69,2.65,.09,0,1.74,-.51,C.walnut);
    block(parent,1.69,.085,.96,0,.66,-.035,C.oak);
    block(parent,1.71,.06,.06,0,2.62,0,C.brass);
    for (const [x,tint,h] of [[-.50,C.rose,1.12],[0,C.sage,.91],[.50,C.brass,1.03]]) {
      block(parent,.045,.17,.045,x,2.54,0,C.brass);
      block(parent,.45,.105,.14,x,2.42,.025,tint);
      block(parent,.31,h,.16,x,2.39-h/2,.025,tint);
    }
    for (const [i,tint] of [C.rose,C.sage,C.chalk].entries()) block(parent,.55,.075,.51,-.40,.75+i*.08,-.025,tint);
    block(parent,2.04,.14,1.22,0,3.11,0,C.walnut);
    block(parent,2.17,.09,1.31,0,3.225,0,C.honey);
    for (const [door,dir] of [[leftDoor,1],[rightDoor,-1]]) {
      const cx=dir*.42;
      block(door,.83,2.63,.105,cx,1.315,0,C.pine);
      block(door,.72,1.82,.055,cx,1.60,.080,C.oak);
      panel(door,'cabinet',.63,1.70,cx,1.60,.109);
      block(door,.68,.48,.065,cx,.39,.078,C.teal);
      for (const y of [.17,.61]) block(door,.68,.038,.027,cx,y,.126,C.honey);
      for (const y of [.35,2.37]) block(door,.18,.073,.03,dir*.12,y,.13,C.brass);
      block(door,.075,.18,.068,dir*.72,1.19,.146,C.brass);
    }
    block(parent,1.11,.27,.69,0,3.41,0,C.oak);
    block(parent,1.15,.105,.73,0,3.595,0,C.honey);
    for (const x of [-.39,.39]) block(parent,.095,.34,.75,x,3.44,0,C.bark);
    block(parent,.13,.10,.045,0,3.46,.371,C.brass);
  }
  function mug(parent) {
    block(parent,.28,.025,.25,0,.012,0,C.chalk);
    block(parent,.19,.18,.18,0,.12,0,C.teal);
    block(parent,.21,.035,.20,0,.218,0,C.chalk);
    block(parent,.15,.016,.145,0,.238,0,C.bark);
    for (const y of [.08,.17]) block(parent,.095,.034,.045,.132,y,0,C.teal);
    block(parent,.035,.105,.045,.164,.125,0,C.teal);
  }
  function lamp(parent,bulb) {
    block(parent,.37,.055,.29,0,.03,0,C.pine);
    block(parent,.25,.065,.20,0,.09,0,C.brass);
    block(parent,.075,.35,.075,0,.27,0,C.walnut);
    block(parent,.36,.045,.31,0,.44,0,C.brass);
    box(parent,.32,.25,.26,0,.59,0,0xffffff,{material:bulb});
    for (const x of [-.167,.167]) for (const z of [-.138,.138]) block(parent,.024,.28,.024,x,.59,z,C.walnut);
    block(parent,.40,.075,.34,0,.755,0,C.pine);
    block(parent,.29,.075,.25,0,.823,0,C.teal);
    block(parent,.11,.065,.12,0,.88,0,C.brass);
  }
  function plant(parent) {
    block(parent,.49,.08,.46,0,.17,0,C.bark);
    block(parent,.47,.29,.43,0,.35,0,C.clay);
    block(parent,.55,.14,.50,0,.55,0,C.rose);
    block(parent,.60,.085,.56,0,.65,0,C.brass);
    block(parent,.47,.025,.43,0,.698,0,C.bark);
    for (const [x,y,z,sign] of [[-.13,1.24,.07,-1],[.06,1.55,-.08,1],[.18,1.12,.06,1],[-.16,.95,-.1,-1]]) {
      brace(parent,[0,.70,0],[x,y,z],.045,.045,C.pine);
      block(parent,.16,.15,.115,x,y,z,C.teal);
      block(parent,.18,.13,.12,x+sign*.105,y+.095,z,C.sage);
      block(parent,.09,.11,.095,x+sign*.197,y+.168,z,C.pale);
    }
  }
  function cookware(pot,kettle) {
    block(pot,.26,.15,.25,0,.087,0,C.pine);
    block(pot,.30,.04,.28,0,.176,0,C.teal);
    block(pot,.23,.018,.20,0,.201,0,C.brass);
    for (const x of [-.176,.176]) block(pot,.07,.045,.10,x,.13,0,C.bark);
    block(kettle,.17,.13,.16,0,.075,0,C.rose);
    block(kettle,.15,.045,.15,0,.16,0,C.clay);
    block(kettle,.055,.038,.055,0,.199,0,C.brass);
    block(kettle,.075,.06,.07,.11,.105,0,C.rose);
    block(kettle,.045,.065,.055,.16,.156,0,C.brass);
    for (const y of [.075,.15]) block(kettle,.065,.028,.035,-.106,y,0,C.bark);
    block(kettle,.028,.09,.035,-.136,.112,0,C.bark);
  }
  function range(parent) {
    // Brick firebox, worktop and flue all sit against the west wall.
    block(parent,.72,.80,1.54,0,.54,0,C.plaster);
    block(parent,.76,.11,1.58,0,.205,0,C.bark);
    block(parent,.82,.105,1.64,0,.966,0,C.stone);
    block(parent,.38,.026,.72,.073,1.027,-.32,C.ink);
    block(parent,.07,.46,.58,.383,.57,-.36,C.bark);
    block(parent,.035,.30,.40,.435,.56,-.36,C.ink);
    for (const z of [-.49,-.39,-.29,-.19]) block(parent,.022,.15,.035,.463,.51,z,C.brick);
    block(parent,.045,.055,.45,.46,.76,-.36,C.brass);
    block(parent,.046,.49,.59,.39,.56,.40,C.teal);
    block(parent,.05,.07,.19,.43,.71,.41,C.brass);
    block(parent,.085,.69,1.51,-.31,1.35,0,C.mortar);
    for (let row=0;row<4;row++) for (let col=0;col<6;col++) {
      block(parent,.035,.14,.224,-.247,1.08+row*.16,-.60+col*.24,(col+row)%3?C.chalk:C.sage);
    }
    // Deep copper hood over the burner, pantry ledges beside it.
    for (const [w,h,d,x,y,tint] of [[.64,.10,.86,-.08,1.82,C.bark],[.56,.15,.76,-.10,1.94,C.clay],
      [.47,.13,.64,-.15,2.08,C.rose],[.33,.11,.48,-.19,2.20,C.brass]]) block(parent,w,h,d,x,y,-.37,tint);
    block(parent,.34,1.37,.39,-.23,2.92,-.37,C.mortar);
    for (let i=0;i<10;i++) {
      const width=i%2?.37:.32;
      block(parent,width,.122,.38,-.22,2.32+i*.143,-.37,i%3?C.brick:C.clay);
    }
    for (let i=0;i<6;i++) {
      const y=3.73+i*.15;
      block(parent,.49,.135,.53,-.23,y,-.37,i%3?C.brick:C.rose);
      block(parent,.026,.078,.11,-.23+.25,y,-.39+(i%2)*.12,C.plaster);
    }
    block(parent,.62,.10,.67,-.23,4.58,-.37,C.bark);
    block(parent,.51,.11,.55,-.23,4.685,-.37,C.brick);
    block(parent,.34,.015,.38,-.23,4.75,-.37,C.ink);
    for (const y of [1.45,1.94]) {
      block(parent,.33,.07,.61,-.20,y,.47,C.oak);
      for (const [i,z] of [.28,.48,.66].entries()) {
        block(parent,.12,.17,.115,-.17,y+.118,z,[C.sage,C.rose,C.chalk][i]);
        block(parent,.13,.038,.125,-.17,y+.222,z,C.walnut);
      }
    }
  }
  function basin(parent) {
    block(parent,.55,.68,.72,0,.50,0,C.pine);
    block(parent,.04,.52,.58,.29,.51,0,C.teal);
    block(parent,.06,.055,.17,.33,.67,.11,C.brass);
    block(parent,.66,.085,.82,0,.885,0,C.chalk);
    block(parent,.50,.023,.62,.025,.936,0,C.mint);
    for (const x of [-.26,.29]) block(parent,.055,.045,.69,x,.951,0,C.chalk);
    for (const z of [-.315,.315]) block(parent,.55,.045,.055,.02,.951,z,C.chalk);
    block(parent,.045,.195,.045,-.24,1.03,0,C.brass);
    block(parent,.165,.045,.045,-.177,1.11,0,C.brass);
    block(parent,.055,.055,.05,-.108,1.086,0,C.brass);
    block(parent,.06,.68,.54,-.285,1.55,0,C.walnut);
    block(parent,.028,.55,.43,-.238,1.55,0,0x91b8b6);
    block(parent,.016,.07,.16,-.217,1.71,-.06,C.chalk);
    block(parent,.08,.06,.31,-.21,1.26,.51,C.brass);
    block(parent,.05,.36,.25,-.18,1.10,.51,C.rose);
  }
  function sideTable(parent,stool) {
    block(parent,1.60,.105,1.14,0,.796,0,C.honey);
    block(parent,1.46,.16,1.04,0,.676,0,C.walnut);
    for (const x of [-.59,.59]) for (const z of [-.40,.40]) block(parent,.12,.52,.12,x,.405,z,C.pine);
    block(parent,1.26,.085,.10,0,.295,-.40,C.teal);
    // Charging dock backs the screen; the left half of the table is the dining place.
    block(parent,.52,.090,.35,0,.888,-.055,C.pine);
    const rest=block(parent,.40,.31,.08,0,1.06,-.15,C.teal);
    rest.rotation.x=-.28;
    block(stool,.49,.095,.48,0,.755,0,C.honey);
    for (const x of [-.16,.16]) for (const z of [-.16,.16]) block(stool,.075,.57,.075,x,.435,z,C.walnut);
    block(stool,.38,.045,.045,0,.33,.16,C.teal);
  }
  return {paint,foundation,architecture,entry,curtain,bed,desk,rug,shelf,shelfStand,wallLantern,wardrobe,mug,lamp,plant,cookware,range,basin,sideTable};
}
