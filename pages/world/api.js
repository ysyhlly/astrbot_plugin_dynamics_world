/** Shared helpers for the Worldbook plugin page. */

import {getLanguage} from './series-ui.js';

export const PLUGIN = "astrbot_plugin_dynamics_world";
export const REQUEST_TIMEOUT_MS = 12000;

function ensureBridge() {
  return (window.DynamicsPanelBridge || window.AstrBotPluginPage || window.AstrBotPluginView) || null;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function unwrap(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("空响应");
  }
  if (payload.status === "error" || payload.ok === false) {
    throw new Error(payload.error || payload.message || "请求失败");
  }
  return payload.data !== undefined ? payload.data : payload;
}

export function withTimeout(promise, timeoutMs = REQUEST_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("请求超时")), timeoutMs);
    Promise.resolve(promise).then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

export async function apiGet(endpoint, params = {}) {
  const active = ensureBridge();
  if (active && typeof active.apiGet === "function") {
    return unwrap(await withTimeout(active.apiGet(endpoint, params)));
  }
  throw new Error("插件页面桥接不可用，请从 AstrBot 管理面板打开本页");
}

export async function apiPost(endpoint, body = {}) {
  const active = ensureBridge();
  if (active && typeof active.apiPost === "function") {
    return unwrap(await withTimeout(active.apiPost(endpoint, body)));
  }
  throw new Error("插件页面桥接不可用，请从 AstrBot 管理面板打开本页");
}

export async function readyBridge() {
  const active = ensureBridge();
  if (typeof active?.apiGet !== "function") {
    throw new Error("插件页面桥接不可用，请从 AstrBot 管理面板打开本页");
  }
  if (typeof active.ready === "function") await withTimeout(active.ready());
  return active;
}

export function formatTs(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "—";
  try {
    return new Date(value * 1000).toLocaleString(getLanguage(), {
      hour12: false,
      timeZone: "Asia/Shanghai",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

/** Split a panel text field into a trimmed list on commas or newlines. */
export function splitList(value) {
  return String(value ?? "")
    .replace(/，/g, ",")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
