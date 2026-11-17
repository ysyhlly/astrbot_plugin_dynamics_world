/* Unified SSE delta stream + visibility-aware fallback store for 3D cabin & world map. */

const REQUEST_TIMEOUT_MS = 12000;

function unwrapPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    throw new Error('空响应');
  }
  if (payload.status === 'error' || payload.ok === false) {
    throw new Error(payload.error || payload.message || '请求失败');
  }
  return payload.data !== undefined ? payload.data : payload;
}

function withTimeout(promise, ms = REQUEST_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('请求超时')), ms);
    Promise.resolve(promise).then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

export function formatKnownRevisions(revisions) {
  if (!revisions || typeof revisions !== 'object') return '';
  const parts = [];
  for (const key of Object.keys(revisions).sort()) {
    const val = revisions[key];
    if (val === null || val === undefined || val === '') continue;
    parts.push(`${key}:${String(val)}`);
  }
  return parts.join(',');
}

export function mergeWorldDelta(prev, incoming) {
  if (!incoming || typeof incoming !== 'object') return prev || null;
  const raw = (incoming.data && typeof incoming.data === 'object' && incoming.revisions === undefined && incoming.scene === undefined)
    ? incoming.data
    : incoming;
  if (prev?.revisions?.binding !== undefined && raw.revisions?.binding !== undefined &&
      prev.revisions.binding !== raw.revisions.binding) prev = null;

  const nowMs = Date.now();
  if (raw.unchanged === true && prev) {
    return {
      ...prev,
      server_time: raw.server_time ?? prev.server_time,
      revisions: { ...(prev.revisions || {}), ...(raw.revisions || {}) },
      received_at_ms: nowMs,
    };
  }

  const nextRevs = { ...(prev?.revisions || {}), ...(raw.revisions || {}) };
  if (!prev || !raw.delta) {
    const mergedMap = (raw.map && raw.map.unchanged && prev?.map) ? prev.map : raw.map;
    return {
      ...raw,
      delta: false,
      map: mergedMap,
      revisions: nextRevs,
      received_at_ms: nowMs,
    };
  }

  const next = { ...prev };
  for (const [k, v] of Object.entries(raw)) {
    if (k === 'delta' || k === 'revisions') continue;
    if (k === 'map') {
      if (v && v.unchanged && prev.map) next.map = prev.map;
      else if (v !== undefined) next.map = v;
      continue;
    }
    next[k] = v;
  }
  next.delta = false;
  next.revisions = nextRevs;
  next.received_at_ms = nowMs;
  return next;
}

