import {tr} from './series-ui.js';
/* Worldbook, character card & session studio panels and drawers. */
import { apiGet, apiPost, escapeHtml, formatTs, splitList } from "./api.js";
import { parsePngCharaChunk } from "./png-chara.js";
export { parsePngCharaChunk };

const CARD_TEXT_FIELDS = [
  ["description", "角色描述", 4],
  ["personality", "性格", 4],
  ["scenario", tr("场景"), 3],
  ["system_prompt", "系统提示词", 6],
  ["post_history_instructions", "输出要求", 4],
  ["first_mes", "开场白", 3],
  ["mes_example", "示例对话", 6],
  ["group_addendum", "群聊适配层（仅群聊注入）", 5],
];

function downloadJsonFile(filename, data) {
  const safeName = String(filename || "export")
    .replace(/[\\/:*?"<>|]+/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 64);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = safeName.endsWith(".json") ? safeName : `${safeName}.json`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function createWorkbenchStudio({
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
}) {
  function selectFirstBook() {
    const books = (state.overview && state.overview.books) || [];
    if (books.length) loadBook(books[0].id);
    else renderBookDetail();
  }

  function renderBookList() {
    const host = $("wbBookList");
    if (!host || !state.overview) return;
    const books = state.overview.books || [];
    if (!books.length) {
      host.innerHTML = `<li><div class="wb-empty" data-series-text="还没有世界书，点右上角新建。">还没有世界书，点右上角新建。</div></li>`;
      return;
    }
    host.innerHTML = books
      .map(
        (book) =>
          `<li><button type="button" class="wb-list-item" data-book="${escapeHtml(
            book.id,
          )}" aria-current="${String(book.id === state.bookId)}"><strong>${escapeHtml(
            book.name,
          )}</strong><small>${book.entry_count} 条 · ${book.enabled_entry_count} 启用 · ${escapeHtml(
            formatTs(book.updated_at),
          )}</small></button></li>`,
      )
      .join("");
    host.querySelectorAll("button[data-book]").forEach((button) => {
      button.addEventListener("click", () => loadBook(button.dataset.book));
    });
  }

  const entryFilter = { q: "", constant: "all", enabled: "all", scenario: "" };
  const selectedEntryIds = new Set();

  async function loadBook(bookId) {
    if (!bookId) return;
    state.bookId = bookId;
    selectedEntryIds.clear();
    renderBookList();
    try {
      const data = await apiGet("book", { book_id: bookId });
      state.book = data.book;
    } catch (error) {
      state.book = null;
      notify("读取世界书失败：" + error.message, "error");
    }
    renderBookDetail();
  }

  function filterBookEntries(book) {
    const entries = book.entries || [];
    const q = entryFilter.q.trim().toLowerCase();
    return entries.filter((entry) => {
      if (entryFilter.constant === "constant" && !entry.constant) return false;
      if (entryFilter.constant === "keyword" && entry.constant) return false;
      if (entryFilter.enabled === "enabled" && !entry.enabled) return false;
      if (entryFilter.enabled === "disabled" && entry.enabled) return false;
      if (entryFilter.scenario && !(entry.scenarios || []).includes(entryFilter.scenario)) return false;
      if (q) {
        const hay = [
          entry.name,
          entry.uid,
          ...(entry.keys || []),
          ...(entry.secondary_keys || []),
          ...(entry.scenarios || []),
          entry.content,
          entry.comment,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderEntryTableMarkup(book, filtered) {
    const entries = book.entries || [];
    if (!entries.length) {
      return `<div class="wb-empty" data-series-text="这本书还没有条目，点「新增条目」开始。">这本书还没有条目，点「新增条目」开始。</div>`;
    }
    if (!filtered.length) {
      return `<div class="wb-empty">没有符合筛选条件的条目。</div>`;
    }
    const readOnly = canWrite() ? "" : " disabled";
    const allChecked = filtered.length > 0 && filtered.every((e) => selectedEntryIds.has(e.uid));
    return (
      `<table class="wb-table"><thead><tr>` +
      `<th class="wb-check-col"><input type="checkbox" id="wbEntrySelectAll" aria-label="全选当前条目"${allChecked ? " checked" : ""}${readOnly} /></th>` +
      `<th data-series-text="条目">条目</th><th data-series-text="关键词">关键词</th><th data-series-text="场景">场景</th><th data-series-text="常驻">常驻</th><th data-series-text="优先级">优先级</th><th data-series-text="启用">启用</th><th></th></tr></thead><tbody>` +
      filtered
        .map(
          (entry) =>
            `<tr>` +
            `<td class="wb-check-col"><input type="checkbox" data-select-entry="${escapeHtml(entry.uid)}"${selectedEntryIds.has(entry.uid) ? " checked" : ""}${readOnly} /></td>` +
            `<td>${escapeHtml(entry.name || entry.uid)}<br /><span class="wb-mono">${escapeHtml(
              entry.uid,
            )}</span></td><td>${escapeHtml(listToText(entry.keys)) || '<span class="wb-mono" data-series-text="（无）">（无）</span>'}</td><td>${escapeHtml(
              listToText(entry.scenarios),
            )}</td><td>${entry.constant ? "是" : "否"}</td><td>${escapeHtml(
              entry.priority,
            )}</td><td>${entry.enabled ? "是" : "否"}</td>` +
            `<td class="actions">` +
            `<button type="button" class="wb-button tiny" data-act="edit" data-id="${escapeHtml(entry.uid)}"${readOnly}>编辑</button> ` +
            `<button type="button" class="wb-button tiny" data-act="toggle" data-id="${escapeHtml(entry.uid)}"${readOnly}>${
              entry.enabled ? "停用" : tr("启用")
            }</button> ` +
            `<button type="button" class="wb-button tiny" data-act="up" data-id="${escapeHtml(entry.uid)}"${readOnly}>↑</button> ` +
            `<button type="button" class="wb-button tiny" data-act="down" data-id="${escapeHtml(entry.uid)}"${readOnly}>↓</button> ` +
            `<button type="button" class="wb-button tiny" data-act="duplicate" data-id="${escapeHtml(entry.uid)}"${readOnly}>复制</button> ` +
            `<button type="button" class="wb-button tiny danger" data-act="delete" data-id="${escapeHtml(entry.uid)}"${readOnly}>删除</button>` +
            `</td></tr>`,
        )
        .join("") +
      `</tbody></table>`
    );
  }

  function updateEntryTableView(book) {
    const tableHost = $("wbEntryTableHost");
    if (!tableHost || !book) return;
    const filtered = filterBookEntries(book);
    const validIds = new Set((book.entries || []).map((e) => e.uid));
    for (const id of Array.from(selectedEntryIds)) {
      if (!validIds.has(id)) selectedEntryIds.delete(id);
    }
    tableHost.innerHTML = renderEntryTableMarkup(book, filtered);
    const countEl = $("wbEntryFilterCount");
    if (countEl) {
      const total = (book.entries || []).length;
      const selCount = selectedEntryIds.size;
      countEl.textContent =
        selCount > 0
          ? `显示 ${filtered.length}/${total} · 已选 ${selCount}`
          : `显示 ${filtered.length}/${total}`;
    }
    const batchEnable = $("wbBatchEnable");
    const batchDisable = $("wbBatchDisable");
    if (batchEnable) batchEnable.disabled = !canWrite() || selectedEntryIds.size === 0;
    if (batchDisable) batchDisable.disabled = !canWrite() || selectedEntryIds.size === 0;

    const selectAll = $("wbEntrySelectAll");
    if (selectAll) {
      selectAll.addEventListener("change", () => {
        for (const entry of filtered) {
          if (selectAll.checked) selectedEntryIds.add(entry.uid);
          else selectedEntryIds.delete(entry.uid);
        }
        updateEntryTableView(book);
      });
    }
    tableHost.querySelectorAll("input[data-select-entry]").forEach((box) => {
      box.addEventListener("change", () => {
        const uid = box.dataset.selectEntry;
        if (box.checked) selectedEntryIds.add(uid);
        else selectedEntryIds.delete(uid);
        updateEntryTableView(book);
      });
    });
    tableHost.querySelectorAll("button[data-act]").forEach((button) => {
      button.addEventListener("click", () => onEntryAction(book, button.dataset.act, button.dataset.id));
    });
  }

  async function batchToggleEntries(book, enabled) {
    if (!requireWrite() || !book) return;
    const targets = (book.entries || []).filter(
      (entry) => selectedEntryIds.has(entry.uid) && Boolean(entry.enabled) !== Boolean(enabled),
    );
    if (!targets.length) {
      notify(enabled ? "所选条目已全部处于启用状态。" : "所选条目已全部处于停用状态。", "ok");
      return;
    }
    const btn = $(enabled ? "wbBatchEnable" : "wbBatchDisable");
    if (btn) btn.disabled = true;
    try {
      for (const entry of targets) {
        await apiPost("entry", {
          action: "update",
          book_id: book.id,
          entry_id: entry.uid,
          enabled: Boolean(enabled),
        });
      }
      notify(`已批量${enabled ? "启用" : "停用"} ${targets.length} 条条目。`, "ok");
      await loadBook(book.id);
      await refreshOverviewSilently();
    } catch (error) {
      notify("批量操作失败：" + error.message, "error");
    } finally {
      if (btn) btn.disabled = !canWrite() || selectedEntryIds.size === 0;
    }
  }

  function exportCurrentBook() {
    if (!state.book) return;
    const book = state.book;
    const payload = {
      name: book.name,
      description: book.description || "",
      enabled: Boolean(book.enabled),
      auto_scenario: Boolean(book.auto_scenario),
      entries: (book.entries || []).map((e, idx) => ({
        uid: e.uid || String(idx),
        comment: e.name || e.comment || "",
        key: Array.isArray(e.keys) ? e.keys : [],
        keysecondary: Array.isArray(e.secondary_keys) ? e.secondary_keys : [],
        content: e.content || "",
        constant: Boolean(e.constant),
        selective: Boolean(e.selective),
        order: Number(e.priority) || 0,
        disable: !e.enabled,
        caseSensitive: Boolean(e.case_sensitive),
        matchWholeWords: Boolean(e.match_whole_word),
        scenarios: Array.isArray(e.scenarios) ? e.scenarios : [],
        behavior: e.behavior || "",
      })),
    };
    downloadJsonFile(`worldbook_${book.name || book.id}.json`, payload);
    notify(`已导出世界书「${book.name}」JSON。`, "ok");
  }

  async function onEntryAction(book, action, entryId) {
    if (!requireWrite()) return;
    const entry = (book.entries || []).find((item) => item.uid === entryId);
    if (!entry) return;
    try {
      if (action === "edit") {
        openEntryDrawer(entry);
        return;
      }
      if (action === "toggle") {
        await apiPost("entry", { action: "update", book_id: book.id, entry_id: entryId, enabled: !entry.enabled });
      } else if (action === "delete") {
        if (!window.confirm("确认删除条目「" + (entry.name || entry.uid) + "」？")) return;
        await apiPost("entry", { action: "delete", book_id: book.id, entry_id: entryId });
      } else if (action === "duplicate") {
        await apiPost("entry", { action: "duplicate", book_id: book.id, entry_id: entryId });
      } else if (action === "up" || action === "down") {
        await apiPost("entry", { action: "move", book_id: book.id, entry_id: entryId, direction: action });
      }
      await loadBook(book.id);
      await refreshOverviewSilently();
    } catch (error) {
      notify("操作失败：" + error.message, "error");
    }
  }

  async function saveBook() {
    if (!requireWrite() || !state.book) return;
    const payload = {
      action: "update",
      book_id: state.book.id,
      name: $("wbBookName").value.trim(),
      description: $("wbBookDesc").value.trim(),
      enabled: $("wbBookEnabled").checked,
      auto_scenario: $("wbBookAuto").checked,
    };
    try {
      const data = await apiPost("book", payload);
      state.book = data.book;
      notify("已保存世界书信息。", "ok");
      renderBookDetail();
      await refreshOverviewSilently();
    } catch (error) {
      notify("保存失败：" + error.message, "error");
    }
  }

  async function deleteBook() {
    if (!requireWrite() || !state.book) return;
    if (!window.confirm("删除世界书「" + state.book.name + "」及其全部条目？此操作不可撤销。")) return;
    try {
      await apiPost("book", { action: "delete", book_id: state.book.id });
      notify("已删除世界书。", "ok");
      state.bookId = "";
      state.book = null;
      await loadOverview();
      selectFirstBook();
    } catch (error) {
      notify("删除失败：" + error.message, "error");
    }
  }

  function renderBookDetail() {
    const host = $("wbBookDetail");
    const title = $("wbBookTitle");
    const actions = $("wbBookActions");
    if (!host) return;
    const book = state.book;
    if (!book) {
      if (title) title.textContent = "未选择世界书";
      if (actions) actions.innerHTML = "";
      host.innerHTML = `<div class="wb-empty" data-series-text="从左侧选择一本世界书。">从左侧选择一本世界书。</div>`;
      return;
    }
    if (title) title.textContent = book.name;
    const readOnly = canWrite() ? "" : " disabled";
    if (actions) {
      actions.innerHTML =
        `<button type="button" class="wb-button" id="wbAddEntry"${readOnly}>新增条目</button>` +
        `<button type="button" class="wb-button" id="wbExportBook">导出 JSON</button>` +
        `<button type="button" class="wb-button danger" id="wbDeleteBook"${readOnly}>删除世界书</button>`;
      const add = $("wbAddEntry");
      if (add) add.addEventListener("click", () => openEntryDrawer(null));
      const exp = $("wbExportBook");
      if (exp) exp.addEventListener("click", exportCurrentBook);
      const remove = $("wbDeleteBook");
      if (remove) remove.addEventListener("click", deleteBook);
    }
    const scenarioSet = new Set();
    for (const entry of book.entries || []) {
      for (const s of entry.scenarios || []) if (s) scenarioSet.add(s);
    }
    if (entryFilter.scenario && !scenarioSet.has(entryFilter.scenario)) {
      entryFilter.scenario = "";
    }
    const scenarioOpts =
      `<option value="">全部场景</option>` +
      Array.from(scenarioSet)
        .sort()
        .map(
          (s) =>
            `<option value="${escapeHtml(s)}"${entryFilter.scenario === s ? " selected" : ""}>${escapeHtml(s)}</option>`,
        )
        .join("");
    host.innerHTML =
      `<div class="wb-grid-2">` +
      `<label class="wb-field"><span data-series-text="名称">名称</span><input type="text" id="wbBookName" value="${escapeHtml(book.name)}"${readOnly} /></label>` +
      `<label class="wb-field"><span data-series-text="说明">说明</span><input type="text" id="wbBookDesc" value="${escapeHtml(book.description || "")}"${readOnly} /></label>` +
      `</div>` +
      `<div class="wb-row">` +
      `<div class="wb-check"><input type="checkbox" id="wbBookEnabled"${book.enabled ? " checked" : ""}${readOnly} /><label data-series-text="启用本书">启用本书</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbBookAuto"${book.auto_scenario ? " checked" : ""}${readOnly} /><label data-series-text="自动识别场景">自动识别场景</label></div>` +
      `<div class="wb-spacer"></div>` +
      `<button type="button" class="wb-button primary" id="wbSaveBook"${readOnly}>保存书籍信息</button>` +
      `</div>` +
      `<div class="wb-entry-toolbar">` +
      `<input type="search" id="wbEntrySearch" class="wb-entry-search" placeholder="搜索条目名 / 关键词 / 正文…" value="${escapeHtml(entryFilter.q)}" />` +
      `<select id="wbEntryConstFilter" aria-label="常驻筛选">` +
      `<option value="all"${entryFilter.constant === "all" ? " selected" : ""}>全部类型</option>` +
      `<option value="constant"${entryFilter.constant === "constant" ? " selected" : ""}>仅常驻</option>` +
      `<option value="keyword"${entryFilter.constant === "keyword" ? " selected" : ""}>仅关键词</option>` +
      `</select>` +
      `<select id="wbEntryEnabledFilter" aria-label="状态筛选">` +
      `<option value="all"${entryFilter.enabled === "all" ? " selected" : ""}>全部状态</option>` +
      `<option value="enabled"${entryFilter.enabled === "enabled" ? " selected" : ""}>仅启用</option>` +
      `<option value="disabled"${entryFilter.enabled === "disabled" ? " selected" : ""}>仅停用</option>` +
      `</select>` +
      `<select id="wbEntryScenarioFilter" aria-label="场景筛选">${scenarioOpts}</select>` +
      `<button type="button" class="wb-button tiny" id="wbBatchEnable"${readOnly}>批量启用</button>` +
      `<button type="button" class="wb-button tiny" id="wbBatchDisable"${readOnly}>批量停用</button>` +
      `<span class="wb-mono wb-entry-count" id="wbEntryFilterCount"></span>` +
      `</div>` +
      `<div id="wbEntryTableHost"></div>`;
    const save = $("wbSaveBook");
    if (save) save.addEventListener("click", saveBook);
    $("wbEntrySearch")?.addEventListener("input", (e) => {
      entryFilter.q = e.target.value || "";
      updateEntryTableView(book);
    });
    $("wbEntryConstFilter")?.addEventListener("change", (e) => {
      entryFilter.constant = e.target.value || "all";
      updateEntryTableView(book);
    });
    $("wbEntryEnabledFilter")?.addEventListener("change", (e) => {
      entryFilter.enabled = e.target.value || "all";
      updateEntryTableView(book);
    });
    $("wbEntryScenarioFilter")?.addEventListener("change", (e) => {
      entryFilter.scenario = e.target.value || "";
      updateEntryTableView(book);
    });
    $("wbBatchEnable")?.addEventListener("click", () => batchToggleEntries(book, true));
    $("wbBatchDisable")?.addEventListener("click", () => batchToggleEntries(book, false));
    updateEntryTableView(book);
  }

  function openCreateDrawer(kind) {
    if (!requireWrite()) return;
    const isBook = kind === "worldbook";
    const host = $("wbDrawerHost");
    const cardFields = isBook
      ? ""
      : CARD_TEXT_FIELDS.map(
          ([field, label, rows]) =>
            `<label class="wb-field"><span>${escapeHtml(label)}</span><textarea id="wbNewCard_${field}" rows="${rows}"></textarea></label>`,
        ).join("");
    const bookFields =
      `<label class="wb-field"><span data-series-text="说明">说明</span><input type="text" id="wbNewDesc" placeholder="可选" /></label>` +
      `<div class="wb-row">` +
      `<div class="wb-check"><input type="checkbox" id="wbNewEnabled" checked /><label data-series-text="启用本书">启用本书</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbNewAuto" checked /><label data-series-text="自动识别场景">自动识别场景</label></div>` +
      `</div>`;
    const cardExtra = isBook
      ? ""
      : `<label class="wb-field"><span data-series-text="标签（逗号分隔）">标签（逗号分隔）</span><input type="text" id="wbNewTags" placeholder="可选" /></label>`;
    host.innerHTML =
      `<div class="wb-drawer" id="wbDrawer"><div class="wb-drawer-inner">` +
      `<header><h2>${isBook ? "新建世界书" : "新建角色卡"}</h2>` +
      `<button type="button" class="wb-button tiny" id="wbDrawerClose" data-series-text="关闭">关闭</button></header>` +
      `<div class="wb-drawer-body">` +
      `<p class="wb-mono">${
        isBook
          ? "填个名字就能建，条目稍后在面板里一条条加，全程不用写 JSON。"
          : "直接把设定写进下面的框里就行，不用准备 JSON。留空的字段建好后还能在编辑页补。"
      }</p>` +
      `<label class="wb-field"><span>${isBook ? "世界书名称" : "角色卡名称"}</span>` +
      `<input type="text" id="wbNewName" placeholder="必填" /></label>` +
      (isBook ? bookFields : cardExtra + cardFields) +
      `</div>` +
      `<footer><button type="button" class="wb-button" id="wbDrawerCancel" data-series-text="取消">取消</button>` +
      `<button type="button" class="wb-button primary" id="wbDrawerSave" data-series-text="创建">创建</button></footer>` +
      `</div></div>`;
    const close = () => { host.innerHTML = ""; };
    $("wbDrawerClose").addEventListener("click", close);
    $("wbDrawerCancel").addEventListener("click", close);
    $("wbDrawer").addEventListener("click", (event) => { if (event.target.id === "wbDrawer") close(); });
    $("wbDrawerSave").addEventListener("click", () => submitCreate(kind, close));
    const nameInput = $("wbNewName");
    if (nameInput) nameInput.focus();
  }

  async function submitCreate(kind, close) {
    if (!requireWrite()) return;
    const name = $("wbNewName").value.trim();
    if (!name) {
      notify("名称不能为空。", "error");
      return;
    }
    try {
      if (kind === "worldbook") {
        const data = await apiPost("book", {
          action: "create",
          name,
          description: $("wbNewDesc").value.trim(),
          enabled: $("wbNewEnabled").checked,
          auto_scenario: $("wbNewAuto").checked,
        });
        state.bookId = data.book.id;
        state.book = data.book;
        close();
        await refreshOverviewSilently();
        setView("books");
        renderBookList();
        renderBookDetail();
        notify("世界书已创建，点右上角「新增条目」开始写内容。", "ok");
        return;
      }
      const payload = { action: "create", name, tags: splitList($("wbNewTags").value) };
      CARD_TEXT_FIELDS.forEach(([field]) => { payload[field] = $("wbNewCard_" + field).value; });
      const data = await apiPost("card", payload);
      state.cardId = data.card.id;
      state.card = data.card;
      close();
      await refreshOverviewSilently();
      setView("cards");
      renderCardList();
      renderCardDetail();
      notify("角色卡已创建。", "ok");
    } catch (error) {
      notify("创建失败：" + error.message, "error");
    }
  }

  function openImportDrawer(kind) {
    if (!requireWrite()) return;
    const isBook = kind === "worldbook";
    const host = $("wbDrawerHost");
    host.innerHTML =
      `<div class="wb-drawer" id="wbDrawer"><div class="wb-drawer-inner">` +
      `<header><h2>${isBook ? "导入世界书" : "导入角色卡"}</h2>` +
      `<button type="button" class="wb-button tiny" id="wbDrawerClose" data-series-text="关闭">关闭</button></header>` +
      `<div class="wb-drawer-body">` +
      `<p class="wb-mono">支持 SillyTavern 世界书 JSON、角色卡 V1/V2 JSON，以及 SillyTavern PNG 角色卡 V2（自动解析 chara 元数据块）。</p>` +
      `<label class="wb-field"><span>选择本地文件（.json / .png）</span><input type="file" id="wbImportFile" accept=".json,.png" /></label>` +
      `<p class="wb-mono" id="wbImportFileStatus"></p>` +
      `<label class="wb-field"><span data-series-text="名称（留空则用 JSON 里的名字）">名称（留空则用 JSON 里的名字）</span><input type="text" id="wbImportName" /></label>` +
      `<label class="wb-field"><span data-series-text="JSON 内容">JSON 内容</span><textarea id="wbImportText" rows="14" placeholder="粘贴 JSON 或从上方选择本地文件"></textarea></label>` +
      `<div class="wb-row"><div class="wb-check"><input type="checkbox" id="wbImportOverwrite" /><label data-series-text="同名时覆盖已有条目">同名时覆盖已有条目</label></div></div>` +
      `</div>` +
      `<footer><button type="button" class="wb-button" id="wbDrawerCancel" data-series-text="取消">取消</button>` +
      `<button type="button" class="wb-button primary" id="wbDrawerSave" data-series-text="导入">导入</button></footer>` +
      `</div></div>`;
    const close = () => { host.innerHTML = ""; };
    $("wbDrawerClose").addEventListener("click", close);
    $("wbDrawerCancel").addEventListener("click", close);
    $("wbDrawer").addEventListener("click", (event) => { if (event.target.id === "wbDrawer") close(); });
    $("wbImportFile")?.addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      const status = $("wbImportFileStatus");
      if (!file) return;
      try {
        let jsonText = "";
        if (file.name.toLowerCase().endsWith(".png") || file.type === "image/png") {
          const buf = await file.arrayBuffer();
          jsonText = parsePngCharaChunk(buf);
          if (status) status.textContent = `已从 PNG 角色卡「${file.name}」解析出 chara 元数据。`;
        } else {
          jsonText = await file.text();
          if (status) status.textContent = `已载入 JSON 文件「${file.name}」。`;
        }
        $("wbImportText").value = jsonText;
        const nameInput = $("wbImportName");
        if (nameInput && !nameInput.value.trim()) {
          try {
            const parsed = JSON.parse(jsonText);
            const autoName = parsed?.data?.name || parsed?.name || "";
            if (autoName) nameInput.value = String(autoName);
          } catch {}
        }
      } catch (err) {
        if (status) status.textContent = `读取失败：${err.message || err}`;
        notify("文件解析失败：" + (err.message || err), "error");
      }
    });
    $("wbDrawerSave").addEventListener("click", () => submitImport(kind, close));
  }

  async function submitImport(kind, close) {
    const text = $("wbImportText").value.trim();
    if (!text) {
      notify("请先粘贴 JSON 内容。", "error");
      return;
    }
    try {
      const data = await apiPost("import", {
        kind,
        name: $("wbImportName").value.trim(),
        text,
        overwrite: $("wbImportOverwrite").checked,
      });
      close();
      if (kind === "worldbook") {
        state.bookId = data.book.id;
        state.book = data.book;
        await refreshOverviewSilently();
        setView("books");
        renderBookList();
        renderBookDetail();
      } else {
        state.cardId = data.card.id;
        state.card = data.card;
        await refreshOverviewSilently();
        setView("cards");
        renderCardList();
        renderCardDetail();
      }
      notify("导入成功。", "ok");
    } catch (error) {
      notify("导入失败：" + error.message, "error");
    }
  }

  function openEntryDrawer(entry) {
    const book = state.book;
    if (!book) return;
    const editing = Boolean(entry);
    const value = entry || {
      name: "",
      keys: [],
      secondary_keys: [],
      content: "",
      behavior: "",
      scenarios: [],
      constant: false,
      enabled: true,
      priority: 100,
      case_sensitive: false,
      match_whole_word: false,
      selective: false,
      comment: "",
    };
    const host = $("wbDrawerHost");
    host.innerHTML =
      `<div class="wb-drawer" id="wbDrawer"><div class="wb-drawer-inner">` +
      `<header><h2>${editing ? "编辑条目" : "新增条目"}</h2>` +
      `<button type="button" class="wb-button tiny" id="wbDrawerClose" data-series-text="关闭">关闭</button></header>` +
      `<div class="wb-drawer-body">` +
      `<label class="wb-field"><span data-series-text="条目名称">条目名称</span><input type="text" id="wbEName" value="${escapeHtml(value.name || "")}" placeholder="留空则显示前三个关键词" /></label>` +
      `<label class="wb-field"><span data-series-text="主关键词（逗号或换行分隔）">主关键词（逗号或换行分隔）</span><textarea id="wbEKeys" rows="2">${escapeHtml(listToText(value.keys))}</textarea><span class="hint" data-series-text="留空且勾选「常驻」时，该条目在任何场景都会注入。">留空且勾选「常驻」时，该条目在任何场景都会注入。</span></label>` +
      `<label class="wb-field"><span data-series-text="次关键词（需同时命中）">次关键词（需同时命中）</span><textarea id="wbESecondary" rows="2">${escapeHtml(listToText(value.secondary_keys))}</textarea></label>` +
      `<label class="wb-field"><span data-series-text="绑定场景（逗号或换行分隔）">绑定场景（逗号或换行分隔）</span><textarea id="wbEScenarios" rows="2">${escapeHtml(listToText(value.scenarios))}</textarea></label>` +
      `<label class="wb-field"><span data-series-text="行为变化">行为变化</span><textarea id="wbEBehavior" rows="3">${escapeHtml(value.behavior || "")}</textarea><span class="hint" data-series-text="命中后角色应有的语气/行为变化，会作为「行为变化」行注入。">命中后角色应有的语气/行为变化，会作为「行为变化」行注入。</span></label>` +
      `<label class="wb-field"><span data-series-text="正文">正文</span><textarea id="wbEContent" rows="10">${escapeHtml(value.content || "")}</textarea></label>` +
      `<div class="wb-grid-2">` +
      `<label class="wb-field"><span data-series-text="优先级（越大越优先）">优先级（越大越优先）</span><input type="number" id="wbEPriority" value="${escapeHtml(value.priority)}" /></label>` +
      `<label class="wb-field"><span data-series-text="备注">备注</span><input type="text" id="wbEComment" value="${escapeHtml(value.comment || "")}" /></label>` +
      `</div>` +
      `<div class="wb-row">` +
      `<div class="wb-check"><input type="checkbox" id="wbEConstant"${value.constant ? " checked" : ""} /><label data-series-text="常驻（不依赖关键词）">常驻（不依赖关键词）</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbEEnabled"${value.enabled ? " checked" : ""} /><label data-series-text="启用">启用</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbECase"${value.case_sensitive ? " checked" : ""} /><label data-series-text="区分大小写">区分大小写</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbEWhole"${value.match_whole_word ? " checked" : ""} /><label data-series-text="全词匹配">全词匹配</label></div>` +
      `<div class="wb-check"><input type="checkbox" id="wbESelective"${value.selective ? " checked" : ""} /><label data-series-text="需要次关键词">需要次关键词</label></div>` +
      `</div>` +
      `</div>` +
      `<footer><button type="button" class="wb-button" id="wbDrawerCancel" data-series-text="取消">取消</button>` +
      `<button type="button" class="wb-button primary" id="wbDrawerSave" data-series-text="保存">保存</button></footer>` +
      `</div></div>`;
    const close = () => { host.innerHTML = ""; };
    $("wbDrawerClose").addEventListener("click", close);
    $("wbDrawerCancel").addEventListener("click", close);
    $("wbDrawer").addEventListener("click", (event) => { if (event.target.id === "wbDrawer") close(); });
    $("wbDrawerSave").addEventListener("click", () => saveEntry(editing ? entry.uid : "", close));
  }

  async function saveEntry(entryId, close) {
    if (!requireWrite() || !state.book) return;
    const payload = {
      action: entryId ? "update" : "create",
      book_id: state.book.id,
      name: $("wbEName").value.trim(),
      keys: splitList($("wbEKeys").value),
      secondary_keys: splitList($("wbESecondary").value),
      scenarios: splitList($("wbEScenarios").value),
      behavior: $("wbEBehavior").value,
      content: $("wbEContent").value,
      priority: Number($("wbEPriority").value) || 0,
      comment: $("wbEComment").value.trim(),
      constant: $("wbEConstant").checked,
      enabled: $("wbEEnabled").checked,
      case_sensitive: $("wbECase").checked,
      match_whole_word: $("wbEWhole").checked,
      selective: $("wbESelective").checked,
    };
    if (entryId) payload.entry_id = entryId;
    try {
      await apiPost("entry", payload);
      notify("条目已保存。", "ok");
      close();
      await loadBook(state.book.id);
      await refreshOverviewSilently();
    } catch (error) {
      notify("保存条目失败：" + error.message, "error");
    }
  }

  function selectFirstCard() {
    const cards = (state.overview && state.overview.cards) || [];
    if (cards.length) loadCard(cards[0].id);
    else renderCardDetail();
  }

  function renderCardList() {
    const host = $("wbCardList");
    if (!host || !state.overview) return;
    const cards = state.overview.cards || [];
    const badge = $("wbDefaultCard");
    if (badge) {
      const found = cards.find((card) => card.id === state.overview.default_card_id);
      badge.textContent = found ? "默认：" + found.name : "未设置默认";
    }
    if (!cards.length) {
      host.innerHTML = `<li><div class="wb-empty" data-series-text="还没有角色卡，点右上角「导入 JSON」粘贴 SillyTavern 角色卡。">还没有角色卡，点右上角「导入 JSON」粘贴 SillyTavern 角色卡。</div></li>`;
      return;
    }
    host.innerHTML = cards
      .map(
        (card) =>
          `<li><button type="button" class="wb-list-item" data-card="${escapeHtml(
            card.id,
          )}" aria-current="${String(card.id === state.cardId)}"><strong>${escapeHtml(
            card.name,
          )}${card.id === state.overview.default_card_id ? " · 默认" : ""}</strong><small>${escapeHtml(
            card.source || "plugin",
          )} · ${card.has_group_addendum ? "含群聊适配层" : "无群聊适配层"}</small></button></li>`,
      )
      .join("");
    host.querySelectorAll("button[data-card]").forEach((button) => {
      button.addEventListener("click", () => loadCard(button.dataset.card));
    });
  }

  async function loadCard(cardId) {
    if (!cardId) return;
    state.cardId = cardId;
    renderCardList();
    try {
      const data = await apiGet("card", { card_id: cardId });
      state.card = data.card;
    } catch (error) {
      state.card = null;
      notify("读取角色卡失败：" + error.message, "error");
    }
    renderCardDetail();
  }

  function renderBookOptions(selected) {
    const books = (state.overview && state.overview.books) || [];
    const current = String(selected || "");
    const known = books.some((book) => book.id === current);
    const head = `<option value=""${current ? "" : " selected"}>（不关联）</option>`;
    const extra =
      current && !known
        ? `<option value="${escapeHtml(current)}" selected>${escapeHtml(current)}（已失效）</option>`
        : "";
    return (
      head +
      extra +
      books
        .map(
          (book) =>
            `<option value="${escapeHtml(book.id)}"${book.id === current ? " selected" : ""}>${escapeHtml(
              book.name,
            )}</option>`,
        )
        .join("")
    );
  }

  async function saveCard() {
    if (!requireWrite() || !state.card) return;
    const payload = {
      action: "update",
      card_id: state.card.id,
      name: $("wbCardName").value.trim(),
      tags: splitList($("wbCardTags").value),
      linked_book_id: $("wbCardBook").value,
    };
    CARD_TEXT_FIELDS.forEach(([field]) => { payload[field] = $("wbCard_" + field).value; });
    try {
      const data = await apiPost("card", payload);
      state.card = data.card;
      notify("已保存角色卡。", "ok");
      renderCardDetail();
      await refreshOverviewSilently();
    } catch (error) {
      notify("保存角色卡失败：" + error.message, "error");
    }
  }

  async function setDefaultCard() {
    if (!requireWrite() || !state.card) return;
    try {
      await apiPost("card", { action: "set_default", card_id: state.card.id });
      notify("已设为全局默认角色卡。", "ok");
      await loadOverview();
    } catch (error) {
      notify("设置默认失败：" + error.message, "error");
    }
  }

  async function deleteCard() {
    if (!requireWrite() || !state.card) return;
    if (!window.confirm("删除角色卡「" + state.card.name + "」？")) return;
    try {
      await apiPost("card", { action: "delete", card_id: state.card.id });
      notify("已删除角色卡。", "ok");
      state.cardId = "";
      state.card = null;
      await loadOverview();
      selectFirstCard();
    } catch (error) {
      notify("删除失败：" + error.message, "error");
    }
  }

  function exportCurrentCard() {
    if (!state.card) return;
    const card = state.card;
    const payload = {
      spec: "chara_card_v2",
      spec_version: "2.0",
      data: {
        name: card.name || "",
        description: card.description || "",
        personality: card.personality || "",
        scenario: card.scenario || "",
        first_mes: card.first_mes || "",
        mes_example: card.mes_example || "",
        system_prompt: card.system_prompt || "",
        post_history_instructions: card.post_history_instructions || "",
        tags: Array.isArray(card.tags) ? card.tags : [],
        extensions: {
          astrbot_dynamics_world: {
            group_addendum: card.group_addendum || "",
            linked_book_id: card.linked_book_id || "",
          },
        },
      },
    };
    downloadJsonFile(`character_${card.name || card.id}.json`, payload);
    notify(`已导出角色卡「${card.name}」JSON。`, "ok");
  }

  function renderCardDetail() {
    const host = $("wbCardDetail");
    const title = $("wbCardTitle");
    const actions = $("wbCardActions");
    if (!host) return;
    const card = state.card;
    if (!card) {
      if (title) title.textContent = "未选择角色卡";
      if (actions) actions.innerHTML = "";
      host.innerHTML = `<div class="wb-empty" data-series-text="从左侧选择一张角色卡。">从左侧选择一张角色卡。</div>`;
      return;
    }
    if (title) title.textContent = card.name;
    const readOnly = canWrite() ? "" : " disabled";
    const isDefault = state.overview && state.overview.default_card_id === card.id;
    if (actions) {
      actions.innerHTML =
        `<button type="button" class="wb-button" id="wbSetDefaultCard"${readOnly}${isDefault ? " disabled" : ""}>${
          isDefault ? "已是默认" : "设为默认"
        }</button>` +
        `<button type="button" class="wb-button" id="wbExportCard">导出 JSON</button>` +
        `<button type="button" class="wb-button danger" id="wbDeleteCard"${readOnly}>删除角色卡</button>`;
      const setDefault = $("wbSetDefaultCard");
      if (setDefault) setDefault.addEventListener("click", setDefaultCard);
      const expCard = $("wbExportCard");
      if (expCard) expCard.addEventListener("click", exportCurrentCard);
      const remove = $("wbDeleteCard");
      if (remove) remove.addEventListener("click", deleteCard);
    }
    host.innerHTML =
      `<div class="wb-grid-2">` +
      `<label class="wb-field"><span data-series-text="名称">名称</span><input type="text" id="wbCardName" value="${escapeHtml(card.name)}"${readOnly} /></label>` +
      `<label class="wb-field"><span data-series-text="标签（逗号分隔）">标签（逗号分隔）</span><input type="text" id="wbCardTags" value="${escapeHtml(listToText(card.tags))}"${readOnly} /></label>` +
      `</div>` +
      `<div class="wb-field"><span>AstrBot 人格：${escapeHtml(card.persona_id || "尚未同步")}</span><button class="wb-button tiny" id="dwSyncPersona"${readOnly}>同步角色设定到人格</button></div>` +
      `<label class="wb-field"><span data-series-text="关联世界书">关联世界书</span><select id="wbCardBook"${readOnly}>${renderBookOptions(card.linked_book_id)}</select></label>` +
      CARD_TEXT_FIELDS.map(
        ([field, label, rows]) =>
          `<label class="wb-field"><span>${escapeHtml(label)}</span><textarea id="wbCard_${field}" rows="${rows}"${readOnly}>${escapeHtml(
            card[field] || "",
          )}</textarea></label>`,
      ).join("") +
      `<div class="wb-row end"><button type="button" class="wb-button primary" id="wbSaveCard"${readOnly}>保存角色卡</button></div>`;
    const save = $("wbSaveCard");
    if (save) save.addEventListener("click", saveCard);
    const sync = $("dwSyncPersona");
    if (sync) {
      sync.addEventListener("click", async () => {
        if (!requireWrite()) return;
        sync.disabled = true;
        try {
          const result = await apiPost("persona", { card_id: card.id });
          notify(result.message);
          await loadCard(card.id);
        } catch (error) {
          notify(error.message, "error");
        } finally {
          sync.disabled = false;
        }
      });
    }
  }

  async function sessionAction(payload) {
    if (!requireWrite()) return;
    try {
      await apiPost("session", payload);
      notify("会话状态已更新。", "ok");
      await loadOverview();
    } catch (error) {
      notify("会话更新失败：" + error.message, "error");
    }
  }

  async function forgetSession(sessionId) {
    if (!requireWrite()) return;
    if (!window.confirm("清除该会话的世界书状态（开关、场景、绑定、角色卡）？")) return;
    await sessionAction({ action: "forget", session_id: sessionId });
  }

  function renderSessionTable() {
    const host = $("wbSessionTable");
    if (!host || !state.overview) return;
    const rows = state.overview.sessions || [];
    const scenarios = state.overview.scenarios || [];
    const books = state.overview.books || [];
    const cards = state.overview.cards || [];
    if (!rows.length) {
      host.innerHTML = `<div class="wb-empty" data-series-text="还没有会话记录。">还没有会话记录。</div>`;
      return;
    }
    const readOnly = canWrite() ? "" : " disabled";
    const scenarioOptions = (selected) =>
      `<option value="" data-series-text="（不锁定）">（不锁定）</option>` +
      scenarios
        .map((name) => `<option value="${escapeHtml(name)}"${name === selected ? " selected" : ""}>${escapeHtml(name)}</option>`)
        .join("");
    const cardOptions = (selected) =>
      `<option value="" data-series-text="（跟随默认）">（跟随默认）</option><option value="__none__"${selected === "__none__" ? " selected" : ""}>（关闭角色卡）</option>` +
      cards
        .map((card) => `<option value="${escapeHtml(card.id)}"${card.id === selected ? " selected" : ""}>${escapeHtml(card.name)}</option>`)
        .join("");
    host.innerHTML =
      `<table class="wb-table"><thead><tr><th data-series-text="会话">会话</th><th data-series-text="注入">注入</th><th data-series-text="场景">场景</th><th data-series-text="自动识别">自动识别</th><th data-series-text="角色卡">角色卡</th><th data-series-text="绑定世界书">绑定世界书</th><th data-series-text="最近活动">最近活动</th><th></th></tr></thead><tbody>` +
      rows
        .map(
          (row) =>
            `<tr data-session="${escapeHtml(row.session_id)}">` +
            `<td class="wb-mono">${escapeHtml(shortId(row.session_id))}</td>` +
            `<td><button type="button" class="wb-button tiny" data-sact="toggle"${readOnly}>${row.enabled ? "开启" : tr("关闭")}</button></td>` +
            `<td><select data-sact="scenario"${readOnly}>${scenarioOptions(row.scenario)}</select></td>` +
            `<td>${escapeHtml(row.scenario_auto || "—")}</td>` +
            `<td><select data-sact="card"${readOnly}>${cardOptions(row.card_id)}</select></td>` +
            `<td><div class="wb-book-chips" data-sact="books">${
              books.length
                ? books
                    .map((book) => {
                      const checked = (row.book_ids || []).includes(book.id);
                      return `<label class="wb-book-chip${checked ? " is-checked" : ""}"><input type="checkbox" value="${escapeHtml(
                        book.id,
                      )}"${checked ? " checked" : ""}${readOnly} /><span>${escapeHtml(book.name)}</span></label>`;
                    })
                    .join("")
                : '<span class="wb-mono">暂无世界书</span>'
            }</div></td>` +
            `<td class="wb-nowrap">${escapeHtml(formatTs(row.last_active))}</td>` +
            `<td class="actions"><button type="button" class="wb-button tiny danger" data-sact="forget"${readOnly}>清除</button></td>` +
            `</tr>`,
        )
        .join("") +
      `</tbody></table>`;
    host.querySelectorAll("tr[data-session]").forEach((tr) => {
      const sessionId = tr.dataset.session;
      tr.querySelectorAll("[data-sact]").forEach((control) => {
        const act = control.dataset.sact;
        if (act === "toggle" || act === "forget") {
          control.addEventListener("click", () => {
            if (act === "forget") return forgetSession(sessionId);
            const row = rows.find((item) => item.session_id === sessionId);
            return sessionAction({ action: row && row.enabled ? "disable" : "enable", session_id: sessionId });
          });
        } else {
          control.addEventListener("change", () => {
            if (act === "scenario") {
              const value = control.value;
              return sessionAction({ action: value ? "set_scenario" : "clear_scenario", session_id: sessionId, scenario: value });
            }
            if (act === "card") {
              return sessionAction({ action: "set_card", session_id: sessionId, card_id: control.value });
            }
            if (act === "books") {
              const ids = Array.from(control.querySelectorAll('input[type="checkbox"]:checked')).map(
                (box) => box.value,
              );
              return sessionAction({ action: "bind_books", session_id: sessionId, book_ids: ids });
            }
            return undefined;
          });
        }
      });
    });
  }

  return {
    selectFirstBook,
    renderBookList,
    loadBook,
    renderBookDetail,
    openCreateDrawer,
    openImportDrawer,
    selectFirstCard,
    renderCardList,
    loadCard,
    renderCardDetail,
    renderSessionTable,
  };
}
