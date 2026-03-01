/**
 * popup.js — md2docx Chrome Extension popup logic
 *
 * Responsibilities:
 *  1. Load and display quota from chrome.storage + API.
 *  2. Convert pasted markdown via background.js and trigger download.
 *  3. Show upgrade CTA when quota is exhausted.
 */

const API_BASE = "https://md2docx.app";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const quotaBar    = document.getElementById("quotaBar");
const quotaText   = document.getElementById("quotaText");
const tierBadge   = document.getElementById("tierBadge");
const mdInput     = document.getElementById("mdInput");
const convertBtn  = document.getElementById("convertBtn");
const upgradeBtn  = document.getElementById("upgradeBtn");
const statusEl    = document.getElementById("status");

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await refreshQuota();

  convertBtn.addEventListener("click", handleConvert);
  upgradeBtn.addEventListener("click", () => {
    chrome.tabs.create({ url: "https://md2docx.app/#upgrade" });
  });
});

// ── Quota display ──────────────────────────────────────────────────────────────
async function refreshQuota() {
  const apiKey = await getApiKey();
  try {
    const res = await fetch(`${API_BASE}/quota`, {
      headers: apiKey !== "anonymous" ? { "X-Api-Key": apiKey } : {},
    });
    if (!res.ok) throw new Error("quota fetch failed");
    const data = await res.json();
    renderQuota(data);
  } catch {
    quotaText.textContent = "Could not load quota";
  }
}

function renderQuota(data) {
  const { used, limit, remaining, tier } = data;
  const isUnlimited = tier === "pro" || tier === "team";

  // Badge
  tierBadge.textContent = tier;
  tierBadge.className   = `tier-badge ${tier}`;

  if (isUnlimited) {
    quotaBar.style.width = "100%";
    quotaText.innerHTML  = "<strong>Unlimited</strong> conversions";
    upgradeBtn.style.display = "none";
    return;
  }

  const pct = Math.min(100, Math.round((used / limit) * 100));
  quotaBar.style.width = `${pct}%`;
  quotaText.innerHTML  =
    `<strong>${remaining}</strong> of ${limit} remaining this month`;

  if (remaining === 0) {
    upgradeBtn.style.display = "block";
    convertBtn.disabled      = true;
  } else {
    upgradeBtn.style.display = "none";
    convertBtn.disabled      = false;
  }
}

// ── Convert ────────────────────────────────────────────────────────────────────
async function handleConvert() {
  const markdown = mdInput.value.trim();
  if (!markdown) {
    setStatus("Paste some Markdown first.", "error");
    return;
  }

  convertBtn.disabled = true;
  setStatus("Converting…");

  const apiKey = await getApiKey();
  const result = await chrome.runtime.sendMessage({
    type: "CONVERT",
    markdown,
    apiKey,
  });

  convertBtn.disabled = false;

  if (result.ok) {
    setStatus("✓ Downloaded result.docx", "success");
    await refreshQuota();
  } else if (result.status === 429) {
    setStatus("Quota exceeded — upgrade for unlimited.", "error");
    upgradeBtn.style.display = "block";
    convertBtn.disabled      = true;
  } else {
    setStatus(`Error: ${result.error ?? "unknown error"}`, "error");
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
async function getApiKey() {
  return new Promise((resolve) => {
    chrome.storage.sync.get("apiKey", (data) => {
      resolve(data.apiKey ?? "anonymous");
    });
  });
}

function setStatus(msg, type = "") {
  statusEl.textContent  = msg;
  statusEl.className    = `status ${type}`;
}
