import {cabinPlan,placeObject} from './cabin-plans.js';
import {COTTAGE_COLORS} from './cabin-joinery.js';
import {styleCanvas} from './cabin-style-art.js';
import {buildWhaleCoast,coastColors} from './cabin-whale-coast.js';
import {buildWitchCourt,courtColors} from './cabin-witch-court.js';

const variants={
  whale_coast:{build:buildWhaleCoast,colors:coastColors,planks:[0xc5b79d,0xb9aa93,0xd7c7aa,0xcac1ab],lamp:0xffc879},
  witch_court:{build:buildWitchCourt,colors:courtColors,planks:[0x9f8990,0x917c83,0xab9799,0x99858d],lamp:0xeaa1b5},
};
const timber=[0xc18d64,0xb78059,0xd39d6a,0xcc9261];
const roles=new Map(Object.entries(COTTAGE_COLORS).map(([role,value])=>[value,role]));

// Each parent/batch is one instanced draw. Decorative roots can follow the
// real sash or moving desk without touching the actor, simulation or raycast proxies.
function assemble(T,scene,id,anchors,invalidate){
  const variant=variants[id], attachments=[], buckets=new Map(), owned=new Set(),snowMeshes=[];
  let disposed=false, portraitStatus='unused';
  const groups=new Set(), geometry=new T.BoxGeometry(1,1,1);
  const matte=new T.MeshStandardMaterial({color:0xffffff,roughness:.93});
  const light=new T.MeshStandardMaterial({color:0xffffff,emissive:variant.lamp,emissiveIntensity:.16,roughness:.72});
  owned.add(geometry);owned.add(matte);owned.add(light);
  function space(name,parent=scene,pose=[0,0,0,0]){
    const node=new T.Group();node.name=name;placeObject(node,pose);
    if(groups.has(parent))parent.add(node);else attachments.push([parent,node]);
    groups.add(node);buckets.set(node,{solid:[],lamp:[],snow:[]});
    return node;
  }
  function part(type,parent,w,h,d,x,y,z,tint,rotation){
    buckets.get(parent)[type].push({w,h,d,x,y,z,tint,rotation});
  }
  function block(parent,w,h,d,x,y,z,tint){part('solid',parent,w,h,d,x,y,z,tint);}
  function glow(parent,w,h,d,x,y,z,tint){part('lamp',parent,w,h,d,x,y,z,tint);}
  function snow(parent,w,h,d,x,y,z){part('snow',parent,w,h,d,x,y,z,0xe7ebef);}
  function beam(parent,a,b,w,d,tint){
    const delta=new T.Vector3(...b).sub(new T.Vector3(...a)),h=delta.length();
    const rotation=new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),delta.normalize());
    part('solid',parent,w,h,d,(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2,tint,rotation);
  }
  function art(parent,kind,w,h,x,y,z){
    let map;
    if(kind==='whaleOriginal'){
      portraitStatus='loading';
      map=new T.TextureLoader().load(new URL('./deepseek-whale-maid.jpg',import.meta.url).href,
        ()=>{if(!disposed){portraitStatus='ready';invalidate();}},undefined,
        ()=>{if(!disposed){portraitStatus='error';invalidate();}});
    }else map=new T.CanvasTexture(styleCanvas(id,kind));
    map.colorSpace=T.SRGBColorSpace;map.magFilter=T.NearestFilter;
    const wall=kind!=='view';
    const mat=wall?new T.MeshStandardMaterial({map,roughness:.97}):new T.MeshBasicMaterial({map,alphaTest:.5});
    if(!wall)mat.color=anchors.sky.color;
    const geo=new T.PlaneGeometry(w,h),mesh=new T.Mesh(geo,mat);
    mesh.position.set(x,y,z);mesh.receiveShadow=wall;mesh.name=kind;parent.add(mesh);
    owned.add(map);owned.add(mat);owned.add(geo);
  }
  variant.build({space,block,glow,snow,beam,art},anchors);
  art(space('window panorama',anchors.window),'view',1.96,1.49,0,0,.129);
  const matrix=new T.Matrix4(),identity=new T.Quaternion(),pos=new T.Vector3(),scale=new T.Vector3(),color=new T.Color();
  for(const [node,rows] of buckets){
    for(const [type,items] of Object.entries(rows)){
      if(!items.length)continue;
      const mesh=new T.InstancedMesh(geometry,type==='lamp'?light:matte,items.length);
      mesh.name=node.name+' '+type;mesh.castShadow=type==='solid';mesh.receiveShadow=type!=='lamp';
      items.forEach((a,i)=>{
        matrix.compose(pos.set(a.x,a.y,a.z),a.rotation||identity,scale.set(a.w,a.h,a.d));
        mesh.setMatrixAt(i,matrix);mesh.setColorAt(i,color.setHex(a.tint));
      });
      mesh.computeBoundingSphere();node.add(mesh);owned.add(mesh);
      if(type==='snow'){mesh.visible=false;snowMeshes.push(mesh);}
    }
  }
  return {
    get portraitStatus(){return portraitStatus;},
    mount(){for(const [root,node] of attachments)root.add(node);},
    detach(){for(const [,node] of attachments)node.removeFromParent();},
    weather(night,snowy){light.emissiveIntensity=night?1.16:.14;for(const obj of snowMeshes)obj.visible=snowy;},
    dispose(){disposed=true;this.detach();for(const obj of owned)obj.dispose();},
  };
}

