function hourToTimeMode(hour) {
 const h = Number(hour);
 if (!Number.isFinite(h)) return 'auto';
 if (h < 5.5 || h >= 19.5) return 'night';
 if (h < 7.2) return 'dawn';
 if (h >= 17.2) return 'dusk';
 return 'day';
}

const LEGACY_CURTAIN_BY_LABEL = {'窗帘打开': 'open', '窗帘半掩': 'half', '窗帘合拢': 'closed'};
const LEGACY_LIGHT_BY_LABEL = {'明亮室内灯光': 'bright', '柔和暖光': 'warm', '昏暗小灯': 'dim', '室内灯已关闭': 'off'};

function normalizeWeatherEffect(w) {
 const s = String(w || 'clear').toLowerCase();
 if (s.includes('rain') || s.includes('storm') || s.includes('drizzle') || s.includes('shower')) return 'rain';
 if (s.includes('snow') || s.includes('sleet')) return 'snow';
 if (s.includes('fog') || s.includes('mist') || s.includes('haze')) return 'fog';
 if (s.includes('cloud') || s.includes('overcast')) return 'cloud';
 return 'clear';
}

export {hourToTimeMode, normalizeWeatherEffect};

export function createCabinTimeline(stageEl, {onPreviewChange, onOpenChange} = {}) {
 const bar = document.createElement('section');
 bar.className = 'cabin-timeline-bar';
 bar.hidden = true;
 bar.setAttribute('aria-label', '过去 24 小时足迹回放');
 for (const evtName of ['pointerdown', 'pointermove', 'wheel', 'click', 'dblclick']) {
  bar.addEventListener(evtName, (e) => e.stopPropagation());
 }

 const topRow = document.createElement('div');
 topRow.className = 'timeline-top';

 const badge = document.createElement('span');
 badge.className = 'timeline-badge';
 badge.textContent = '24h 足迹监控回放';

 const timeReadout = document.createElement('strong');
 timeReadout.className = 'timeline-clock';
 timeReadout.textContent = '实时监控';

 const playBtn = document.createElement('button');
 playBtn.type = 'button';
 playBtn.className = 'ghost small timeline-play-btn';
 playBtn.textContent = '▶ 播放回放';

 const liveBtn = document.createElement('button');
 liveBtn.type = 'button';
 liveBtn.className = 'ghost small timeline-live-btn';
 liveBtn.textContent = '回到实时监控';

 const closeBtn = document.createElement('button');
 closeBtn.type = 'button';
 closeBtn.className = 'ghost small timeline-close-btn';
 closeBtn.textContent = '收起';

 topRow.append(badge, timeReadout, playBtn, liveBtn, closeBtn);

 const sliderRow = document.createElement('div');
 sliderRow.className = 'timeline-slider-row';

 const range = document.createElement('input');
 range.type = 'range';
 range.className = 'timeline-range';
 range.min = '0';
 range.max = '0';
 range.step = '1';
 range.value = '0';
 range.setAttribute('aria-label', '拖动回放过去 24 小时关键帧');
 sliderRow.append(range);

 const summaryEl = document.createElement('div');
 summaryEl.className = 'timeline-summary';
 summaryEl.textContent = '拖动滑块或点击播放回放，重现过去 24 小时的天光、布置、站位与生活片段。';

 bar.append(topRow, sliderRow, summaryEl);
 stageEl.append(bar);

 let open = false;
 let keyframes = [];
 let previewing = false;
 let playTimer = 0;

 function syncPlayButton() {
  const playing = Boolean(playTimer);
  playBtn.dataset.playing = String(playing);
  playBtn.textContent = playing ? '⏸ 暂停回放' : '▶ 播放回放';
  playBtn.disabled = keyframes.length <= 1;
 }

 function stopPlayback() {
  if (playTimer) {
   clearInterval(playTimer);
   playTimer = 0;
  }
  syncPlayButton();
 }

 function buildStops(rawList) {
  const list = Array.isArray(rawList) ? rawList.slice(-72) : [];
  let carry = null;
  const stops = list.map((kf) => {
   const isLegacyArrange = kf && kf.kind === 'admin_arrange' && !Array.isArray(kf.furniture);
   let merged = {...kf};
   if (isLegacyArrange && carry) {
    merged = {
     ...merged,
     weather: carry.weather || merged.weather,
     weather_label: carry.weather_label || merged.weather_label,
     temperature: carry.temperature ?? merged.temperature,
     curtains: carry.curtains || merged.curtains,
     lighting: carry.lighting || merged.lighting,
     location: carry.location || merged.location,
     place_name: carry.place_name || merged.place_name,
     pose: carry.pose || merged.pose,
     cat_spot: carry.cat_spot || merged.cat_spot,
     outfit_now: carry.outfit_now || merged.outfit_now,
    };
    const m = typeof merged.summary === 'string' && merged.summary.match(/^布置了小屋：(.+?)\s*→\s*(.+)$/);
    if (m) {
     const afterLabel = m[2].trim();
     if (LEGACY_CURTAIN_BY_LABEL[afterLabel]) merged.curtains = LEGACY_CURTAIN_BY_LABEL[afterLabel];
     else if (LEGACY_LIGHT_BY_LABEL[afterLabel]) merged.lighting = LEGACY_LIGHT_BY_LABEL[afterLabel];
    }
   }
   const stop = {
    ...merged,
    isLive: false,
    timeMode: hourToTimeMode(merged.hour),
    weatherEffect: normalizeWeatherEffect(merged.weather),
   };
   carry = stop;
   return stop;
  });
  stops.push({
   id: '__live__',
   isLive: true,
   clock_label: '实时此刻',
   summary: '正在同步当前小屋实时监控画面',
  });
  return stops;
 }

 function applyIndex(idx, notify = true) {
  if (!keyframes.length) return;
  const clamped = Math.max(0, Math.min(keyframes.length - 1, idx));
  range.value = String(clamped);
  const stop = keyframes[clamped];
  const historyFrames = keyframes.slice(0, -1);
  if (!stop || stop.isLive) {
   stopPlayback();
   const wasPreview = previewing;
   previewing = false;
   bar.dataset.preview = 'false';
   liveBtn.disabled = true;
   timeReadout.textContent = keyframes.length > 1 ? `实时此刻（共 ${keyframes.length - 1} 帧记录）` : '实时此刻';
   summaryEl.textContent = keyframes.length > 1
    ? '向左拖动滑块或点击「▶ 播放回放」，重现过去 24 小时的天光、布置与角色轨迹。'
    : '已开启 24h 足迹记录，随着角色作息与房间变化将自动累积回放关键帧。';
   if (notify && wasPreview && typeof onPreviewChange === 'function') {
    onPreviewChange({active: false, keyframe: null, index: clamped, keyframes: historyFrames});
   }
   return;
  }
  previewing = true;
  bar.dataset.preview = 'true';
  liveBtn.disabled = false;
  const tempTxt = stop.temperature !== undefined && stop.temperature !== null ? ` ${Math.round(Number(stop.temperature))}°C` : '';
  const wxTxt = stop.weather_label ? ` · ${stop.weather_label}${tempTxt}` : '';
  const placeTxt = stop.place_name ? ` · ${stop.place_name}` : '';
  const frameTag = historyFrames.length > 0 ? ` [${clamped + 1}/${historyFrames.length}]` : '';
  timeReadout.textContent = `${stop.clock_label || '历史时刻'}${wxTxt}${placeTxt}${frameTag}`;
  summaryEl.textContent = stop.summary || '安静度过的一段日常时光。';
  if (notify && typeof onPreviewChange === 'function') {
   onPreviewChange({active: true, keyframe: stop, index: clamped, keyframes: historyFrames});
  }
 }

 function startPlayback() {
  if (keyframes.length <= 1) return;
  stopPlayback();
  const cur = Number(range.value) || 0;
  const startIdx = cur >= keyframes.length - 2 ? 0 : cur;
  applyIndex(startIdx, true);
  playTimer = setInterval(() => {
   const nextIdx = (Number(range.value) || 0) + 1;
   if (nextIdx >= keyframes.length - 1) {
    stopPlayback();
    applyIndex(keyframes.length - 1, true);
   } else {
    applyIndex(nextIdx, true);
   }
  }, 1150);
  syncPlayButton();
 }

 playBtn.addEventListener('click', () => {
  if (playTimer) stopPlayback();
  else startPlayback();
 });

 for (const evtName of ['input', 'change']) {
  range.addEventListener(evtName, () => {
   stopPlayback();
   const nextIdx = Number(range.value) || 0;
   applyIndex(nextIdx, true);
  });
 }

 liveBtn.addEventListener('click', () => {
  stopPlayback();
  applyIndex(keyframes.length - 1, true);
 });

 closeBtn.addEventListener('click', () => {
  setOpen(false);
 });

 function setOpen(next) {
  open = Boolean(next);
  bar.hidden = !open;
  if (!open) {
   stopPlayback();
   if (previewing) applyIndex(keyframes.length - 1, true);
  } else {
   syncPlayButton();
   applyIndex(previewing ? Number(range.value) || 0 : keyframes.length - 1, false);
  }
  if (typeof onOpenChange === 'function') onOpenChange(open);
 }

 return {
  setKeyframes(rawList) {
   const prevId = previewing ? keyframes[Number(range.value) || 0]?.id : '__live__';
   keyframes = buildStops(rawList);
   range.max = String(Math.max(0, keyframes.length - 1));
   range.disabled = keyframes.length <= 1;
   syncPlayButton();
   if (!previewing || prevId === '__live__') {
    applyIndex(keyframes.length - 1, false);
   } else {
    const found = keyframes.findIndex((item) => item.id === prevId);
    applyIndex(found >= 0 ? found : keyframes.length - 1, found < 0);
   }
  },
  scrubTo(index) {
   stopPlayback();
   applyIndex(index, true);
  },
  toggle() {
   setOpen(!open);
   return open;
  },
  setOpen,
  isOpen() {
   return open;
  },
  isPreviewing() {
   return previewing;
  },
  exitPreview() {
   stopPlayback();
   if (previewing) applyIndex(keyframes.length - 1, true);
  },
  dispose() {
   stopPlayback();
   bar.remove();
  },
 };
}
