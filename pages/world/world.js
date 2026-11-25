import { apiGet, apiPost, escapeHtml as esc, formatTs, setSeriesTimezone } from "./api.js";
import { getSharedScope, msg, setSharedScope, setText, tr } from "./series-ui.js";
import { worldStream } from "./world-stream.js?v=round2.1";

const $ = (id) => document.getElementById(id);
window.DynamicsGetActiveScope = () => $("dwScope")?.value?.trim() || "";
let preview = null;
let lifeSerial = 0;
let scopeInitialized = false;
let currentWorld = null;
let currentLife = null;
const lifePanels = ["dwLifeSummary", "dwOverviewLife", "dwPlan", "dwDiary", "dwCommitments", "dwIntents"];
const labels = { observation: "已记录经历", user_claim: "用户陈述", fiction: "虚构生活", subjective: "主观感受", plan: "计划", receipt: "发送回执", available: "空闲", busy: "忙碌", asleep: "睡眠", unknown: "未知", proposed: "待确认", committed: "已约定", conditional: "有条件", completed: "已完成", cancelled: "已取消", expired: "已过期", pending: "待处理", claimed: "处理中", sent: "已送达", failed: "失败", uncertain: "结果待核实" };
const counts = {legacy_history:"历史作息",cards:"角色",books:"世界书",sessions:"会话绑定",entries:"设定条目",lives:"生活实例",scopes:"生活会话",events:"事件",diary:"日记",commitments:"约定",intents:"联系动机"};
const tag = (value) => `<span class="wb-tag">${esc(labels[value] ? tr(labels[value]) : (value || tr("未知")))}</span>`;
function notice(text, error=false) {
  const node = $("wbNotice"); node.textContent = text;
  node.className = "wb-notice" + (error ? " error" : "");
}
function items(values, render, empty) {
  return values?.length ? values.map(x=>`<article class="dw-item">${render(x)}</article>`).join("") : `<div class="wb-empty">${esc(empty)}</div>`;
}
function renderRuntime(data) {
  setText($("dwRuntime"), msg(data.ready ? "聊天接入已开启" : data.conflicts.length && data.runtime_enabled ? "等待旧插件停用" : "编辑模式"));
  $("dwRuntimeHint").textContent = data.ready ? tr("角色与生活由群间世界统一维护，回复由 Chat Dynamics 调度。") : data.conflicts.length ? tr("检测到旧世界书或动态生活仍启用；预览与编辑可继续。") : tr("可以先建立世界，准备好后再开启聊天接入。");
  if(data.compatibility?.chat_dynamics?.state!=='ready')$('dwRuntimeHint').textContent+=tr(' 配套聊天能力尚未确认，请打开“安装引导”检查。');
}
export async function refreshWorld() {
  try {
    const data = await apiGet("world");
    if (data?.timezone) setSeriesTimezone(data.timezone);
    currentWorld = data;
    renderRuntime(data);
    $("dwScopes").innerHTML = data.sessions.map(x=>`<option value="${esc(x)}"></option>`).join("");
    $("dwApplySettings").disabled = !data.settings_import_available || data.runtime_enabled;
    if (!scopeInitialized && !$("dwScope").value) {
      const bridge = (window.DynamicsPanelBridge || window.AstrBotPluginPage || window.AstrBotPluginView);
      const explicitScope = new URLSearchParams(location.search).has("umo") || bridge?.getContext?.()?.scope === "";
      const shared = getSharedScope();
      const picked = explicitScope || shared ? shared : (data.sessions[0] || "");
      if (picked) {
        $("dwScope").value = picked;
        if (!explicitScope && !shared) setSharedScope(picked, { emit: false });
        document.dispatchEvent(new Event('world-scope-ready'));
      }
    }
    scopeInitialized = true;
    if ($("dwScope").value) await refreshLife();
  } catch (error) { notice(tr("读取世界状态失败：")+error.message,true); }
}

export async function refreshLife() {
  const umo = $("dwScope").value.trim();
  const serial = ++lifeSerial;
  if (currentLife?.umo !== umo) currentLife = null;
  if (!umo) {
    for (const id of lifePanels) {
      const node = $(id);
      if (node) node.innerHTML = '<div class="wb-empty" data-series-text="请先选择会话。">请先选择会话。</div>';
    }
    const planCard = $("dwPlanCard");
    if (planCard) planCard.hidden = true;
    const planNode = $("dwPlan");
    if (planNode) planNode.innerHTML = "";
    document.querySelectorAll("[data-life-action], #dwCorrect, #dwRegenPlan").forEach(x=>x.disabled=true);
    return;
  }
  try {
    const data = await apiGet("life", {umo});
    if (serial !== lifeSerial || umo !== $("dwScope").value.trim()) return;
    if (data?.timezone) setSeriesTimezone(data.timezone);
    currentLife = {umo,data};
    renderLife(data);
  } catch (error) {
    if (serial === lifeSerial) {
      currentLife = null;
      const message = `<div class="wb-empty">${esc(error.message)}</div>`;
      lifePanels.forEach(id=>{ const node = $(id); if (node) node.innerHTML = message; });
      const planCard = $("dwPlanCard");
      if (planCard) planCard.hidden = true;
      const planNode = $("dwPlan");
      if (planNode) planNode.innerHTML = "";
      document.querySelectorAll("[data-life-action], #dwCorrect, #dwRegenPlan").forEach(x=>x.disabled=true);
      notice(tr("读取生活失败：")+error.message,true);
    }
  }
}

