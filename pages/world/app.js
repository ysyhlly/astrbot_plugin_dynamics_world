/** Main workbench shell for astrbot_plugin_dynamics_world. */
import { languagePicker, msg, setText, tr } from "./series-ui.js";
import "./pixel-cabin.js?v=wb-iso.1";
import { refreshWorld, refreshLife } from "./world.js?v=wb-iso.1";
import { apiGet, escapeHtml, readyBridge } from "./api.js";
import { createWorkbenchOps } from "./workbench-ops.js?v=stage.11";
import { createWorkbenchStudio } from "./workbench-studio.js?v=stage.11";

let leafletPromise = null;
let mapModulePromise = null;
let setupModulePromise = null;
let creativeModulePromise = null;
const loadedModules = new Set();

function ensureLeaflet() {
  if (typeof window.L !== "undefined") return Promise.resolve();
  if (!leafletPromise) {
    leafletPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector('script[src*="./vendor/leaflet/leaflet.js"]');
      if (existing) {
        if (typeof window.L !== "undefined") {
          resolve();
          return;
        }
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => {
          leafletPromise = null;
          reject(new Error("Failed to load Leaflet"));
        }, { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = "./vendor/leaflet/leaflet.js";
      script.async = true;
      script.addEventListener("load", () => resolve(), { once: true });
      script.addEventListener("error", () => {
        leafletPromise = null;
        reject(new Error("Failed to load Leaflet"));
      }, { once: true });
      document.head.append(script);
    });
  }
  return leafletPromise;
}

function ensureMapModule(needLeaflet = false) {
  const loadMap = () => {
    if (!mapModulePromise) {
      mapModulePromise = import("./map.js?v=round2.1")
        .then((mod) => {
          loadedModules.add("map");
          return mod;
        })
        .catch((err) => {
          mapModulePromise = null;
          throw err;
        });
    }
    return mapModulePromise;
  };
  return needLeaflet ? ensureLeaflet().then(loadMap) : loadMap();
}

function ensureSetupModule() {
  if (!setupModulePromise) {
    setupModulePromise = import("./setup.js?v=series-audit.1")
      .then((mod) => {
        loadedModules.add("setup");
        return mod;
      })
      .catch((err) => {
        setupModulePromise = null;
        throw err;
      });
  }
  return setupModulePromise;
}

function ensureCreativeModule() {
  if (!creativeModulePromise) {
    creativeModulePromise = import("./creative-world.js?v=wb-iso.1")
      .then((mod) => {
        loadedModules.add("creative");
        return mod;
      })
      .catch((err) => {
        creativeModulePromise = null;
        throw err;
      });
  }
  return creativeModulePromise;
}

const state = {
  overview: null,
  view: "overview",
  bookId: "",
  book: null,
  cardId: "",
  card: null,
};

const $ = (id) => document.getElementById(id);

function notify(message, kind) {
  const node = $("wbNotice");
  if (!node) return;
  if (!message) {
    node.className = "wb-notice wb-hidden";
    node.textContent = "";
    return;
  }
  node.className = "wb-notice" + (kind ? " " + kind : "");
  node.textContent = message;
}

function setLink(ok, label) {
  const lamp = $("wbLamp");
  const text = $("wbLinkLabel");
  if (lamp) lamp.className = "wb-lamp" + (ok ? " on" : " warn");
  if (text) setText(text, msg(label));
}

function canWrite() {
  const caps = state.overview && state.overview.capabilities;
  return Boolean(caps && caps.write);
}

function requireWrite() {
  if (canWrite()) return true;
  notify(tr("当前为只读模式：请在插件配置里打开 web_panel.allow_write 后再修改。"), "error");
  return false;
}

function flag(value, on, off) {
  return value
    ? `<span class="wb-tag on">${escapeHtml(on)}</span>`
    : `<span class="wb-tag off">${escapeHtml(off)}</span>`;
}

function listToText(items) {
  return (Array.isArray(items) ? items : []).join(", ");
}

function shortId(value) {
  const text = String(value || "");
  return text.length > 34 ? text.slice(0, 18) + "…" + text.slice(-10) : text;
}

const STAGE_DRAWER_VIEWS = new Set(["life", "projects", "activity", "scenes", "weather"]);
const CORE_VIEWS = ["life", "map", "cards", "books"];
const VIEW_ALIASES = { stories: "life" };
const MORE_VIEWS = ["scenes", "weather", "projects", "activity", "sessions", "overview", "setup", "preview", "config", "migration"];
const MORE_VIEW_SET = new Set(MORE_VIEWS);

