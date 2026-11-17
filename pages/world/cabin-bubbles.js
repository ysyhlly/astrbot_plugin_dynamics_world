import {projectJourneyRadar} from './avatar-state.js';

function clipText(value, maxLen = 36) {
 const raw = String(value || '').replace(/\s+/g, ' ').trim();
 if (!raw) return '';
 return raw.length > maxLen ? `${raw.slice(0, maxLen - 1)}…` : raw;
}

function pickBubblePayload(snapshot, actorDiag) {
 if (!snapshot) return null;
 if (snapshot.isReplay) {
  const txt = clipText(snapshot.replaySummary || snapshot.plan_now || snapshot.mood_now || '回放此刻足迹', 38);
  return {icon: '🕰️', text: txt, target: 'stories', tone: 'replay'};
 }
 const action = snapshot?.scene?.action;
 if (action?.active && action?.label) {
  return {icon: '✨', text: clipText(action.label, 34), target: 'life', tone: 'action'};
 }
 const visit = snapshot?.world_space?.active_guest || snapshot?.world_space?.active_visit;
 if (visit && (visit.name || visit.guest_name || visit.peer_name || visit.activity || visit.summary)) {
  const peer = visit.name || visit.guest_name || visit.peer_name || '邻屋伙伴';
  return {icon: '🍵', text: clipText(visit.activity || visit.summary || `正与 ${peer} 在院里叙话`, 34), target: 'stories', tone: 'visit'};
 }
 const unopened = Number(snapshot?.mailbox?.unopened_count) || 0;
 if (unopened > 0) {
  return {icon: '📬', text: `拱门信箱收到 ${unopened} 封新来信`, target: 'inspect:mailbox', tone: 'mail'};
 }
 const micro = actorDiag?.micro;
 if (micro?.thought || micro?.label) {
  return {icon: '💭', text: clipText(micro.thought || micro.label, 34), target: 'life', tone: 'micro'};
 }
 const vit = snapshot?.ecology?.vitality;
 const plan = clipText(snapshot?.plan_now || '', 30);
 const mood = clipText(snapshot?.mood_now || vit?.mood_label || '', 16);
 if (plan) return {icon: '🌿', text: mood ? `${mood} · ${plan}` : plan, target: 'life', tone: 'calm'};
 if (mood) return {icon: '🌿', text: mood, target: 'life', tone: 'calm'};
 return null;
}

