// =====================================================================
// Pure utility functions. No dependencies.
// =====================================================================

function safeString(value) {
    return value == null ? "" : String(value).trim();
}

function toNumber(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
}

function formatValue(value) {
    if (value === null || value === undefined) return "-";
    if (typeof value === "number") {
        return Number.isInteger(value) ? String(value) : value.toFixed(4);
    }
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

function formValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
}

function formNumber(id, fallback = 0) {
    return toNumber(formValue(id), fallback);
}

function formNumberOrNull(id) {
    const raw = formValue(id);
    if (raw === "") return null;
    return toNumber(raw, 0);
}

function formBool(id) {
    const el = document.getElementById(id);
    return el ? el.checked : false;
}

async function decisionFetchJson(url) {
    const res = await fetch(url);
    let data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok) {
        throw new Error(data.error || `Request failed with status ${res.status}.`);
    }
    return data;
}

function flattenRow(row) {
    const out = {};
    Object.entries(row || {}).forEach(([key, value]) => {
        if (value === null || value === undefined) { out[key] = value; return; }
        if (typeof value === "object") {
            if (Array.isArray(value)) { out[key] = JSON.stringify(value); return; }
            Object.entries(value).forEach(([subKey, subValue]) => {
                out[`${key}.${subKey}`] = subValue;
            });
        } else {
            out[key] = value;
        }
    });
    return out;
}

function deriveColumns(firstRow, preferredKeys = []) {
    const keys = Object.keys(firstRow || {});
    const preferred = preferredKeys.filter(key => keys.includes(key));
    const rest = keys.filter(key => !preferred.includes(key));
    return [...preferred, ...rest].map(key => ({ key, label: key }));
}

function formatMoney(value, currency) {
    if (value === null || value === undefined) return "Unavailable";
    return `${Number(value).toFixed(2)} ${currency || ""}`.trim();
}

function formatPercent(value) {
    if (value === null || value === undefined) return "Unavailable";
    return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatProbability(value) {
    if (value === null || value === undefined) return "-";
    const num = Number(value);
    if (!Number.isFinite(num)) return String(value);
    return `${(num * 100).toFixed(1)}%`;
}

function on(id, eventName, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(eventName, handler);
}