const views = {
  cabin: ["3D 像素小屋", "小屋与花园，装下日常的片刻。"],
  projects: ["持续创作项目", "让构思、初稿与修订沿着同一个项目积累。"],
  activity: ["世界动态", "查看实际发生的变化，以及仍在进行的行动。"],
  scenes: ["室内动作", "管理当前房间内的阅读、饮水、写笔记与家具陈设。"],
  weather: ["天气环境", "查看窗外天光与预报，配置现实或模拟气候来源。"],
  setup: ["安装引导与检查", "逐步建立角色和世界，确认配套能力已经接通。"],
  overview: ["世界总览", "查看角色的生活状态，维护共同的世界。"],
  map: ["世界地图", "看见角色在哪里、在做什么，以及周围的环境。"],
  life: ["生活与故事", "管理生活节奏、纠正当下状态，回看生活故事与聊天约定。"],
  books: ["世界书", "整理世界设定，决定哪些内容在对话中生效。"],
  cards: ["角色卡", "维护角色身份、性格与共同的生活背景。"],
  sessions: ["场景与会话", "为不同会话选择角色与场景。"],
  preview: ["注入预览", "检查本轮会提供给模型的角色与世界资料。"],
  config: ["生效配置", "查看当前设置与接入状态。"],
  migration: ["数据迁移", "把已有设定与生活记录带入群间世界。"],
};

function normalizeView(rawName, anchor = "") {
  const key = String(rawName || "").trim();
  if (!key) return { name: "", anchor };
  const resolved = Object.hasOwn(VIEW_ALIASES, key) ? VIEW_ALIASES[key] : key;
  const resolvedAnchor = anchor || (key === "stories" ? "stories" : "");
  return { name: resolved, anchor: resolvedAnchor };
}

let drawerBar = null;
let drawerOpener = null;
let landingView = null;
let landingAnchor = "";
let loaded = false;
const isVisible = (node) => Boolean(node?.getClientRects().length) && !node.disabled &&
  !node.closest("[inert]") && getComputedStyle(node).visibility !== "hidden";
function ensureDrawerBar() {
  if (drawerBar) return drawerBar;
  drawerBar = document.createElement("div");
  drawerBar.id = "cabinDrawerBar";
  drawerBar.className = "cabin-drawer-bar";
  const copy = document.createElement("div");
  copy.className = "cabin-drawer-copy";
  const title = document.createElement("strong");
  title.id = "cabinDrawerTitle";
  const lede = document.createElement("small");
  lede.id = "cabinDrawerLede";
  copy.append(title, lede);
  const actions = document.createElement("div");
  actions.className = "cabin-drawer-actions";
  const toWorkbenchBtn = document.createElement("button");
  toWorkbenchBtn.type = "button";
  toWorkbenchBtn.id = "cabinDrawerToWorkbench";
  toWorkbenchBtn.className = "wb-button tiny";
  setText(toWorkbenchBtn, msg("进入工作台"));
  toWorkbenchBtn.addEventListener("click", () => setView(state.view, { focus: true, drawer: false }));
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.id = "cabinDrawerClose";
  closeBtn.className = "wb-button tiny cabin-drawer-close";
  setText(closeBtn, msg("回到 3D 小屋"));
  closeBtn.addEventListener("click", () => setView("cabin"));
  actions.append(toWorkbenchBtn, closeBtn);
  drawerBar.append(copy, actions);
  return drawerBar;
}

function ensureLazyViewTabs() {
  const tabs = $("wbTabs");
  if (!tabs) return;
  const defs = [
    ["projects", "创作项目"],
    ["activity", "世界动态"],
    ["setup", "安装引导"],
  ];
  for (const [viewName, label] of defs) {
    if ($("tab-" + viewName)) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "wb-tab";
    btn.id = "tab-" + viewName;
    btn.dataset.view = viewName;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", "false");
    btn.setAttribute("aria-controls", "view-" + viewName);
    btn.tabIndex = -1;
    setText(btn, msg(label));
    tabs.append(btn);
  }
}

