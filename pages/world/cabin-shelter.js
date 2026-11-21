/* Distance fog belongs outdoors. The cutaway exposes the room to the camera
 * without admitting weather through its missing walls. Includes instanced
 * furniture and characters loaded after the first frame. */
export const SHELTER = Object.freeze({
  halfWidth:5.55, back:-4.38, front:4.02, ridge:5.66, roofSlope:.38, edge:.24,
});
const varying = '\n#ifdef USE_FOG\nvarying vec3 vCottagePosition;\n#endif\n';
const vertex = `
#include <fog_vertex>
#ifdef USE_FOG
  vCottagePosition = transpose(mat3(viewMatrix)) * mvPosition.xyz + cameraPosition;
#endif`;
const fragment = `
#ifdef USE_FOG
  vec3 shelteredColor = gl_FragColor.rgb;
  float dx = abs(vCottagePosition.x) - ${SHELTER.halfWidth};
  float dz = max(${SHELTER.back} - vCottagePosition.z, vCottagePosition.z - ${SHELTER.front});
  float roof = ${SHELTER.ridge} - ${SHELTER.roofSlope} * abs(vCottagePosition.x);
  float exposure = smoothstep(0.0, ${SHELTER.edge}, max(max(dx,dz),vCottagePosition.y-roof));
  #include <fog_fragment>
  gl_FragColor.rgb = mix(shelteredColor, gl_FragColor.rgb, exposure);
#endif`;

export function installCabinFog(scene) {
  const objects=new WeakSet(),materials=new WeakSet();
  function patch(material) {
    if (!material?.fog || material.isShaderMaterial || materials.has(material)) return;
    materials.add(material);
    const previous=material.onBeforeCompile, originalKey=material.customProgramCacheKey();
    material.onBeforeCompile=function(shader,renderer) {
      previous.call(this,shader,renderer);
      shader.vertexShader=shader.vertexShader
        .replace('#include <fog_pars_vertex>','#include <fog_pars_vertex>'+varying)
        .replace('#include <fog_vertex>',vertex);
      shader.fragmentShader=shader.fragmentShader
        .replace('#include <fog_pars_fragment>','#include <fog_pars_fragment>'+varying)
        .replace('#include <fog_fragment>',fragment);
    };
    material.customProgramCacheKey=()=>originalKey+'-cottage-shelter';
    material.needsUpdate=true;
  }
  function childAdded(event) {attach(event.child);}
  function attach(object) {
    if (objects.has(object)) return;
    objects.add(object);
    if (Array.isArray(object.material)) object.material.forEach(patch);
    else patch(object.material);
    object.addEventListener('childadded',childAdded);
    object.children.forEach(attach);
  }
  attach(scene);
  return ()=>scene.traverse(object=>object.removeEventListener('childadded',childAdded));
}