export function createWorldStream({ pollIntervalMs = 6000, getBridge } = {}) {
  const resolveBridge = getBridge || (() => globalThis.window?.AstrBotPluginPage || globalThis.window?.AstrBotPluginView || null);
  let scope = '';
  let snapshot = null;
  let epoch = 0;
  let sse = null;
  let pollTimer = null;
  let sseRetryTimer = null;
  let inFlight = null;
  let disposed = false;

  const listeners = new Set();
  const errorListeners = new Set();

  function emit(data) {
    for (const fn of listeners) {
      try { fn(data); } catch {}
    }
  }

  function emitError(err) {
    for (const fn of errorListeners) {
      try { fn(err); } catch {}
    }
  }

  function isHidden() {
    return Boolean(globalThis.document && globalThis.document.hidden === true);
  }

  async function unsubscribe(bridge, subId) {
    if (subId && typeof bridge?.unsubscribeSSE === 'function') {
      try { await bridge.unsubscribeSSE(subId); } catch {}
    }
  }

  function closeSSE() {
    const current = sse;
    sse = null;
    if (current) void unsubscribe(current.bridge,current.id);
  }

  function stopPoll() {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (sseRetryTimer !== null) {
      clearTimeout(sseRetryTimer);
      sseRetryTimer = null;
    }
  }

  function stopTransport() {
    stopPoll();
    void closeSSE();
  }

  function startFallbackPoll() {
    if (disposed || !scope || isHidden() || sse?.active || pollTimer !== null) return;
    pollTimer = setInterval(() => {
      if (!scope || isHidden() || sse?.active) return;
      void refreshNow({ full: false }).catch(() => {});
    }, pollIntervalMs);
  }

  function accept(payload, full = false) {
    if (snapshot && Number(payload.server_time) < Number(snapshot.server_time)) return snapshot;
    const before = full ? null : snapshot;
    snapshot = mergeWorldDelta(before, payload);
    if (!before || !payload.unchanged) emit(snapshot);
    return snapshot;
  }

  async function openSSE(expectedEpoch) {
    if (expectedEpoch !== epoch || disposed || !scope || isHidden() || sse || sseRetryTimer !== null) return;
    const bridge = resolveBridge();
    if (!bridge || typeof bridge.subscribeSSE !== 'function') {
      startFallbackPoll();
      return;
    }
    const connection = {bridge, id:null, active:false};
    sse = connection;
    const isCurrent = () => sse === connection && expectedEpoch === epoch && !disposed && !isHidden();
    function disconnected() {
      if (!isCurrent()) return;
      closeSSE();
      startFallbackPoll();
      sseRetryTimer = setTimeout(() => {
        sseRetryTimer = null;
        if (expectedEpoch === epoch && scope && !isHidden()) void openSSE(expectedEpoch);
      }, 20000);
      void refreshNow({ full: false }).catch(() => {});
    }
    const known = formatKnownRevisions(snapshot?.revisions);
    const query = { umo: scope, ...(known ? { known_revisions: known } : {}) };
    try {
      const subId = await bridge.subscribeSSE(
        'stream',
        {
          onOpen() {
            if (!isCurrent()) return;
            connection.active = true;
            stopPoll();
          },
          onMessage(evt) {
            if (!isCurrent()) return;
            if (evt?.eventType === 'ping') return;
            const payload = evt?.parsed && typeof evt.parsed === 'object' ? evt.parsed : evt;
            if (!payload || typeof payload !== 'object') return;
            if (payload.reset === true) {
              inFlight = null;
              epoch += 1;
              snapshot = null;
              emit(null);
              stopTransport();
              startFallbackPoll();
              void refreshNow({ full: true }).catch(() => {});
              return;
            }
            if (!payload.revisions && !payload.scene && !payload.unchanged) return;
            accept(payload);
          },
          onError: disconnected,
          onClose: disconnected,
        },
        query,
      );
      if (!isCurrent()) {
        await unsubscribe(bridge,subId);
        return;
      }
      connection.id = subId || null;
      connection.active = Boolean(subId);
      if (connection.active) stopPoll();
      else disconnected();
    } catch {
      disconnected();
    }
  }

  async function refreshNow({ full = false, fresh = false } = {}) {
    const targetScope = scope;
    if (!targetScope || disposed) return null;
    if (inFlight && !full && !fresh) return inFlight;
    const ticket = epoch;
    const bridge = resolveBridge();
    if (!bridge || typeof bridge.apiGet !== 'function') {
      const err = new Error('插件页面桥接不可用，请从 AstrBot 管理面板打开本页');
      emitError(err);
      throw err;
    }
    const params = { umo: targetScope };
    if (!full && snapshot) {
      const known = formatKnownRevisions(snapshot.revisions);
      if (known) params.known_revisions = known;
      if (snapshot.map && !snapshot.map.unchanged && snapshot.map.revision != null) {
        params.revision = snapshot.map.revision;
        if (snapshot.map.world_id) params.world_id = snapshot.map.world_id;
      }
    }
    const task = (async () => {
      await Promise.resolve();
      try {
        const res = unwrapPayload(await withTimeout(bridge.apiGet('map', params)));
        if (ticket !== epoch || targetScope !== scope || disposed) return null;
        accept(res, full);
        void openSSE(ticket);
        return snapshot;
      } catch (err) {
        if (ticket !== epoch || targetScope !== scope || disposed) return null;
        emitError(err);
        startFallbackPoll();
        throw err;
      } finally {
        if (inFlight === task) inFlight = null;
      }
    })();
    inFlight = task;
    return task;
  }

  function applyIncoming(payload) {
    if (!payload || typeof payload !== 'object') return snapshot;
    return accept(payload);
  }

  function setScope(nextScope) {
    const clean = String(nextScope || '').trim();
    if (clean === scope) {
      if (clean && !snapshot && !inFlight) {
        return refreshNow({ full: true }).catch(() => null);
      }
      if (clean && !isHidden() && !sse && pollTimer === null) {
        void openSSE(epoch);
      }
      return Promise.resolve(snapshot);
    }
    epoch += 1;
    scope = clean;
    snapshot = null;
    inFlight = null;
    stopTransport();
    if (!scope) return Promise.resolve(null);
    return refreshNow({ full: true }).catch(() => null);
  }

  function onVisibilityChange() {
    if (disposed || !scope) return;
    if (isHidden()) {
      stopTransport();
    } else {
      void refreshNow({ full: false }).catch(() => null);
    }
  }
  function onPageHide() { stopTransport(); }
  function onPageShow(event) {
    if (event.persisted) onVisibilityChange();
  }

  if (globalThis.document && typeof globalThis.document.addEventListener === 'function') {
    globalThis.document.addEventListener('visibilitychange', onVisibilityChange);
  }
  if (globalThis.window && typeof globalThis.window.addEventListener === 'function') {
    globalThis.window.addEventListener('pagehide', onPageHide);
    globalThis.window.addEventListener('pageshow', onPageShow);
  }

  return {
    get scope() { return scope; },
    get isSSEActive() { return Boolean(sse?.active); },
    getSnapshot() { return snapshot; },
    setScope,
    refreshNow,
    applyIncoming,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    onError(fn) {
      errorListeners.add(fn);
      return () => errorListeners.delete(fn);
    },
    dispose() {
      disposed = true;
      stopTransport();
      listeners.clear();
      errorListeners.clear();
      if (globalThis.document && typeof globalThis.document.removeEventListener === 'function') {
        globalThis.document.removeEventListener('visibilitychange', onVisibilityChange);
      }
      if (globalThis.window && typeof globalThis.window.removeEventListener === 'function') {
        globalThis.window.removeEventListener('pagehide', onPageHide);
        globalThis.window.removeEventListener('pageshow', onPageShow);
      }
    },
  };
}

export const worldStream = createWorldStream();