export function createCabinBubbles(stageEl, {onBubbleSelect} = {}) {
 const bubbleBtn = document.createElement('button');
 bubbleBtn.type = 'button';
 bubbleBtn.className = 'cabin-thought-bubble';
 bubbleBtn.hidden = true;

 const iconSpan = document.createElement('span');
 iconSpan.className = 'cabin-thought-icon';
 const textSpan = document.createElement('span');
 textSpan.className = 'cabin-thought-text';
 bubbleBtn.append(iconSpan, textSpan);

 const radarEl = document.createElement('aside');
 radarEl.className = 'cabin-away-radar';
 radarEl.hidden = true;
 radarEl.setAttribute('aria-live', 'polite');

 const radarBadge = document.createElement('div');
 radarBadge.className = 'away-radar-badge';
 radarBadge.textContent = '家中监控 · 外出途中';

 const radarRoute = document.createElement('div');
 radarRoute.className = 'away-radar-route';

 const radarTrack = document.createElement('div');
 radarTrack.className = 'away-radar-track';
 const radarFill = document.createElement('div');
 radarFill.className = 'away-radar-fill';
 radarTrack.append(radarFill);

 const radarMeta = document.createElement('div');
 radarMeta.className = 'away-radar-meta';
 radarEl.append(radarBadge, radarRoute, radarTrack, radarMeta);

 stageEl.append(bubbleBtn, radarEl);

 let lastSnapshot = null;
 let currentTarget = 'life';
 let forceHidden = false;

 bubbleBtn.addEventListener('click', (event) => {
  event.stopPropagation();
  if (typeof onBubbleSelect === 'function') onBubbleSelect(currentTarget, lastSnapshot);
 });

 function syncPosition(room3d) {
  if (forceHidden || !room3d || !lastSnapshot) {
   bubbleBtn.hidden = true;
   return;
  }
  const actorDiag = room3d.actorDiagnostics?.() || null;
  const proj = actorDiag?.projection;
  const away = proj?.location === 'away' || (!proj?.visible && Boolean(lastSnapshot?.journey?.in_transit));
  if (away) {
   bubbleBtn.hidden = true;
   return;
  }
  const inspectOpen = stageEl.querySelector('.cabin-inspect-card:not([hidden]), .cabin-inspect:not([hidden])');
  if (inspectOpen) {
   bubbleBtn.hidden = true;
   return;
  }
  const head = room3d.projectActorHead?.();
  if (!head || !head.visible) {
   bubbleBtn.hidden = true;
   return;
  }
  const w = stageEl.clientWidth || 0;
  const h = stageEl.clientHeight || 0;
  if (w < 160 || h < 160) {
   bubbleBtn.hidden = true;
   return;
  }
  const payload = pickBubblePayload(lastSnapshot, actorDiag);
  if (!payload) {
   bubbleBtn.hidden = true;
   return;
  }
  currentTarget = payload.target;
  bubbleBtn.dataset.tone = payload.tone;
  iconSpan.textContent = payload.icon;
  textSpan.textContent = payload.text;

  const padX = Math.min(110, Math.max(64, w * 0.14));
  const x = Math.max(padX, Math.min(w - padX, head.x));
  const y = Math.max(66, Math.min(h - 118, head.y - 10));
  bubbleBtn.style.left = `${Math.round(x)}px`;
  bubbleBtn.style.top = `${Math.round(y)}px`;
  bubbleBtn.hidden = false;
 }

 function update(snapshot, room3d) {
  lastSnapshot = snapshot || null;
  if (!lastSnapshot || forceHidden) {
   bubbleBtn.hidden = true;
   radarEl.hidden = true;
   return;
  }
  const actorDiag = room3d?.actorDiagnostics?.() || null;
  const proj = actorDiag?.projection;
  const isTravelling = lastSnapshot?.scene?.phase === 'travelling' || lastSnapshot?.actor?.phase === 'travelling';
  const homeIds=new Set((lastSnapshot?.scene?.rooms||[]).map(r=>r.place_id).filter(Boolean));
  const placeId=lastSnapshot?.scene?.place_id||lastSnapshot?.actor?.place_id;
  const isAway = isTravelling || Boolean(placeId&&homeIds.size&&!homeIds.has(placeId));
  if (isAway) {
   radarBadge.textContent=isTravelling?'家中监控 · 外出途中':'家中监控 · 在外停留';
   const radar = proj?.journeyRadar || projectJourneyRadar(lastSnapshot, Date.now());
   const origin = radar?.origin || lastSnapshot?.scene?.location_label || '小屋';
   const dest = radar?.destination || lastSnapshot?.journey?.destination || '外地';
   const pct = Math.max(4, Math.min(100, Math.round((Number(radar?.progress) || 0.35) * 100)));
   radarRoute.textContent = `${origin} → ${dest}`;
   radarFill.style.width = `${pct}%`;
   const eta = radar?.etaLabel || '归期未定';
   radarMeta.textContent = eta;
   radarEl.hidden = false;
   bubbleBtn.hidden = true;
   return;
  }
  radarEl.hidden = true;
  syncPosition(room3d);
 }

 return {
  update,
  syncPosition,
  setHidden(flag) {
   forceHidden = Boolean(flag);
   if (forceHidden) {
    bubbleBtn.hidden = true;
    radarEl.hidden = true;
   }
  },
  dispose() {
   bubbleBtn.remove();
   radarEl.remove();
  },
 };
}
