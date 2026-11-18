// A shallow, layered landscape between the rear of the sash and its glazing.
export function addWindowLandscape(THREE, windowGroup, daySky, nightSky, skyColor) {
  const positions = [], colors = [];
  const paint = new THREE.Color();
  function triangle(a, b, c, tint) {
    positions.push(...a, ...b, ...c);
    paint.setHex(tint);
    for (let i = 0; i < 3; i++) colors.push(paint.r, paint.g, paint.b);
  }
  function mount(parent, name, tint) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const material = new THREE.MeshBasicMaterial({vertexColors: true});
    if (tint) material.color = tint;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = name;
    parent.add(mesh);
    positions.length = colors.length = 0;
    return mesh;
  }
  function ridge(points, z, color) {
    for (let i = 1; i < points.length; i++) {
      const [x0, y0] = points[i - 1], [x1, y1] = points[i];
      triangle([x0,-.745,z], [x1,-.745,z], [x1,y1,z], color);
      triangle([x0,-.745,z], [x1,y1,z], [x0,y0,z], color);
    }
  }
  ridge([[-.98,-.17],[-.76,-.02],[-.60,-.09],[-.31,.13],[-.12,.025],[.15,.23],[.39,.09],[.59,.14],[.98,-.08]], .117, 0x91aeb6);
  triangle([.15,.23,.118], [-.12,.025,.118], [.05,.05,.118], 0xb6c8c6);
  triangle([-.31,.13,.118], [-.60,-.09,.118], [-.38,-.04,.118], 0xb6c8c6);
  ridge([[-.98,-.25],[-.71,-.13],[-.46,-.18],[-.18,-.26],[.12,-.20],[.43,-.04],[.62,-.11],[.98,-.02]], .122, 0x769b91);
  ridge([[-.98,-.37],[-.70,-.30],[-.45,-.35],[-.19,-.44],[.13,-.42],[.52,-.32],[.98,-.37]], .126, 0x8ba87b);
  // A stream winds out of the valley into the foreground.
  const banks = [[-.11,-.42,.014],[-.26,-.49,.031],[-.14,-.56,.053],[.09,-.64,.074],[.03,-.745,.12]];
  for (let i = 1; i < banks.length; i++) {
    const [ax,ay,aw] = banks[i - 1], [bx,by,bw] = banks[i], z = .128;
    triangle([ax-aw,ay,z], [bx-bw,by,z], [bx+bw,by,z], 0xa5c8c6);
    triangle([ax-aw,ay,z], [bx+bw,by,z], [ax+aw,ay,z], 0xa5c8c6);
  }
  for (const [x, y, h] of [[-.87,-.62,.51],[-.72,-.58,.33],[-.57,-.53,.23],[.36,-.55,.21],[.50,-.57,.33],[.72,-.66,.55],[.89,-.61,.39]]) {
    for (let i = 0; i < 3; i++) {
      const base = y + i*h*.22, top = base + h*(.56-i*.04), w = h*(.27-i*.06);
      triangle([x-w,base,.134], [x,base,.134], [x,top,.134], 0x466e65);
      triangle([x,base,.134], [x+w,base,.134], [x,top,.134], 0x628677);
    }
  }
  mount(windowGroup, 'Mountain valley and pines', skyColor);

  function ellipse(cx, cy, rx, ry, z, color) {
    for (let i = 0; i < 24; i++) {
      const a = i * Math.PI / 12, b = (i + 1) * Math.PI / 12;
      triangle([cx,cy,z], [cx+rx*Math.cos(a),cy+ry*Math.sin(a),z], [cx+rx*Math.cos(b),cy+ry*Math.sin(b),z], color);
    }
  }
  const z = .114;
  for (const [x, y, s] of [[-.61,.38,1],[.46,.52,.74]]) {
    ellipse(x,y,.23*s,.040*s,z,0xe3e9df);
    ellipse(x-.04*s,y+.034*s,.09*s,.057*s,z+.0005,0xeef0e5);
    ellipse(x+.065*s,y+.016*s,.086*s,.042*s,z+.0005,0xeef0e5);
  }
  mount(daySky, 'High clouds', skyColor);
  ellipse(0,0,.125,.125,.110,0xffce8a);
  const sun = mount(daySky, 'Sun');
  sun.userData.keepSeparate = true;

  // A crescent with open sky showing through the curved inner edge.
  for (let i = 0; i < 18; i++) {
    const edge = n => {
      const a = Math.PI * n / 18, bulge = Math.sin(a);
      const y = .39 + .15 * Math.cos(a), x = .61 - .16 * bulge;
      return [[x,y,z],[x+.082*bulge,y,z]];
    };
    const [a,b] = edge(i), [c,d] = edge(i+1);
    triangle(a,c,d,0xf2e9c8);
    triangle(a,d,b,0xf2e9c8);
  }
  mount(nightSky, 'Crescent moon');
  return sun;
}