function renderPlanStatusBanner(data) {
    const ps = data.plan_status;
    if (!ps || ps.status === "ready") return "";
    const failed = ps.status === "failed";
    const generating = ps.status === "generating";
    const tone = failed ? "error" : "warning";
    const title = generating
      ? tr("今日日程正在重新生成中…")
      : failed
      ? tr("今日日程生成失败")
      : tr("今日日程尚未生成");
    const bits = [];
    if (ps.last_attempt_at) bits.push(tr("最近尝试 ") + formatTs(ps.last_attempt_at));
    if (ps.last_attempt_status && ps.last_attempt_status !== "advanced") bits.push(ps.last_attempt_status);
    if (ps.last_error) bits.push(ps.last_error);
    if (ps.plan_date && ps.today && ps.plan_date !== ps.today) {
      bits.push(tr("当前显示的是 {0} 的旧安排", ps.plan_date));
    }
    const detail = bits.length ? `<p class="dw-meta">${esc(bits.join(" · "))}</p>` : "";
    const btnText = generating ? tr("生成中…") : failed ? tr("重新生成今日日程") : tr("生成今日日程");
    const disabled = generating || data.paused || (!data.managed && !data.legacy) ? "disabled" : "";
    return `<div class="dw-plan-banner is-${tone}" role="status"><div><strong>${esc(title)}</strong>${detail}</div><button class="wb-button primary tiny" type="button" data-regen-plan="true" ${disabled}>${esc(btnText)}</button></div>`;
}

function renderLife(data) {
    const s = data.snapshot || {};
    // Weather is appended by EnvironmentService for older clients. Keep it out
    // of the activity heading and render the current structured values separately.
    const activity = String(s.activity || tr("尚无当前活动")).split("；环境参考（")[0];
    const environment = s.environment, current = environment?.current;
    const weather = environment?.available && current ? `<div class="dw-hero-weather"><span>${environment.stale ? tr("上次天气 · 已过期") : tr("天气参考")}</span><strong>${esc(current.label || tr("天气待确认"))}${typeof current.temperature === "number" ? " · "+esc(current.temperature)+"℃" : ""}${typeof current.is_day === "boolean" ? current.is_day ? tr(" · 白天") : tr(" · 夜间") : ""}</strong><small>${esc(environment.location || tr("角色世界"))}</small></div>` : "";
    const summary = `<div class="dw-hero-copy"><h2>${esc(data.character?.name || tr("角色"))} · ${esc(activity)}</h2><p>${esc(data.character?.scenario || tr("尚未设置场景"))} ${tag(s.availability || "unknown")}${data.paused ? tag(tr("生活已暂停")) : ""}</p><p>${esc(s.summary || s.subjective_state || (data.managed ? tr("等待新的生活记录。") : tr("本会话尚未启用持续生活，请检查角色与会话范围配置。")))}</p></div>${weather}`;
    $("dwLifeSummary").innerHTML = summary;
    $("dwOverviewLife").innerHTML = summary;
    const planStatus = data.plan_status || null;
    const showPlanFallback = Boolean(data.legacy) || Boolean(planStatus && planStatus.status !== "ready");
    const planCard = $("dwPlanCard");
    if (planCard) planCard.hidden = !showPlanFallback;
    const planNode = $("dwPlan");
    if (planNode) {
      if (showPlanFallback) {
        const planBanner = renderPlanStatusBanner(data);
        planNode.innerHTML = planBanner + (data.legacy ? `<pre class="wb-pre">${esc(data.legacy.text)}</pre>` : "");
      } else {
        planNode.innerHTML = "";
      }
    }
    $("dwDiary").innerHTML = items(data.diary,x=>`${tag(x.fact_kind)} <span class="dw-meta">${esc(formatTs(x.occurred))}</span><p>${esc(x.text)}</p>`,tr("还没有生活故事。"));
    $("dwCommitments").innerHTML = items(s.commitments,x=>`${tag(x.status)}<p>${esc(x.description)}</p><span class="dw-meta">${x.due_at ? esc(formatTs(x.due_at)) : tr("未指定时间")}</span>`,tr("当前没有约定。"));
    $("dwIntents").innerHTML = items(data.intents,x=>`${tag(x.status)}<p>${esc(x.reason || x.motivation || x.topic || tr("联系动机"))}</p>${["pending","failed"].includes(x.status) ? `<button class="wb-button tiny" data-cancel-intent="${esc(x.intent_id)}" data-series-text="取消联系">取消联系</button>`:""}`,tr("当前没有待联系事项。"));
    document.querySelectorAll("[data-life-action], #dwCorrect").forEach(x=>x.disabled=!data.managed);
    const regenBtn = $("dwRegenPlan");
    if (regenBtn) regenBtn.disabled = (!data.managed && !data.legacy) || Boolean(data.paused) || Boolean(data.plan_status?.generating);
}
window.addEventListener("series-languagechange",()=>{
  if (currentWorld) renderRuntime(currentWorld);
  if (currentLife && currentLife.umo === $("dwScope").value.trim()) renderLife(currentLife.data);
});