function organizeTabClusters() {
  ensureLazyViewTabs();
  const tabs = $("wbTabs");
  if (!tabs) return;
  const moreDetails = $("wbTabsMore");
  const moreMenu = $("wbTabsMoreMenu");
  const anchor = moreDetails || null;

  const cabinTab = tabs.querySelector('.wb-tab[data-view="cabin"]');
  if (cabinTab) {
    cabinTab.dataset.cluster = "cabin";
    delete cabinTab.dataset.clusterStart;
    delete cabinTab.dataset.clusterLabel;
    if (anchor) tabs.insertBefore(cabinTab, anchor);
  }

  for (const viewName of CORE_VIEWS) {
    const btn = tabs.querySelector(`.wb-tab[data-view="${viewName}"]`);
    if (!btn) continue;
    btn.dataset.cluster = "core";
    delete btn.dataset.clusterStart;
    delete btn.dataset.clusterLabel;
    if (anchor) tabs.insertBefore(btn, anchor);
    else tabs.append(btn);
  }

  if (moreMenu) {
    for (const viewName of MORE_VIEWS) {
      const btn = tabs.querySelector(`.wb-tab[data-view="${viewName}"]`);
      if (!btn) continue;
      btn.dataset.cluster = "ops";
      delete btn.dataset.clusterStart;
      delete btn.dataset.clusterLabel;
      moreMenu.append(btn);
    }
  }
}

function updateMoreTabsIndicator(activeView) {
  const moreDetails = $("wbTabsMore");
  const summary = $("wbTabsMoreSummary");
  if (!moreDetails || !summary) return;
  const labelNode = summary.querySelector(".wb-tabs-more-label");
  const inMore = MORE_VIEW_SET.has(activeView);
  summary.dataset.active = String(inMore);
  if (labelNode) {
    if (inMore && views[activeView]) {
      setText(labelNode, msg("{0} · {1}", msg("更多与运维"), msg(views[activeView][0])));
    } else {
      setText(labelNode, msg("更多与运维"));
    }
  }
}

const ops = createWorkbenchOps({
  state,
  $,
  notify,
  canWrite,
  requireWrite,
  flag,
  shortId,
  loadOverview,
});

const studio = createWorkbenchStudio({
  state,
  $,
  notify,
  canWrite,
  requireWrite,
  listToText,
  shortId,
  setView,
  loadOverview,
  refreshOverviewSilently,
});

function syncViewSections(name, isDrawer, isCabinStage) {
  const bar = ensureDrawerBar();
  document.querySelectorAll(".wb-view").forEach((section) => {
    const isTarget = section.id === "view-" + name;
    const keepCabin = isCabinStage && section.id === "view-cabin";
    section.classList.toggle("wb-hidden", !(isTarget || keepCabin));
    section.classList.toggle("is-stage-drawer", isDrawer && isTarget);
    if (isDrawer && isTarget) {
      setText($("cabinDrawerTitle") || bar.querySelector("#cabinDrawerTitle"), msg(views[name][0]));
      setText($("cabinDrawerLede") || bar.querySelector("#cabinDrawerLede"), msg(views[name][1]));
      if (section.firstElementChild !== bar) section.prepend(bar);
    }
  });
  if (!isDrawer && bar.parentElement) bar.remove();
}

function loadLazyViewModule(name) {
  const finish = () => {
    if (state.view !== name) return;
    const curDrawer = document.body.dataset.stageMode === "cabin-drawer";
    syncViewSections(name, curDrawer, curDrawer || name === "cabin");
    document.dispatchEvent(new CustomEvent("world-view", { detail: name }));
  };
  if (name === "map") {
    if (typeof window.L === "undefined" || !loadedModules.has("map")) {
      void ensureMapModule(true)
        .then(finish)
        .catch((err) => notify(tr("无法加载地图模块。") + (err?.message ? " " + err.message : ""), "error"));
      return true;
    }
  } else if (name === "scenes" || name === "weather") {
    if (!loadedModules.has("map")) {
      void ensureMapModule(false)
        .then(finish)
        .catch((err) => notify(tr("无法加载世界视图模块。") + (err?.message ? " " + err.message : ""), "error"));
      return true;
    }
  } else if (name === "setup") {
    if (!loadedModules.has("setup")) {
      void ensureSetupModule()
        .then(finish)
        .catch((err) => notify(tr("无法加载安装引导模块。") + (err?.message ? " " + err.message : ""), "error"));
      return true;
    }
  } else if (name === "projects" || name === "activity") {
    if (!loadedModules.has("creative")) {
      void ensureCreativeModule()
        .then(finish)
        .catch((err) => notify(tr("无法加载创作与动态模块。") + (err?.message ? " " + err.message : ""), "error"));
      return true;
    }
  }
  return false;
}

