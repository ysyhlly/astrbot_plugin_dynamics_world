/* Crisp low-res pixel-art render pass: nearest upscale, depth-jump outlines, ridge/crease shading and Bayer dithering. */
import {DepthTexture,HalfFloatType,NearestFilter,ShaderMaterial,Vector2,WebGLRenderTarget} from 'three';
import {FullScreenQuad} from 'three/examples/jsm/postprocessing/Pass.js';

const VERTEX_SHADER=`
varying vec2 vUv;
void main(){
 vUv=uv;
 gl_Position=vec4(position.xy,0.0,1.0);
}`;

const FRAGMENT_SHADER=`
uniform sampler2D tDiffuse;
uniform sampler2D tDepth;
uniform vec2 uResolution;
uniform float uNear;
uniform float uFar;
uniform float uNight;
uniform float uExposure;
varying vec2 vUv;

vec3 myRRTAndODTFit(vec3 v){
 vec3 a=v*(v+0.0245786)-0.000090537;
 vec3 b=v*(0.983729*v+0.4329510)+0.238081;
 return a/b;
}

vec3 myACESFilmic(vec3 color){
 const mat3 inMat=mat3(
  vec3(0.59719,0.07600,0.02840),
  vec3(0.35458,0.90834,0.13383),
  vec3(0.04823,0.01566,0.83777)
 );
 const mat3 outMat=mat3(
  vec3(1.60475,-0.10208,-0.00327),
  vec3(-0.53108,1.10813,-0.07276),
  vec3(-0.07367,-0.00605,1.07602)
 );
 color*=uExposure/0.6;
 color=inMat*color;
 color=myRRTAndODTFit(color);
 color=outMat*color;
 return clamp(color,0.0,1.0);
}

vec3 myLinearToSRGB(vec3 c){
 c=clamp(c,0.0,1.0);
 return mix(c*12.92,1.055*pow(c,vec3(1.0/2.4))-0.055,step(vec3(0.0031308),c));
}

float viewZ(vec2 uv){
 float z=texture2D(tDepth,uv).x;
 float ndc=z*2.0-1.0;
 return (2.0*uNear*uFar)/(uFar+uNear-ndc*(uFar-uNear));
}

void main(){
 vec2 cell=floor(vUv*uResolution);
 vec2 pUv=(cell+0.5)/uResolution;
 vec2 stepUv=1.0/uResolution;
 vec4 texel=texture2D(tDiffuse,pUv);
 if(texel.a<0.02){
  gl_FragColor=vec4(0.0);
  return;
 }
 vec3 col=texel.rgb;
 float dC=viewZ(pUv);
 float dL=viewZ(pUv-vec2(stepUv.x,0.0));
 float dR=viewZ(pUv+vec2(stepUv.x,0.0));
 float dU=viewZ(pUv+vec2(0.0,stepUv.y));
 float dD=viewZ(pUv-vec2(0.0,stepUv.y));
 float aL=texture2D(tDiffuse,pUv-vec2(stepUv.x,0.0)).a;
 float aR=texture2D(tDiffuse,pUv+vec2(stepUv.x,0.0)).a;
 float aU=texture2D(tDiffuse,pUv+vec2(0.0,stepUv.y)).a;
 float aD=texture2D(tDiffuse,pUv-vec2(0.0,stepUv.y)).a;

 // Outer silhouette where a foreground pixel borders empty background or a much deeper surface.
 float sil=step(0.08,max(max(texel.a-aL,texel.a-aR),max(texel.a-aU,texel.a-aD)));
 float maxJump=max(max(dL-dC,dR-dC),max(dU-dC,dD-dC));
 float jumpEdge=smoothstep(dC*0.045+0.09,dC*0.09+0.24,maxJump);
 float edge=max(sil*0.76,jumpEdge*0.54);

 // Concave crease & convex pixel highlight from depth laplacian.
 float lap=(dL+dR+dU+dD)-4.0*dC;
 float ridge=clamp(lap/(dC*0.08+0.12),0.0,1.0)*step(maxJump,dC*0.06+0.16);
 float crease=clamp(-lap/(dC*0.08+0.12),0.0,1.0);

 col*=1.0+ridge*0.11-crease*0.14;
 vec3 ink=mix(vec3(0.36,0.41,0.37),vec3(0.22,0.28,0.34),uNight);
 col=mix(col,col*ink,edge);

 vec3 mapped=myLinearToSRGB(myACESFilmic(col));
 vec4 outCol=vec4(mapped,texel.a);

 // 2x2 Bayer ordered dither + gentle 22-step pixel palette quantization.
 vec2 m=mod(cell,2.0);
 float bayer=(m.x<0.5?(m.y<0.5?0.0:2.0):(m.y<0.5?3.0:1.0))/4.0-0.375;
 float levels=22.0;
 outCol.rgb=clamp(floor(outCol.rgb*levels+0.5+bayer*0.24)/levels,0.0,1.0);
 gl_FragColor=outCol;
}`;