async function action(button, work) {
  button.disabled=true;
  try { await work(); } catch (error) { notice(error.message,true); }
  finally { button.disabled=false; }
}
function applyScope(){
  scopeInitialized = true;
  setSharedScope($("dwScope").value.trim());
  document.dispatchEvent(new Event("world-scope-ready"));
  void refreshLife();
}
$("dwLoad").addEventListener("click",applyScope);
$("dwScope").addEventListener("change",applyScope);
window.addEventListener("dynamics-scopechange",(event)=>{
  const next = String(event.detail?.umo || "").trim();
  scopeInitialized = true;
  if ($("dwScope").value.trim() !== next) {
    $("dwScope").value = next;
    document.dispatchEvent(new Event("world-scope-ready"));
    void refreshLife();
  }
});
document.querySelectorAll("[data-life-action]").forEach(button=>button.addEventListener("click",()=>action(button, async()=>{
  await apiPost("life",{action:button.dataset.lifeAction,umo:$("dwScope").value.trim()});
  notice(tr("生活设置已更新。"));await refreshLife();
})));
$("dwCorrect").addEventListener("click",()=>action($("dwCorrect"),async()=>{
  const activity = $("dwActivity").value.trim();
  if (!activity) throw new Error(tr("请填写当前活动。"));
  await apiPost("life",{action:"correct",umo:$("dwScope").value.trim(),patch:{activity,availability:$("dwAvailability").value}});
  notice(tr("已记录纠正。"));await refreshLife();
}));
$("dwIntents").addEventListener("click",event=>{
  const button = event.target.closest("[data-cancel-intent]");if (!button) return;
  action(button,async()=>{await apiPost("life",{action:"cancel_intent",umo:$("dwScope").value.trim(),intent_id:button.dataset.cancelIntent});await refreshLife();});
});
async function triggerRegenPlan(button) {
  const umo = $("dwScope").value.trim();
  if (!umo) return;
  const targets = [button, $("dwRegenPlan"), ...document.querySelectorAll("#dwPlan [data-regen-plan]")].filter(Boolean);
  targets.forEach(b => { b.disabled = true; });
  notice(tr("正在保留已发生历史并重新生成今日日程…"));
  try {
    const res = await apiPost("life", { action: "regenerate_plan", umo });
    notice(tr("今日日程已重新生成（{0} 项安排）。", res?.count ?? (res?.daily_plan?.length || 0)));
  } catch (error) {
    notice(tr("日程重新生成失败：") + error.message, true);
  } finally {
    await Promise.allSettled([refreshLife(), worldStream.refreshNow({ fresh: true })]);
  }
}
$("dwRegenPlan")?.addEventListener("click", () => void triggerRegenPlan($("dwRegenPlan")));
$("dwPlan")?.addEventListener("click", event => {
  const button = event.target.closest("[data-regen-plan]");
  if (!button) return;
  void triggerRegenPlan(button);
});
$("dwPreviewMigration").addEventListener("click",()=>action($("dwPreviewMigration"),async()=>{
  preview=null;$("dwImportMigration").disabled=true;
  preview=await apiGet("migration");
  $("dwMigrationReport").innerHTML=`<div class="wb-stats">${Object.entries(preview.counts).map(([k,v])=>`<div class="wb-stat"><strong>${esc(v)}</strong><span>${esc(counts[k]?tr(counts[k]):k)}</span></div>`).join("")}</div><p>${preview.already_imported ? tr("这一份数据已经导入。") : preview.has_data ? tr("旧数据将保持原样，导入结果单独保存。") : tr("没有发现可迁移的数据。")}</p>${items(preview.conflicts,x=>`<p>${esc(x)}</p>`,tr("未发现目标数据冲突。"))}`;
  $("dwImportMigration").disabled=!preview.has_data || preview.conflicts.length>0 || preview.already_imported;
}));
$("dwImportMigration").addEventListener("click",()=>action($("dwImportMigration"),async()=>{
  if (!preview) throw new Error(tr("请先预览迁移。"));
  await apiPost("migration",{action:"import",fingerprint:preview.fingerprint});preview=null;
  $("dwMigrationReport").textContent=tr("导入完成。可应用迁入的配置，再检查角色和生活记录。原插件数据保持不变。");
  notice(tr("旧数据已导入，聊天接入仍保持关闭。")); await refreshWorld();
  $("wbRefresh").click();
  setTimeout(()=>$("dwImportMigration").disabled=true,0);
}));
$("dwApplySettings").addEventListener("click",()=>action($("dwApplySettings"),async()=>{
  await apiPost("migration",{action:"apply_settings"});notice(tr("已应用原有配置，聊天接入仍关闭。停用旧插件后可开启接入。"));await refreshWorld();
}));
