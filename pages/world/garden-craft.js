/* Shared low-poly botanical and joinery shapes. No external textures or models. */
import {BoxGeometry,BufferGeometry,Float32BufferAttribute,SphereGeometry,IcosahedronGeometry,CylinderGeometry,TorusGeometry,Shape,ExtrudeGeometry,SRGBColorSpace,NearestFilter,NearestMipmapLinearFilter,RepeatWrapping} from 'three';
import {RoundedBoxGeometry} from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';

function chamferedTimber(radius=.025){
 // 44 triangles: six faces, twelve edge bevels and eight corner facets.
 const positions=[],uvs=[],inner=.5-radius;
 function face(points){
  const a=points[0],b=points[1],c=points[2],u=b.map((v,i)=>v-a[i]),v=c.map((q,i)=>q-a[i]);
  let normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
  const center=a.map((_,i)=>points.reduce((sum,p)=>sum+p[i],0)/points.length);
  if(normal.reduce((sum,n,i)=>sum+n*center[i],0)<0){points.reverse();normal=normal.map(n=>-n);}
  const drop=normal.map(Math.abs).indexOf(Math.max(...normal.map(Math.abs))),axes=[0,1,2].filter(i=>i!==drop);
  for(let i=1;i<points.length-1;i++)for(const p of [points[0],points[i],points[i+1]]){positions.push(...p);uvs.push(p[axes[0]]+.5,p[axes[1]]+.5);}
 }
 for(let axis=0;axis<3;axis++)for(const sign of [-1,1]){
  const other=[0,1,2].filter(a=>a!==axis),pts=[];
  for(const [a,b] of [[-1,-1],[1,-1],[1,1],[-1,1]]){const p=[0,0,0];p[axis]=sign*.5;p[other[0]]=a*inner;p[other[1]]=b*inner;pts.push(p);}face(pts);
 }
 for(let a=0;a<3;a++)for(let b=a+1;b<3;b++)for(const sa of [-1,1])for(const sb of [-1,1]){
  const along=3-a-b,pts=[];
  for(const [end,side] of [[-1,0],[1,0],[1,1],[-1,1]]){const p=[0,0,0];p[a]=sa*(side?inner:.5);p[b]=sb*(side?.5:inner);p[along]=end*inner;pts.push(p);}face(pts);
 }
 for(const sx of [-1,1])for(const sy of [-1,1])for(const sz of [-1,1]){const signs=[sx,sy,sz];face([0,1,2].map(axis=>signs.map((s,i)=>s*(i===axis?.5:inner))));}
 const g=new BufferGeometry();g.setAttribute('position',new Float32BufferAttribute(positions,3));g.setAttribute('uv',new Float32BufferAttribute(uvs,2));g.computeVertexNormals();return g;
}

// Exposed faces of a small voxel cluster. Instances carry the seasonal colour.
function orchardCrown() {
 const vertices=[],uv=[];
 const levels=[
  ['.....','.###.','.###.','.###.','.....'],
  ['.###.','#####','#####','#####','.###.'],
  ['.###.','#####','#####','#####','.###.'],
  ['..##.','.####','#####','.###.','..#..'],
  ['.....','..##.','.###.','..#..','.....'],
 ];
 const faces=[
  [[1,0,0],[[1,0,1],[1,0,0],[1,1,0],[1,1,1]]],
  [[-1,0,0],[[0,0,0],[0,0,1],[0,1,1],[0,1,0]]],
  [[0,1,0],[[0,1,1],[1,1,1],[1,1,0],[0,1,0]]],
  [[0,-1,0],[[0,0,0],[1,0,0],[1,0,1],[0,0,1]]],
  [[0,0,1],[[0,0,1],[1,0,1],[1,1,1],[0,1,1]]],
  [[0,0,-1],[[1,0,0],[0,0,0],[0,1,0],[1,1,0]]],
 ];
 const solid=(x,y,z)=>levels[y]?.[z]?.[x]==='#';
 for(let y=0;y<5;y++)for(let z=0;z<5;z++)for(let x=0;x<5;x++){
  if(!solid(x,y,z)) continue;
  for(const [[dx,dy,dz],corners] of faces){
   if(solid(x+dx,y+dy,z+dz)) continue;
   for(const n of [0,1,2,0,2,3]){
    const [a,b,c]=corners[n];
    vertices.push((x+a)/5-.5,(y+b)/5-.5,(z+c)/5-.5);
    uv.push(n===1||n===2?1:0,n>=2?1:0);
   }
  }
 }
 const geometry=new BufferGeometry();
 geometry.setAttribute('position',new Float32BufferAttribute(vertices,3));
 geometry.setAttribute('uv',new Float32BufferAttribute(uv,2));
 geometry.computeVertexNormals();
 return geometry;
}

