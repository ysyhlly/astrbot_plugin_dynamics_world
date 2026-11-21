// Cabinetry, bedding and character placement are measured in the bed's local axes.
export const BED_FRAME = {width:2.43, depth:3.25, halfWidth:1.228, halfDepth:1.655, quiltY:1.043};
export const BED_SEAT = [1.12,.75];
export const BED_SLEEP = [.47,.42];
export const FLOOR_Y = .13;
export const DEFAULT_BODY = {radius:.40, rest:.49, game:.49, sleep:.90};
const EPS = .00001;

export function bedFootprint([x,,z,yaw],radius) {
  const c=Math.abs(Math.cos(yaw)), s=Math.abs(Math.sin(yaw));
  const w=c*BED_FRAME.halfWidth+s*BED_FRAME.halfDepth+radius;
  const d=s*BED_FRAME.halfWidth+c*BED_FRAME.halfDepth+radius;
  return {left:x-w,right:x+w,back:z-d,front:z+d,radius};
}
function inRoom([x,,z],r) {
  // The north and west walls need shoulder clearance. The other sides
  // are open cut edges; keep the footpoint on the floor up to the doorway.
  return x>=-4.86+r && x<=4.89 && z>=-3.54+r && z<=3.66;
}
export function insideBed([x,,z],b) {
  return x>b.left+EPS && x<b.right-EPS && z>b.back+EPS && z<b.front-EPS;
}
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[2]-b[2]);

export function clearBedFloor(point,b) {
  if (!insideBed(point,b)) return point;
  const [x,y,z]=point;
  const exits=[[b.left,y,z],[b.right,y,z],[x,y,b.back],[x,y,b.front]];
  // Prefer the open aisle; the retained west and north walls are solid.
  const usable=exits.filter(p=>inRoom(p,b.radius));
  return (usable.length?usable:exits).reduce((best,p)=>distance(p,point)<distance(best,point)?p:best);
}

// Slab intersection with the open rectangle: walking along its boundary is safe.
export function crossesBed(a,b,rect) {
  let enter=0,leave=1;
  for (const [i,min,max] of [[0,rect.left+EPS,rect.right-EPS],[2,rect.back+EPS,rect.front-EPS]]) {
    const delta=b[i]-a[i];
    if (Math.abs(delta)<EPS) {
      if (a[i]<min || a[i]>max) return false;
    } else {
      const t0=(min-a[i])/delta,t1=(max-a[i])/delta;
      enter=Math.max(enter,Math.min(t0,t1));
      leave=Math.min(leave,Math.max(t0,t1));
      if (enter>=leave) return false;
    }
  }
  return true;
}

function detour(from,to,b) {
  if (!crossesBed(from,to,b)) return [];
  const y=FLOOR_Y;
  const corners=[[b.left,y,b.back],[b.right,y,b.back],[b.right,y,b.front],[b.left,y,b.front]];
  let best=null,bestCost=Infinity;
  for(let i=0;i<4;i++){
    if(!inRoom(corners[i],b.radius)||crossesBed(from,corners[i],b))continue;
    for(const dir of [-1,1]){
      const via=[];
      let length=distance(from,corners[i]);
      for(let n=0;n<4;n++){
        const point=corners[(i+n*dir+4)%4];
        if(!inRoom(point,b.radius))break;
        if(n)length+=distance(via[n-1],point);
        via.push(point);
        if(!crossesBed(point,to,b)){
          const cost=length+distance(point,to);
          if(cost<bestCost){bestCost=cost;best=[...via];}
          break;
        }
      }
    }
  }
  return best;
}

export function avoidBed(path,b) {
  if(!b || path.length<2)return path;
  const first=clearBedFloor(path[0],b),last=clearBedFloor(path.at(-1),b);
  const result=[first];
  for(const point of [...path.slice(1,-1).filter(p=>!insideBed(p,b)),last]){
    const prev=result.at(-1);
    const via=detour(prev,point,b);
    if(via===null) return null;
    for(const next of [...via,point]) if(distance(result.at(-1),next)>EPS) result.push(next);
  }
  return result;
}

export function floorWalk(from,to,progress,b) {
  const path=avoidBed([from,to],b);
  if(!path)return clearBedFloor(from,b);
  if(path.length===1)return [...path[0]];
  if(path.length===2)return path[0].map((v,i)=>v+(path[1][i]-v)*progress);
  const lengths=path.slice(1).map((p,i)=>distance(path[i],p));
  let left=progress*lengths.reduce((a,v)=>a+v,0);
  for(let i=0;i<lengths.length;i++){
    if(left<=lengths[i])return path[i].map((v,k)=>v+(path[i+1][k]-v)*left/lengths[i]);
    left-=lengths[i];
  }
  return [...path.at(-1)];
}

// Probe the loaded rig once. A boot hanging outside the quilt does not hold
// up the torso. Feet, hair, skirts and independently animated limbs inside
// the support footprint all participate. World axes are immaterial here.
export function measureBedBody(T,avatar) {
  const body={...DEFAULT_BODY};
  const part=new T.Box3(), poseMatrix=new T.Matrix4(), modelToBed=new T.Matrix4();
  const phases=[0,.21,.48,.76,1.36,2.65];
  // [xMin,xMax,zMin,zMax,surface height]; the pillows and folded hem sit above the quilt.
  const surfaces=[
    [-1.215,1.215,-1.625,1.625,.6775],[-1.15,1.15,-1.55,1.55,.935],
    [-1.225,1.225,-.565,1.625,BED_FRAME.quiltY],[-1.16,1.16,-.635,-.445,1.0815],
    [-1.03,-.07,-1.385,-.795,1.102], [.05,1.01,-1.385,-.795,1.102],
  ];
  const eachPart=(visit)=>{
    avatar.group.updateMatrixWorld(true);
    avatar.group.traverseVisible(node=>{
      if(!node.isMesh)return;
      if(!node.geometry.boundingBox)node.geometry.computeBoundingBox();
      poseMatrix.multiplyMatrices(modelToBed,node.matrixWorld);
      part.copy(node.geometry.boundingBox).applyMatrix4(poseMatrix);
      visit(part.min,part.max);
    });
  };
  for(const name of ['idle','walk','read']){
    modelToBed.identity();
    for(const t of phases){
      avatar.setPose(name,t);
      eachPart((min,max)=>{
        if(min.y>1.1-FLOOR_Y||max.y<0)return;
        const dx=Math.max(Math.abs(min.x),Math.abs(max.x)),dz=Math.max(Math.abs(min.z),Math.abs(max.z));
        body.radius=Math.max(body.radius,Math.hypot(dx,dz)+.055);
      });
    }
  }
  for(const [key,pose,anchor,yaw] of [['rest','rest',BED_SEAT,Math.PI/2],['game','sit_game',BED_SEAT,Math.PI/2],['sleep','sleep',BED_SLEEP,0]]){
    let lift=-Infinity;
    modelToBed.makeRotationY(yaw).setPosition(anchor[0],0,anchor[1]);
    for(const t of phases){
      avatar.setPose(pose,t);
      eachPart((min,max)=>{
        lift=Math.max(lift,FLOOR_Y-min.y);
        for(const [x0,x1,z0,z1,height] of surfaces){
          if(min.x<x1 && max.x>x0 && min.z<z1 && max.z>z0)lift=Math.max(lift,height-min.y);
        }
      });
    }
    if(Number.isFinite(lift))body[key]=lift+.012;
  }
  return body;
}