export function createCabinStyles(T,scene,{cottageRoots,anchors,paint,planks,materials,textures,invalidate}){
  let active='cottage',night=false,snowy=false;
  const built=new Map(), cloth=new Map(), spans=new Map(), temp=new T.Color();
  // Baked timber keeps per-vertex colours. Group equal texels into runs once.
  scene.traverse(mesh=>{
    if(mesh.material!==paint)return;
    const attr=mesh.geometry?.attributes.color;
    if(!attr||spans.has(attr))return;
    const runs=[];
    for(let n=0;n<attr.count;){
      const tint=temp.fromBufferAttribute(attr,n).getHex(), first=n++;const r=attr.getX(first),g=attr.getY(first),b=attr.getZ(first);
      while(n<attr.count&&attr.getX(n)===r&&attr.getY(n)===g&&attr.getZ(n)===b)n++;
      if(roles.has(tint))runs.push([first,n,tint]);
    }
    spans.set(attr,runs);
  });
  const dyes=[];
  for(const mat of materials.values()){
    const tint=mat.color.getHex();if(roles.has(tint))dyes.push([mat,tint]);
  }
  const prints=textures.filter(map=>['quilt','rug','cabinet'].includes(map.userData?.cabinSurface))
    .map(map=>[map,map.userData.cabinSurface,map.image]);
  const planksOriginal=planks.instanceColor.array.slice();
  function set(id){
    const next=cabinPlan(id).id;
    if(active===next)return false;
    // Construct before detaching the displayed room so a failed build stays local.
    if(next!=='cottage'&&!built.has(next))built.set(next,assemble(T,scene,next,anchors,invalidate));
    built.get(active)?.detach();
    for(const root of cottageRoots) root.visible=next==='cottage';
    if(next!=='cottage')built.get(next).mount();
    const palette=variants[next]?.colors || COTTAGE_COLORS;
    for(const [attr,runs] of spans){
      for(const [lo,hi,tint] of runs){
        temp.setHex(palette[roles.get(tint)]);
        for(let i=lo;i<hi;i++)attr.setXYZ(i,temp.r,temp.g,temp.b);
      }
      attr.needsUpdate=true;
    }
    for(const [mat,tint] of dyes)mat.color.setHex(palette[roles.get(tint)]);
    if(next==='cottage')planks.instanceColor.array.set(planksOriginal);
    else for(let i=0;i<planks.count;i++){
      const old=temp.fromArray(planksOriginal,i*3).getHex(),index=timber.indexOf(old);
      planks.setColorAt(i,temp.setHex(variants[next].planks[Math.max(0,index)]));
    }
    planks.instanceColor.needsUpdate=true;
    for(const [map,kind,original] of prints){
      const key=next+'/'+kind;
      if(next!=='cottage'&&!cloth.has(key))cloth.set(key,styleCanvas(next,kind));
      map.image=next==='cottage'?original:cloth.get(key);map.needsUpdate=true;
    }
    active=next;built.get(active)?.weather(night,snowy);
    return true;
  }
  return {set,get id(){return active;},get portraitStatus(){return built.get(active)?.portraitStatus||'unused';},
    weather(isNight,snow){if(night===isNight&&snowy===snow)return;night=isNight;snowy=snow;built.get(active)?.weather(night,snowy);},
    dispose(){for(const kit of built.values())kit.dispose();built.clear();cloth.clear();spans.clear();},
  };
}
