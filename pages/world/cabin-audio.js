// Procedural zero-asset WebAudio ambient soundscape (muted by default; ~3.5 KB).
export function createCabinAudio() {
 let ctx = null;
 let master = null;
 let breezeGain = null;
 let rainGain = null;
 let kettleGain = null;
 let enabled = false;
 let chirpTimer = 0;
 let state = {weather: 'clear', night: false, cooking: false};

 function buildNoiseBuffer(audioCtx) {
  const length = audioCtx.sampleRate * 2;
  const buffer = audioCtx.createBuffer(1, length, audioCtx.sampleRate);
  const out = buffer.getChannelData(0);
  let b0 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < length; i++) {
   const white = Math.random() * 2 - 1;
   b0 = 0.99765 * b0 + white * 0.099046;
   b1 = 0.96300 * b1 + white * 0.2965164;
   b2 = 0.57000 * b2 + white * 1.0526913;
   out[i] = (b0 + b1 + b2 + white * 0.1848) * 0.08;
  }
  return buffer;
 }

 function ensureGraph() {
  if (ctx) return true;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return false;
  ctx = new AudioCtx();
  master = ctx.createGain();
  master.gain.value = 0.0001;
  master.connect(ctx.destination);

  const noiseBuf = buildNoiseBuffer(ctx);

  const makeLoop = (type, freq, q) => {
   const src = ctx.createBufferSource();
   src.buffer = noiseBuf;
   src.loop = true;
   const filter = ctx.createBiquadFilter();
   filter.type = type;
   filter.frequency.value = freq;
   filter.Q.value = q;
   const gain = ctx.createGain();
   gain.gain.value = 0.0001;
   src.connect(filter);
   filter.connect(gain);
   gain.connect(master);
   src.start();
   return gain;
  };

  breezeGain = makeLoop('lowpass', 360, 0.7);
  rainGain = makeLoop('bandpass', 1240, 0.85);
  kettleGain = makeLoop('lowpass', 195, 1.1);
  return true;
 }

 function syncLevels() {
  if (!ctx || !master) return;
  const now = ctx.currentTime;
  if (!enabled) {
   master.gain.setTargetAtTime(0.0001, now, 0.18);
   return;
  }
  master.gain.setTargetAtTime(0.65, now, 0.28);
  const isRain = state.weather === 'rain';
  const isSnow = state.weather === 'snow';
  breezeGain.gain.setTargetAtTime(isSnow ? 0.032 : 0.022, now, 0.4);
  rainGain.gain.setTargetAtTime(isRain ? 0.075 : 0.0001, now, 0.45);
  kettleGain.gain.setTargetAtTime(state.cooking ? 0.038 : 0.0001, now, 0.4);
 }

 function scheduleChirp() {
  clearTimeout(chirpTimer);
  if (!enabled || !ctx) return;
  const delay = 3200 + Math.random() * 4200;
  chirpTimer = window.setTimeout(() => {
   if (!enabled || !ctx || ctx.state !== 'running') return;
   if (state.night && state.weather !== 'rain' && state.weather !== 'snow') {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = 'sine';
    const baseFreq = 2650 + Math.random() * 420;
    osc.frequency.setValueAtTime(baseFreq, now);
    osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.08, now + 0.06);
    g.gain.setValueAtTime(0.0001, now);
    g.gain.linearRampToValueAtTime(0.012, now + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.11);
    osc.connect(g);
    g.connect(master);
    osc.start(now);
    osc.stop(now + 0.13);
   }
   scheduleChirp();
  }, delay);
 }

 return {
  toggle() {
   if (!enabled) {
    if (!ensureGraph()) return false;
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    enabled = true;
    syncLevels();
    scheduleChirp();
   } else {
    enabled = false;
    clearTimeout(chirpTimer);
    syncLevels();
   }
   return enabled;
  },
  isEnabled() {
   return enabled;
  },
  setState(next = {}) {
   state = {...state, ...next};
   if (enabled) syncLevels();
  },
  playTap(kind = 'wood') {
   if (!enabled || !ctx || ctx.state !== 'running') return;
   const now = ctx.currentTime;
   const osc = ctx.createOscillator();
   const g = ctx.createGain();
   osc.type = kind === 'paper' ? 'triangle' : 'sine';
   osc.frequency.setValueAtTime(kind === 'paper' ? 680 : 420, now);
   osc.frequency.exponentialRampToValueAtTime(kind === 'paper' ? 310 : 185, now + 0.045);
   g.gain.setValueAtTime(0.025, now);
   g.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
   osc.connect(g);
   g.connect(master);
   osc.start(now);
   osc.stop(now + 0.055);
  },
  dispose() {
   enabled = false;
   clearTimeout(chirpTimer);
   if (ctx) {
    ctx.close().catch(() => {});
    ctx = null;
   }
  },
 };
}
