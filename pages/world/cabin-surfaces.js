// Hand-painted texels for the cottage. All marks land on the texture grid.
const PALETTE = {
  ink: '#293641', teal: '#2c5e62', jade: '#4a8782', celadon: '#8eb6a4',
  cream: '#ffe4b3', gold: '#dfaa60', ochre: '#bc7846',
  rust: '#a84c45', rose: '#d9775c', plum: '#733f46',
};

function stamp(ctx, x, y, pattern, colors, scale = 1) {
  pattern.forEach((row, j) => {
    for (let i = 0; i < row.length; i++) {
      const color = colors[row[i]];
      if (color) {
        ctx.fillStyle = color;
        ctx.fillRect(x + i * scale, y + j * scale, scale, scale);
      }
    }
  });
}

const STAR = [
  '...a.a...', 'a..aaa..a', '.aaabaaa.', '..abbba..',
  '.abbbbba.', '..abbba..', '.aaabaaa.', 'a..aaa..a', '...a.a...',
];
const TULIP = ['p...p', 'pp.pp', '.ppp.', '.pqp.', '..s..', '..s.l', 'l.ssl', '.lsl.', '..s..'];

function textile(ctx, kind) {
  const {cream, gold, rust, rose, plum, teal, jade, celadon, ink} = PALETTE;
  const rug = kind === 'rug';
  const base = rug ? teal : rust;
  const rect = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };
  rect(0, 0, 64, 48, rug ? ink : plum);
  rect(1, 1, 62, 46, rug ? gold : cream);
  rect(2, 2, 60, 44, base);
  if (rug) {
    for (const y of [4, 37]) {
      rect(4, y, 56, 7, jade);
      for (let x = 4; x < 60; x += 7) {
        stamp(ctx, x + 1, y + 1, ['..a..', '.aaa.', 'aabaa', '.aaa.', '..a..'], {a: celadon, b: gold});
      }
    }
    for (const [cx, radius, color] of [[14, 7, jade], [32, 12, gold], [50, 7, jade]]) {
      for (let dy = -radius; dy <= radius; dy++) {
        const dx = radius - Math.abs(dy);
        rect(cx - dx, 24 + dy, dx * 2 + 1, 1, color);
      }
      stamp(ctx, cx - 4, 20, STAR, {a: cx === 32 ? plum : cream, b: cx === 32 ? cream : rose});
    }
  } else {
    for (let row = 0; row < 3; row++) for (let col = 0; col < 4; col++) {
      const x = 4 + 14 * col, y = 3 + 14 * row, light = (col + row) % 2 === 0;
      rect(x, y, 14, 14, light ? cream : teal);
      rect(x, y, 14, 1, light ? gold : jade);
      rect(x, y, 1, 14, light ? gold : jade);
      stamp(ctx, x + 3, y + 3, STAR, {a: light ? rust : celadon, b: light ? rose : cream});
    }
  }
  for (let x = 4; x < 61; x += 4) for (const y of [1, 46]) rect(x, y, 2, 1, cream);
}

function almanac(ctx) {
  const rect = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };
  rect(0, 0, 48, 48, '#e6b878');
  rect(2, 2, 44, 44, '#283c52');
  rect(4, 4, 40, 40, '#548a92');
  rect(4, 17, 40, 10, '#90b4a6');
  rect(4, 25, 40, 10, '#d8be90');
  stamp(ctx, 25, 6, ['..aaa..','.aaaaa.','aaaaaaa','aaaaaaa','aaaaaaa','.aaaaa.','..aaa..'], {a:'#ffe3a0'});
  const peaks = [20,22,23,21,18,16,14,17,20,22,19,17,20,21,23,25,22,18,17,19];
  peaks.forEach((y, i) => rect(4 + i * 2, y, 2, 18, i < 7 || i > 15 ? '#637f84' : '#768d86'));
  for (let i = 0; i < 20; i++) {
    const y = 26 + Math.round(Math.sin(i * .38) * 3);
    rect(4 + i * 2, y, 2, 44 - y, '#326b70');
  }
  for (let y = 31; y < 44; y++) {
    const x = 21 + Math.round(4 * Math.sin((y - 31) * .55));
    rect(x, y, 2 + Math.floor((y - 31) * .46), 1, '#abc4a6');
  }
  for (const [x, y, scale] of [[6,22,2],[33,25,1],[37,29,1],[13,21,1]]) {
    stamp(ctx, x, y, ['..a..','..a..','.aaa.','aaaaa','.aaa.','aaaaa','..b..'], {a:'#264b50',b:'#845c4c'}, scale);
  }
  rect(2, 44, 44, 2, '#d6a563');
}

function paintedPanel(ctx) {
  const p = PALETTE;
  ctx.fillStyle = p.teal; ctx.fillRect(0, 0, 24, 36);
  for (const [x, y, w, h] of [[2,2,20,1],[2,33,20,1],[1,3,1,30],[22,3,1,30]]) {
    ctx.fillStyle = p.jade; ctx.fillRect(x, y, w, h);
  }
  stamp(ctx, 9, 5, TULIP, {p:p.rose, q:p.gold, s:p.gold, l:p.celadon});
  ctx.fillStyle=p.gold; ctx.fillRect(11,14,1,11);
  stamp(ctx, 4, 15, ['a..','.aa','..a','...a','....a','.....a','......a'], {a:p.celadon});
  stamp(ctx, 13, 14, ['.....a','....aa','...aa','..a','.a','a'], {a:p.celadon});
  stamp(ctx, 6, 24, ['..gggggg..','...cccc...','..cccccc..','..ccggcc..','...cccc...','....gg....'], {g:p.gold,c:p.cream});
  for (const [x,y] of [[5,8],[17,9],[4,26],[18,25]]) {ctx.fillStyle=p.gold;ctx.fillRect(x,y,1,2);}
}

export function surfaceCanvas(kind) {
  const sizes = {quilt:[64,48], rug:[64,48], almanac:[48,48], cabinet:[24,36], wood:[48,16]};
  const [w, h] = sizes[kind] || [32,32];
  const canvas = document.createElement('canvas');
  canvas.width=w; canvas.height=h;
  const ctx=canvas.getContext('2d');
  ctx.imageSmoothingEnabled=false;
  ctx.fillStyle='#fff'; ctx.fillRect(0,0,w,h);
  if (kind === 'quilt' || kind === 'rug') textile(ctx, kind);
  else if (kind === 'almanac') almanac(ctx);
  else if (kind === 'cabinet') paintedPanel(ctx);
  else if (kind === 'wood') {
    for (const [x,y,width] of [[0,2,11],[12,3,7],[25,2,16],[34,6,14],[2,7,15],[8,12,16],[30,11,8],[40,13,8]]) {
      ctx.fillStyle='#e4d9cd'; ctx.fillRect(x,y,width,1);
    }
    stamp(ctx, 19, 6, ['.aaaaaa.','aabbbaaa','..aaaa..'], {a:'#e1d3c2',b:'#c5b8a8'});
  } else {
    const cloth = kind === 'fabric';
    for (let i=0;i<52;i++) {
      const x=(i*13 + Math.floor(i/6)*3)%32, y=(i*17+Math.floor(i/7)*5)%32;
      ctx.fillStyle=cloth ? '#eee4d4' : '#ebdfcf';
      ctx.fillRect(x,y,cloth ? 1 : 2+(i%4),1);
    }
  }
  return canvas;
}

