/** Main workbench shell for astrbot_plugin_dynamics_world. */
import { languagePicker, msg, setText, tr } from "./series-ui.js";
import "./map.js?v=round2.1";
import "./setup.js?v=series-audit.1";
import "./creative-world.js";
import "./pixel-cabin.js?v=mobile.2";
import { refreshWorld, refreshLife } from "./world.js?v=series-audit.1";
import { apiGet, escapeHtml, readyBridge } from "./api.js";
import { createWorkbenchOps } from "./workbench-ops.js?v=stage.11";
import { createWorkbenchStudio } from "./workbench-studio.js?v=stage.11";

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

const STAGE_DRAWER_VIEWS = new Set(["life", "stories", "projects", "activity", "scenes", "weather"]);
const CLUSTER_SPEC = [
  ["companion", "日常陪伴", ["cabin", "life", "stories", "projects", "activity", "scenes", "weather"]],
  ["map", "地图出行", ["map"]],
  ["studio", "设定工坊", ["cards", "books", "sessions", "overview"]],
  ["ops", "调试运维", ["setup", "preview", "config", "migration"]],
];

const views = {
  cabin: ["3D 像素小屋", "小屋与花园，装下日常的片刻。"],
  projects: ["持续创作项目", "让构思、初稿与修订沿着同一个项目积累。"],
  activity: ["世界动态", "查看实际发生的变化，以及仍在进行的行动。"],
  scenes: ["室内动作", "管理当前房间内的阅读、饮水、写笔记与家具陈设。"],
  weather: ["天气环境", "查看窗外天光与预报，配置现实或模拟气候来源。"],
  setup: ["安装引导与检查", "逐步建立角色和世界，确认配套能力已经接通。"],
  overview: ["世界总览", "查看角色的生活状态，维护共同的世界。"],
  map: ["世界地图", "看见角色在哪里、在做什么，以及周围的环境。"],
  life: ["日常动态", "今天的安排、当前的状态，都有迹可循。"],
  stories: ["故事与约定", "回看已经发生的事，记住还未完成的约定。"],
  books: ["世界书", "整理世界设定，决定哪些内容在对话中生效。"],
  cards: ["角色卡", "维护角色身份、性格与共同的生活背景。"],
  sessions: ["场景与会话", "为不同会话选择角色与场景。"],
  preview: ["注入预览", "检查本轮会提供给模型的角色与世界资料。"],
  config: ["生效配置", "查看当前设置与接入状态。"],
  migration: ["数据迁移", "把已有设定与生活记录带入群间世界。"],
};

let drawerBar = null;
let drawerOpener = null;
let landingView = null;
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
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.id = "cabinDrawerClose";
  closeBtn.className = "wb-button tiny cabin-drawer-close";
  setText(closeBtn, msg("回到 3D 小屋"));
  closeBtn.addEventListener("click", () => setView("cabin"));
  drawerBar.append(copy, closeBtn);
  return drawerBar;
}

function organizeTabClusters() {
  const tabs = $("wbTabs");
  if (!tabs) return;
  for (const [cluster, label, names] of CLUSTER_SPEC) {
    let firstPlaced = false;
    for (const viewName of names) {
      const btn = tabs.querySelector(`.wb-tab[data-view="${viewName}"]`);
      if (!btn) continue;
      btn.dataset.cluster = cluster;
      if (!firstPlaced) {
        btn.dataset.clusterStart = "true";
        btn.dataset.clusterLabel = msg(label);
        firstPlaced = true;
      } else {
        delete btn.dataset.clusterStart;
        delete btn.dataset.clusterLabel;
      }
      tabs.append(btn);
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

function setView(name, { focus = false, remember = true } = {}) {
  if (!views[name]) name = "overview";
  const wasDrawer = STAGE_DRAWER_VIEWS.has(state.view);
  state.view = name;
  const isDrawer = STAGE_DRAWER_VIEWS.has(name);
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
  if (["life", "stories"].includes(name)) refreshLife();
  const selected = isDrawer && !isVisible($("tab-" + name)) ? "cabin" : name;
  document.querySelectorAll(".wb-tab").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.view === selected));
    tab.tabIndex = tab.dataset.view === selected ? 0 : -1;
  });
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
  document.dispatchEvent(new CustomEvent("world-view", { detail: name }));
  if (name === "books" && !state.bookId) studio.selectFirstBook();
  if (name === "cards" && !state.cardId) studio.selectFirstCard();
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
window.addEventListener("series-languagechange", updateDocumentTitle);

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
      setView(landingView || (state.overview.cards?.length ? "cabin" : "setup"));
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
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest(".wb-tab");
    if (!button) return;
    landingView = button.dataset.view || "overview";
    setView(landingView, { focus: true });
  });
  tabs.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...tabs.querySelectorAll(".wb-tab")].filter(isVisible);
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
    if (event.detail && views[event.detail]) setView(event.detail, { focus: true });
  });
  const backCabin = $("wbBackCabin");
  if (backCabin) backCabin.addEventListener("click", () => setView("cabin"));
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.key !== "Escape" || !STAGE_DRAWER_VIEWS.has(state.view)) return;
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
  document.querySelector(".dw-nav-tools")?.prepend(language);
  organizeTabClusters();
  wireTabs();
  wireActions();
  const requested = new URLSearchParams(location.search).get("view");
  landingView = views[requested] ? requested : null;
  setView("overview", { remember: false });
  void loadOverview();
}
