import {tr} from './series-ui.js';
/* Overview stats, global active books, injection preview & runtime config panels. */
import { apiGet, apiPost, escapeHtml, formatTs } from "./api.js";

export function createWorkbenchOps({ state, $, notify, canWrite, requireWrite, flag, shortId, loadOverview }) {
  function renderStats() {
    const data = state.overview;
    const host = $("wbStats");
    if (!host || !data) return;
    const books = data.books || [];
    const cards = data.cards || [];
    const entries = books.reduce((sum, book) => sum + (book.entry_count || 0), 0);
    const enabledEntries = books.reduce((sum, book) => sum + (book.enabled_entry_count || 0), 0);
    const cells = [
      ["世界书", books.length],
      ["条目总数", entries],
      ["已启用条目", enabledEntries],
      ["角色卡", cards.length],
      ["场景", (data.scenarios || []).length],
      [tr("会话"), (data.sessions || []).length],
    ];
    host.innerHTML = cells
      .map(([label, value]) => `<div class="wb-stat"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}</span></div>`)
      .join("");
  }

  async function saveGlobalActive() {
    if (!requireWrite()) return;
    const ids = Array.from(document.querySelectorAll("#wbGlobalActive input[data-book]"))
      .filter((node) => node.checked)
      .map((node) => node.dataset.book);
    try {
      await apiPost("book", { action: "set_global_active", book_ids: ids });
      notify("已保存全局启用范围。", "ok");
      await loadOverview();
    } catch (error) {
      notify("保存失败：" + error.message, "error");
    }
  }

  function renderGlobalActive() {
    const data = state.overview;
    const host = $("wbGlobalActive");
    if (!host || !data) return;
    const books = data.books || [];
    const active = new Set(data.active_book_ids || []);
    const counter = $("wbActiveCount");
    if (counter) {
      counter.textContent = active.size ? active.size + " 本指定" : "全部已启用";
    }
    if (!books.length) {
      host.innerHTML = `<div class="wb-empty" data-series-text="还没有世界书。">还没有世界书。</div>`;
      return;
    }
    const readOnly = canWrite() ? "" : " disabled";
    host.innerHTML =
      `<p class="wb-field"><span class="hint" data-series-text="不勾选任何一本时，所有已启用的世界书都会参与注入。">不勾选任何一本时，所有已启用的世界书都会参与注入。</span></p>` +
      books
        .map(
          (book) =>
            `<div class="wb-check"><input type="checkbox" data-book="${escapeHtml(book.id)}"${
              active.has(book.id) ? " checked" : ""
            }${readOnly} /><label>${escapeHtml(book.name)}</label>${flag(book.enabled, "已启用", "已禁用")}</div>`,
        )
        .join("") +
      `<div class="wb-row end" style="margin-top:10px"><button type="button" class="wb-button primary" id="wbSaveActive"${readOnly}>保存全局启用</button></div>`;
    const save = $("wbSaveActive");
    if (save) save.addEventListener("click", saveGlobalActive);
  }

  function sessionRowSummary(row) {
    const parts = [row.enabled ? "注入开启" : "注入关闭"];
    if (row.scenario) parts.push("场景 " + row.scenario);
    parts.push("角色卡 " + row.card_label);
    return parts.join(" · ");
  }

  function renderOverviewSessions() {
    const data = state.overview;
    const host = $("wbOverviewSessions");
    if (!host || !data) return;
    const rows = (data.sessions || []).slice(0, 10);
    if (!rows.length) {
      host.innerHTML = `<div class="wb-empty" data-series-text="还没有会话记录。">还没有会话记录。</div>`;
      return;
    }
    host.innerHTML =
      `<table class="wb-table"><thead><tr><th data-series-text="会话">会话</th><th data-series-text="状态">状态</th><th data-series-text="最近活动">最近活动</th></tr></thead><tbody>` +
      rows
        .map(
          (row) =>
            `<tr><td class="wb-mono">${escapeHtml(shortId(row.session_id))}</td><td>${escapeHtml(
              sessionRowSummary(row),
            )}</td><td class="wb-nowrap">${escapeHtml(formatTs(row.last_active))}</td></tr>`,
        )
        .join("") +
      `</tbody></table>`;
  }

  function renderPreviewBooks() {
    const select = $("wbPreviewBook");
    if (!select || !state.overview) return;
    const books = state.overview.books || [];
    const current = select.value || state.bookId || (books[0] && books[0].id) || "";
    select.innerHTML = books
      .map(
        (book) =>
          `<option value="${escapeHtml(book.id)}"${book.id === current ? " selected" : ""}>${escapeHtml(
            book.name,
          )}</option>`,
      )
      .join("");
  }

  async function runPreviewRequest() {
    const select = $("wbPreviewBook");
    const bookId = select ? select.value : "";
    if (!bookId) {
      notify("请先选择一本世界书。", "error");
      return;
    }
    const limit = (state.overview && state.overview.config && state.overview.config.max_entries) || 10;
    try {
      const data = await apiGet("preview", {
        book_id: bookId,
        keys: $("wbPreviewText").value,
        scenario: $("wbPreviewScenario").value,
        limit,
      });
      const matched = data.matched || [];
      $("wbPreviewMatched").textContent = matched.length
        ? "命中 " + matched.length + " 条：" + matched.map((item) => item.title).join("、")
        : "没有条目命中。";
      $("wbPreviewOut").textContent = data.text || "（本轮不会注入任何世界书内容）";
    } catch (error) {
      notify("预览失败：" + error.message, "error");
    }
  }

  function formatValue(value) {
    if (value === null || value === undefined) return "—";
    if (Array.isArray(value)) return value.length ? value.join(", ") : "（空）";
    if (typeof value === "boolean") return value ? "开" : "关";
    const text = String(value);
    return text.length ? text : "（空）";
  }

  function renderConfigRows(title, rows) {
    return (
      `<h3 style="margin:16px 0 6px;font-size:13px">${escapeHtml(title)}</h3>` +
      `<table class="wb-table"><tbody>` +
      rows
        .map(([key, value]) => `<tr><td class="wb-mono">${escapeHtml(key)}</td><td>${escapeHtml(formatValue(value))}</td></tr>`)
        .join("") +
      `</tbody></table>`
    );
  }

  function renderConfig() {
    const host = $("wbConfigBody");
    if (!host || !state.overview) return;
    const config = state.overview.config || {};
    const sections = [];
    const scalars = [];
    Object.keys(config).forEach((key) => {
      const value = config[key];
      if (value && typeof value === "object" && !Array.isArray(value)) return;
      scalars.push([key, value]);
    });
    if (scalars.length) sections.push(renderConfigRows("基础", scalars));
    Object.keys(config).forEach((key) => {
      const value = config[key];
      if (!value || typeof value !== "object" || Array.isArray(value)) return;
      sections.push(renderConfigRows(key, Object.entries(value)));
    });
    host.innerHTML = sections.join("");
  }

  return {
    renderStats,
    renderGlobalActive,
    renderOverviewSessions,
    renderPreviewBooks,
    runPreviewRequest,
    renderConfig,
  };
}
