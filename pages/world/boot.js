(() => {
  // The host's sandboxed iframe gives a classic script an opaque origin.
  const entry = new URL("./app.js?v=cabin.2", document.currentScript.src);
  const timeout = setTimeout(() => showError(new Error("页面组件加载超时")), 15000);
  let settled = false;

  function startupCopy() {
    const messages = {
      zh: ["加载失败", "世界页面加载失败，请刷新重试。", "刷新"],
      en: ["Loading failed", "The world page could not load. Refresh to try again.", "Refresh"],
      ja: ["読み込みに失敗", "世界ページを読み込めませんでした。更新して再試行してください。", "更新"],
      ru: ["Ошибка загрузки", "Не удалось загрузить страницу мира. Обновите её и повторите попытку.", "Обновить"],
    };
    let host = {}, stored;
    try { host = ((window.DynamicsPanelBridge || window.AstrBotPluginPage || window.AstrBotPluginView))?.getContext?.() || {}; } catch {}
    try { stored = localStorage.getItem("lmem_lang"); } catch {}
    const options = [new URLSearchParams(location.search).get("lang"), host.localeOverride, host.locale, stored, document.documentElement.lang];
    const locale = options.map(value => String(value || "").toLowerCase().split(/[-_]/)[0]).find(value => Object.hasOwn(messages,value));
    return messages[locale || "zh"];
  }

  function showError(error) {
    if (settled) return;
    settled = true;
    clearTimeout(timeout);
    document.body.dataset.stageMode = "workbench";
    document.body.dataset.worldStartup = "module-error";
    const [label, message, retry] = startupCopy();
    document.getElementById("wbLinkLabel").textContent = label;
    const notice = document.getElementById("wbNotice");
    notice.className = "wb-notice error";
    notice.textContent = message;
    const refresh = document.getElementById("wbRefresh");
    refresh.textContent = retry;
    refresh.disabled = false;
    refresh.onclick = () => location.reload();
    console.error("Dynamics World: startup failed", error);
  }

  import(entry.href).then(({ boot }) => {
    if (settled) return;
    boot();
    settled = true;
    clearTimeout(timeout);
  }).catch(showError);
})();