export function createPixelPass(renderer,camera,{pixelSize=3}={}){
 let enabled=false,width=320,height=200,target=null,quad=null,material=null,failed=false;
 function ensureTarget(cssW,cssH){
  const cellSize=cssW<550?Math.min(1.5,pixelSize):pixelSize;
  const w=Math.max(96,Math.round(cssW/cellSize)),h=Math.max(72,Math.round(cssH/cellSize));
  if(target&&w===width&&h===height)return;
  width=w;height=h;
  if(!target){
   const depthTexture=new DepthTexture(w,h);
   depthTexture.minFilter=NearestFilter;depthTexture.magFilter=NearestFilter;
   try{
    target=new WebGLRenderTarget(w,h,{type:HalfFloatType,minFilter:NearestFilter,magFilter:NearestFilter,generateMipmaps:false,depthBuffer:true,depthTexture});
   }catch{
    target=new WebGLRenderTarget(w,h,{minFilter:NearestFilter,magFilter:NearestFilter,generateMipmaps:false,depthBuffer:true,depthTexture});
   }
   material=new ShaderMaterial({
    uniforms:{
     tDiffuse:{value:target.texture},
     tDepth:{value:depthTexture},
     uResolution:{value:new Vector2(w,h)},
     uNear:{value:camera.near},
     uFar:{value:camera.far},
     uNight:{value:0},
     uExposure:{value:renderer.toneMappingExposure||1.08},
    },
    vertexShader:VERTEX_SHADER,
    fragmentShader:FRAGMENT_SHADER,
    toneMapped:false,
    depthTest:false,
    depthWrite:false,
   });
   quad=new FullScreenQuad(material);
  }else{
   target.setSize(w,h);
   if(target.depthTexture)target.depthTexture.image={width:w,height:h};
   material.uniforms.uResolution.value.set(w,h);
  }
 }
 return {
  get enabled(){return enabled&&!failed;},
  get resolution(){return [width,height];},
  setEnabled(value){enabled=!!value;},
  resize(cssW,cssH){if(cssW>0&&cssH>0&&target)ensureTarget(cssW,cssH);},
  render(scene,cssW,cssH,nightFactor=0){
   if(!enabled||failed)return false;
   try{
    ensureTarget(cssW,cssH);
    material.uniforms.uNear.value=camera.near;
    material.uniforms.uFar.value=camera.far;
    material.uniforms.uNight.value=nightFactor;
    material.uniforms.uExposure.value=renderer.toneMappingExposure||1.08;
    const prevAutoClear=renderer.autoClear;
    renderer.autoClear=true;
    renderer.setRenderTarget(target);
    renderer.clear(true,true,false);
    renderer.render(scene,camera);
    renderer.setRenderTarget(null);
    renderer.clear(true,true,false);
    quad.render(renderer);
    renderer.autoClear=prevAutoClear;
    return true;
   }catch{
    failed=true;
    renderer.setRenderTarget(null);
    return false;
   }
  },
  dispose(){
   quad?.dispose?.();
   material?.dispose?.();
   target?.depthTexture?.dispose?.();
   target?.dispose?.();
   quad=null;material=null;target=null;
  }
 };
}