export function createGardenShapes(){
 const sphere=new SphereGeometry(.5,8,5),leaf=new SphereGeometry(.5,6,4);
 const stone=new IcosahedronGeometry(.5,1);
 const pos=stone.attributes.position;
 for(let i=0;i<pos.count;i++){
  const x=pos.getX(i),y=pos.getY(i),z=pos.getZ(i);
  const k=1+.085*Math.sin(x*13+z*17)*Math.cos(y*19);pos.setXYZ(i,x*k,y*k,z*k);
 }
 stone.computeVertexNormals();
 const shape=new Shape();shape.moveTo(-.5,-.5);shape.lineTo(.5,-.5);shape.lineTo(.5,.35);shape.lineTo(0,.5);shape.lineTo(-.5,.35);shape.closePath();
 const picket=new ExtrudeGeometry(shape,{depth:1,bevelEnabled:true,bevelThickness:.018,bevelSize:.025,bevelSegments:1,steps:1});picket.translate(0,0,-.5);
 const grass=new BufferGeometry();
 // Three closed, bent blades; readable from every azimuth without DoubleSide.
 const vertices=[],indices=[];
 for(let n=0;n<3;n++){
  const a=n*Math.PI*2/3,c=Math.cos(a),s=Math.sin(a),off=vertices.length/3;
  const pts=[[-.13,-.5,0],[.13,-.5,0],[.12,.05,.12],[.04,.5,.29],[-.08,.05,.12],[0,-.45,-.06]];
  for(const [x,y,z] of pts)vertices.push(x*c-z*s,y,x*s+z*c);
  for(const tri of [[0,1,2],[0,2,4],[4,2,3],[1,5,2],[2,5,3],[3,5,4],[4,5,0],[0,5,1]])indices.push(...tri.map(i=>i+off));
 }
 grass.setAttribute('position',new Float32BufferAttribute(vertices,3));grass.setIndex(indices);grass.computeVertexNormals();
 const pad=new CylinderGeometry(.5,.5,1,20,1,false,.18,Math.PI*2-.36);
 const linen=new BufferGeometry();
 const lp=[],lu=[],li=[],nx=12,ny=10;
 for(let j=0;j<=ny;j++)for(let i=0;i<=nx;i++){const u=i/nx,v=j/ny;lp.push((u-.5),.5-v,.045*Math.sin(u*6*Math.PI)*(v*.7+.3));lu.push(u,v);}
 for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){const a=j*(nx+1)+i,b=a+nx+1;li.push(a,b,a+1,b,b+1,a+1,a,a+1,b,b,a+1,b+1);}
 linen.setAttribute('position',new Float32BufferAttribute(lp,3));linen.setAttribute('uv',new Float32BufferAttribute(lu,2));linen.setIndex(li);linen.computeVertexNormals();
 // Deliberately smooth and double-wound cloth uses a fixed front/back normal per face after expansion.
 const cloth=linen.toNonIndexed();cloth.computeVertexNormals();linen.dispose();
 return {
  voxel:new BoxGeometry(1,1,1),soft:new RoundedBoxGeometry(1,1,1,1,.075),timber:chamferedTimber(),
  sphere,leaf,stone,clod:new IcosahedronGeometry(.5,0),crown:orchardCrown(),stem:new CylinderGeometry(.34,.5,1,7),
  cylinder:new CylinderGeometry(.5,.5,1,12),pot:new CylinderGeometry(.5,.37,1,12),
  cone:new CylinderGeometry(.16,.5,1,8),ring:new TorusGeometry(.5,.025,5,20),
  tubeRing:new TorusGeometry(.5,.07,6,16),picket,grass,pad,cloth,
 };
}

export function createGardenSurface(THREE,kind,color){
 const canvas=document.createElement('canvas');canvas.width=canvas.height=32;const g=canvas.getContext('2d');
 g.fillStyle='#ffffff';g.fillRect(0,0,32,32);
 let seed=31;const rnd=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
 if(kind==='wood'){
  for(let n=0;n<17;n++){
   g.fillStyle=n%3?'#ecdfcf':'#d8cbbf';
   g.fillRect(Math.floor(rnd()*32),Math.floor(rnd()*32),2+Math.floor(rnd()*9),1);
  }
 }else{
  for(let n=0;n<45;n++){
   const x=Math.floor(rnd()*32),y=Math.floor(rnd()*32);
   g.fillStyle=n%3?'#e4e2cf':'#cfd2be';
   g.fillRect(x,y,2+n%3,1);
   if(n%5===0) g.fillRect(x+1,y-1,1,1);
  }
 }
 const texture=new THREE.CanvasTexture(canvas);
 texture.colorSpace=SRGBColorSpace;
 texture.magFilter=NearestFilter; texture.minFilter=NearestMipmapLinearFilter;
 texture.wrapS=texture.wrapT=RepeatWrapping;
 const mat=new THREE.MeshStandardMaterial({color,roughness:kind==='wood'?.86:.98,map:texture});
 return {material:mat,texture};
}
