/* Client-side <50ms true-3D WebGL Polaroid card compositor. */

function cleanActivity(raw) {
  if (typeof raw !== 'string') return '';
  return raw.split('；环境参考')[0].trim();
}

function formatPolaroidStamp(epochSec, timezone) {
  const ms = Number.isFinite(epochSec) && epochSec > 0 ? epochSec * 1000 : Date.now();
  const date = new Date(ms);
  try {
    const parts = new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      ...(timezone ? {timeZone: timezone} : {}),
    }).formatToParts(date);
    const pick = t => parts.find(p => p.type === t)?.value || '';
    const y = pick('year'), mo = pick('month'), d = pick('day'), h = pick('hour'), mi = pick('minute');
    if (y && mo && d && h && mi) return `${y}-${mo}-${d} ${h}:${mi}`;
  } catch {}
  const pad = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('无法解码 3D 画面截图'));
    img.src = dataUrl;
  });
}

function truncateText(ctx, text, maxWidth) {
  const s = String(text || '').trim();
  if (!s || ctx.measureText(s).width <= maxWidth) return s;
  let out = s;
  while (out.length > 1 && ctx.measureText(out + '…').width > maxWidth) {
    out = out.slice(0, -1);
  }
  return out + '…';
}

export async function composeClientPolaroid(imageDataUrl, snapshot, diag = null, noteOverride = '') {
  if (!imageDataUrl || !imageDataUrl.startsWith('data:image/')) {
    throw new Error('3D 画布尚未就绪');
  }
  const img = await loadImage(imageDataUrl);
  const W = 800, H = 640;
  const photoX = 40, photoY = 36, photoW = 720, photoH = 460;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('浏览器不支持 2D Canvas 合成');

  // Warm Polaroid paper stock & subtle border
  ctx.fillStyle = '#faf5eb';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#ded2c0';
  ctx.lineWidth = 4;
  ctx.strokeRect(10, 10, W - 20, H - 20);

  // Inner photo mat
  ctx.fillStyle = '#e7dccb';
  ctx.fillRect(photoX - 3, photoY - 3, photoW + 6, photoH + 6);

  // Cover-fit WebGL capture into 720x460 without aspect distortion
  const srcW = Math.max(1, img.naturalWidth || img.width || photoW);
  const srcH = Math.max(1, img.naturalHeight || img.height || photoH);
  const scale = Math.max(photoW / srcW, photoH / srcH);
  const cropW = photoW / scale;
  const cropH = photoH / scale;
  const sx = (srcW - cropW) / 2;
  const sy = (srcH - cropH) / 2;

  ctx.save();
  ctx.beginPath();
  ctx.rect(photoX, photoY, photoW, photoH);
  ctx.clip();
  ctx.fillStyle = diag?.night ? '#192a22' : '#dfe7d7';
  ctx.fillRect(photoX, photoY, photoW, photoH);
  ctx.drawImage(img, sx, sy, cropW, cropH, photoX, photoY, photoW, photoH);

  // Gentle Polaroid lens vignette
  const vignette = ctx.createRadialGradient(
    photoX + photoW / 2, photoY + photoH / 2, photoH * 0.34,
    photoX + photoW / 2, photoY + photoH / 2, photoW * 0.62,
  );
  vignette.addColorStop(0, 'rgba(0,0,0,0)');
  vignette.addColorStop(1, 'rgba(20,28,22,0.16)');
  ctx.fillStyle = vignette;
  ctx.fillRect(photoX, photoY, photoW, photoH);
  ctx.restore();

  ctx.strokeStyle = '#d3c5b0';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(photoX, photoY, photoW, photoH);

  // Extract live world metadata
  const data = snapshot || {};
  const scene = data.scene || {};
  const env = data.environment || {};
  const cur = env.current || {};
  const eco = data.ecology || {};
  const charName = data.character?.name || '小屋主人';
  const placeLabel = [scene.place_name || data.actor?.place_name || '木屋花园', scene.room_name]
    .filter(Boolean)
    .join(' · ');
  const activeGuest = data.world_space?.active_guest?.name;
  const titleLine = activeGuest
    ? `${charName} 与 ${activeGuest} · ${placeLabel}`
    : `${charName} · ${placeLabel}`;

  const rawCaption =
    String(noteOverride || '').trim() ||
    scene.action?.label ||
    cleanActivity(data.replaySummary) ||
    cleanActivity(data.activity) ||
    cleanActivity(data.plan_now) ||
    '在小屋与院落间度过安静的一刻';

  const stamp = formatPolaroidStamp(data.server_time, env.timezone);
  const solar = eco.season?.solar_term || '';
  const wxLabel = cur.label || (diag?.atmosphere?.weather === 'rain' ? '雨' : diag?.atmosphere?.weather === 'snow' ? '雪' : '晴好');
  const tempText = cur.temperature != null ? ` ${cur.temperature}°C` : '';
  const mood = eco.vitality?.mood_label || '安宁';
  const metaLine = [
    stamp,
    [solar, `${wxLabel}${tempText}`].filter(Boolean).join(' · '),
    `心情 ${mood}`,
  ].join('  |  ');

  const fontStack = '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif';
  ctx.textBaseline = 'top';

  ctx.fillStyle = '#26382e';
  ctx.font = `600 22px ${fontStack}`;
  ctx.fillText(truncateText(ctx, titleLine, photoW - 140), photoX + 4, 514);

  // Right-side Polaroid badge
  ctx.save();
  ctx.font = `600 11px ui-monospace, SFMono-Regular, Consolas, monospace`;
  const badgeText = '3D LIVE · DW';
  const bw = ctx.measureText(badgeText).width + 18;
  const bx = photoX + photoW - bw;
  ctx.fillStyle = '#efe5d4';
  ctx.strokeStyle = '#d5c5ad';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.roundRect(bx, 515, bw, 24, 12);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = '#5c6f62';
  ctx.fillText(badgeText, bx + 9, 521);
  ctx.restore();

  ctx.fillStyle = '#4a5f53';
  ctx.font = `400 16px ${fontStack}`;
  ctx.fillText(truncateText(ctx, `「${rawCaption}」`, photoW - 8), photoX + 4, 550);

  ctx.fillStyle = '#75867b';
  ctx.font = `400 13px ui-monospace, SFMono-Regular, Menlo, ${fontStack}`;
  ctx.fillText(truncateText(ctx, metaLine, photoW - 8), photoX + 4, 585);

  return canvas.toDataURL('image/png');
}