function setView(rawName, { focus = false, remember = true, drawer = false, anchor = "" } = {}) {
  const normalized = normalizeView(rawName, anchor);
  let name = normalized.name;
  const resolvedAnchor = normalized.anchor;
  if (!views[name]) name = "overview";
  const wasDrawer = document.body.dataset.stageMode === "cabin-drawer";
  state.view = name;
  const isDrawer = Boolean(drawer) && name !== "cabin" && STAGE_DRAWER_VIEWS.has(name);
  const isCabinStage = name === "cabin" || isDrawer;
  if (isDrawer && !wasDrawer && focus) drawerOpener = document.activeElement;
  document.body.dataset.stageMode = name === "cabin" ? "cabin" : isDrawer ? "cabin-drawer" : "workbench";
  document.body.dataset.drawerView = isDrawer ? name : "";
  setText($("wbTitle"), msg(views[name][0]));
  setText($("wbLede"), msg(views[name][1]));
  updateDocumentTitle();
  if (remember) try {
    const url = new URL(location.href);
    url.searchParams.set("view", name);
    history.replaceState(history.state, "", url);
  } catch {}
  if (name === "life") refreshLife();
  const selected = isDrawer && !isVisible($("tab-" + name)) ? "cabin" : name;
  document.querySelectorAll(".wb-tab[data-view]").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.view === selected));
    tab.tabIndex = tab.dataset.view === selected ? 0 : -1;
  });
  updateMoreTabsIndicator(name);
  const moreDetails = $("wbTabsMore");
  if (moreDetails && moreDetails.open && !focus) moreDetails.open = false;
  syncViewSections(name, isDrawer, isCabinStage);
  const loadingLazy = loadLazyViewModule(name);
  if (!loadingLazy) {
    document.dispatchEvent(new CustomEvent("world-view", { detail: name }));
  }
  if (name === "books" && !state.bookId) studio.selectFirstBook();
  if (name === "cards" && !state.cardId) studio.selectFirstCard();
  if (name === "life" && resolvedAnchor === "stories") {
    requestAnimationFrame(() => {
      $("dwStoriesSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  if (isDrawer && focus) $("cabinDrawerClose")?.focus({ preventScroll: true });
  if (wasDrawer && !isDrawer) {
    if (name === "cabin") {
      const target = isVisible(drawerOpener) ? drawerOpener : $("tab-cabin");
      target?.focus({ preventScroll: true });
    }
    drawerOpener = null;
  }
}

function updateDocumentTitle() {
  document.title = tr(views[state.view][0]) + tr(" · 群间世界");
}
window.addEventListener("series-languagechange", () => {
  updateDocumentTitle();
  updateMoreTabsIndicator(state.view);
});

async function refreshOverviewSilently() {
  try {
    state.overview = await apiGet("overview");
    ops.renderStats();
    ops.renderGlobalActive();
    studio.renderBookList();
    studio.renderCardList();
    ops.renderPreviewBooks();
  } catch {}
}

function renderAll() {
  ops.renderStats();
  ops.renderGlobalActive();
  ops.renderOverviewSessions();
  studio.renderBookList();
  studio.renderCardList();
  studio.renderSessionTable();
  ops.renderPreviewBooks();
  ops.renderConfig();
  if (state.bookId) studio.loadBook(state.bookId);
  else if (state.view === "books") studio.selectFirstBook();
  if (state.cardId) studio.loadCard(state.cardId);
  else if (state.view === "cards") studio.selectFirstCard();
}

async function loadOverview() {
  const refresh = $("wbRefresh");
  if (refresh.disabled) return;
  refresh.disabled = true;
  document.body.dataset.worldStartup = "connecting";
  setLink(false, "连接中");
  try {
    await readyBridge();
    document.body.dataset.worldStartup = "loading";
    setLink(false, "读取中");
    state.overview = await apiGet("overview");
    renderAll();
    if (!loaded && state.view === "overview") {
      const target = landingView || (state.overview.cards?.length ? "cabin" : "setup");
      setView(target, { drawer: false, anchor: landingView ? landingAnchor : "" });
    }
    loaded = true;
    document.body.dataset.worldStartup = "ready";
    setLink(true, "已连接");
    notify("");
    void refreshWorld();
    document.dispatchEvent(new Event("world-overview-ready"));
  } catch (error) {
    document.body.dataset.worldStartup = "error";
    setLink(false, "连接失败");
    notify(tr("无法读取世界工作区。请刷新重试。") + (error?.message ? " " + error.message : ""), "error");
  } finally {
    refresh.disabled = false;
  }
}

function wireTabs() {
  const tabs = $("wbTabs");
  if (!tabs) return;
  const moreDetails = $("wbTabsMore");
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest(".wb-tab[data-view]");
    if (!button) return;
    landingView = button.dataset.view || "overview";
    landingAnchor = "";
    if (moreDetails?.open) moreDetails.open = false;
    setView(landingView, { focus: true, drawer: false });
  });
  document.addEventListener("click", (event) => {
    if (moreDetails?.open && !moreDetails.contains(event.target)) {
      moreDetails.open = false;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && moreDetails?.open) {
      event.preventDefault();
      moreDetails.open = false;
      $("wbTabsMoreSummary")?.focus({ preventScroll: true });
    }
  });
  tabs.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...tabs.querySelectorAll(".wb-tab[data-view]")].filter(isVisible);
    const index = buttons.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? buttons.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus();
    buttons[next].click();
  });
}

