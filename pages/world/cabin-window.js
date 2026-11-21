/* Pixel valley mounted behind the window bars. The sky material still follows
 * the weather and the solar-arc controller moves the sun independently. */
export function addWindowLandscape(THREE, windowGroup, daySky, nightSky, skyColor, textures) {
  function picture(parent, name, width, height, worldWidth, worldHeight, depth, draw, tint) {
    const canvas=document.createElement('canvas');
    canvas.width=width; canvas.height=height;
    const ctx=canvas.getContext('2d');
    const rect=(x,y,w,h,color)=>{ctx.fillStyle=color; ctx.fillRect(x,y,w,h);};
    draw(rect);
    const map=new THREE.CanvasTexture(canvas);
    map.colorSpace=THREE.SRGBColorSpace;
    map.magFilter=map.minFilter=THREE.NearestFilter;
    map.generateMipmaps=false;
    textures.push(map);
    const material=new THREE.MeshBasicMaterial({map,alphaTest:.5});
    if (tint) material.color=tint;
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(worldWidth,worldHeight),material);
    mesh.name=name;
    mesh.position.z=depth;
    mesh.userData.keepSeparate=true;
    parent.add(mesh);
    return mesh;
  }

  picture(windowGroup,'Pine valley',56,42,1.96,1.49,.129,rect=>{
    const peaks=[22,20,17,16,18,20,17,15,13,10,12,15,18,19,16,15,18,20,18,16,15,17,20,22,21,19,18,20];
    for (let i=0;i<peaks.length;i++) {
      const y=peaks[i];
      rect(i*2,y,2,42-y,i>=9&&i<14?'#7399ac':'#94afae');
      if (y<=15) rect(i*2,y,2,i===9?3:1,'#eff0d2');
      const meadow=24+Math.round(2.3*Math.sin(i*.38));
      rect(i*2,meadow,2,42-meadow,'#82a684');
    }
    for (let y=28;y<42;y++) {
      const x=26+Math.round(4*Math.sin((y-28)*.48)), width=1+Math.floor((y-28)*.53);
      rect(x,y,width,1,'#aed4c1');
      if (y%3===0) rect(x,y,Math.max(1,width-2),1,'#d1dfc3');
    }
    for (const [x,y,s] of [[2,22,2],[9,26,1],[15,24,1],[38,24,1],[45,22,2],[51,26,1]]) {
      rect(x+2*s,y,1*s,3*s,'#395e69');
      rect(x+s,y+2*s,3*s,3*s,'#477469');
      rect(x,y+4*s,5*s,3*s,'#365e60');
      rect(x+2*s,y+7*s,s,2*s,'#735447');
    }
    rect(15,31,5,4,'#e2b57b');rect(14,30,7,2,'#8b544e');rect(16,29,3,1,'#a46a53');rect(17,33,1,2,'#594b4c');
  },skyColor);
  picture(daySky,'Fair-weather clouds',56,42,1.96,1.49,.115,rect=>{
    for (const [x,y] of [[5,8],[36,5],[43,10]]) {
      rect(x,y,8,2,'#e3ead9');rect(x+2,y-2,4,2,'#f6edd9');
    }
  },skyColor);
  const sun=picture(daySky,'Sun',9,9,.25,.25,.113,rect=>{
    rect(2,0,5,9,'#ffd88a');rect(0,2,9,5,'#ffd88a');rect(1,1,7,7,'#ffd88a');
    rect(2,1,3,2,'#ffedaa');
  });
  const moon=picture(nightSky,'Crescent',10,11,.29,.32,.115,rect=>{
    for (const [y,x,w] of [[0,4,3],[1,3,2],[2,2,2],[3,1,2],[4,1,2],[5,1,2],[6,1,3],[7,2,3],[8,3,5],[9,4,5],[10,6,2]]) {
      rect(x,y,w,1,'#f9e9b0');
    }
  });
  moon.position.x=.61; moon.position.y=.39;
  return sun;
}