function wireActions() {
  document.addEventListener("world-setup-saved", () => loadOverview());
  document.addEventListener("cabin-open-view", (event) => {
    const detail = event.detail;
    const rawView = typeof detail === "string" ? detail : detail?.view;
    const { name, anchor } = normalizeView(rawView, typeof detail === "object" && detail ? detail.anchor || "" : "");
    if (!name || !views[name]) return;
    const drawer = typeof detail === "object" && detail ? Boolean(detail.drawer) : false;
    setView(name, { focus: true, drawer, anchor });
  });
  const backCabin = $("wbBackCabin");
  if (backCabin) backCabin.addEventListener("click", () => setView("cabin"));
  const cmdK = $("dwCmdK");
  if (cmdK) {
    cmdK.addEventListener("click", () => {
      if (typeof window.DynamicsSeriesNavigation?.openCmdK === "function") {
        window.DynamicsSeriesNavigation.openCmdK();
      } else if (typeof window.DynamicsCommandPalette?.open === "function") {
        window.DynamicsCommandPalette.open();
      } else {
        document.dispatchEvent(
          new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true, cancelable: true })
        );
      }
    });
  }
  window.addEventListener("dynamics-cmdk-deeplink", (event) => {
    const item = event.detail || {};
    const dl = typeof item.deep_link === "object" && item.deep_link ? item.deep_link : {};
    if (dl.umo) {
      const scopeInput = $("dwScope");
      if (scopeInput && scopeInput.value.trim() !== String(dl.umo).trim()) {
        scopeInput.value = String(dl.umo).trim();
        scopeInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
    const rawTarget = dl.view || (typeof item.deep_link === "string" ? item.deep_link : "");
    const { name: targetView, anchor } = normalizeView(rawTarget, dl.anchor || "");
    if (targetView && views[targetView]) {
      const currentMode = document.body.dataset.stageMode || "workbench";
      const openInDrawer = currentMode !== "workbench" && STAGE_DRAWER_VIEWS.has(targetView);
      setView(targetView, { focus: true, drawer: openInDrawer, anchor });
      if (targetView === "books" && dl.id) {
        state.bookId = String(dl.id);
        studio.loadBook(state.bookId);
      } else if (targetView === "cards" && dl.id) {
        state.cardId = String(dl.id);
        studio.loadCard(state.cardId);
      }
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.key !== "Escape" || document.body.dataset.stageMode !== "cabin-drawer") return;
    if ($("wbDrawerHost")?.children.length) return;
    if (document.querySelector("#causal-panel:not([hidden]), dialog[open]")) return;
    if (CSS.supports("selector(:popover-open)") && document.querySelector(":popover-open")) return;
    event.preventDefault();
    setView("cabin");
  });
  const refresh = $("wbRefresh");
  if (refresh) refresh.addEventListener("click", () => loadOverview());
  const newBook = $("wbNewBook");
  if (newBook) newBook.addEventListener("click", () => studio.openCreateDrawer("worldbook"));
  const newCard = $("wbNewCard");
  if (newCard) newCard.addEventListener("click", () => studio.openCreateDrawer("card"));
  const importBook = $("wbImportBook");
  if (importBook) importBook.addEventListener("click", () => studio.openImportDrawer("worldbook"));
  const importCard = $("wbImportCard");
  if (importCard) importCard.addEventListener("click", () => studio.openImportDrawer("card"));
  const runPreview = $("wbPreviewRun");
  if (runPreview) runPreview.addEventListener("click", ops.runPreviewRequest);
}

export function boot() {
  const language = languagePicker();
  language.classList.add("dw-cabin-language");
  const navTools = document.querySelector(".dw-nav-tools");
  const themeBtn = $("dwTheme");
  if (navTools && themeBtn) navTools.insertBefore(language, themeBtn);
  else navTools?.prepend(language);
  organizeTabClusters();
  wireTabs();
  wireActions();
  const query = new URLSearchParams(location.search);
  // Companion panels offer "return to cabin" even before the first card is set up.
  const requestedRaw = query.get("view") || (query.has("series_entry") ? "cabin" : "");
  const normalized = normalizeView(requestedRaw);
  landingView = Object.hasOwn(views, normalized.name) ? normalized.name : null;
  landingAnchor = normalized.anchor;
  setView("overview", { remember: false, drawer: false });
  void loadOverview();
}
