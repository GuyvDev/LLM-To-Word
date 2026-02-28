/**
 * web/app.js — md2docx Web UI logic
 *
 * Features:
 *  - Drag & drop or paste Markdown
 *  - POST to FastAPI /convert, download the .docx blob
 *  - Display real-time quota from /quota endpoint
 *  - Show upgrade CTA on 429
 */

const API_BASE = "https://api.md2docx.app";   // change to http://localhost:8000 for local dev

// ── DOM refs ──────────────────────────────────────────────────────────────────
const dropArea    = document.getElementById("dropArea");
const mdInput     = document.getElementById("mdInput");
const fontSel     = document.getElementById("fontSel");
const baseFontSel = document.getElementById("baseFontSel");
const convertBtn  = document.getElementById("convertBtn");
const statusEl    = document.getElementById("status");
const quotaPill   = document.getElementById("quotaPill");

// ── Init ───────────────────────────────────────────────────────────────────────
(async () => {
  await loadQuota();
  setupDrop();
  convertBtn.addEventListener("click", handleConvert);
})();

// ── Quota ──────────────────────────────────────────────────────────────────────
async function loadQuota() {
  const apiKey = localStorage.getItem("md2docx_api_key") ?? "anonymous";
  try {
    const headers = apiKey !== "anonymous" ? { "X-Api-Key": apiKey } : {};
    const res  = await fetch(`${API_BASE}/quota`, { headers });
    if (!res.ok) throw new Error();
    const data = await res.json();
    renderQuota(data);
  } catch {
    quotaPill.textContent = "—";
  }
}

function renderQuota({ used, limit, remaining, tier }) {
  if (tier === "pro" || tier === "team") {
    quotaPill.textContent = "Unlimited";
    quotaPill.className   = "quota-pill pro";
    return;
  }
  quotaPill.textContent = `${remaining} / ${limit} free conversions`;
  quotaPill.className   = remaining === 0 ? "quota-pill exhausted" : "quota-pill";
  if (remaining === 0) {
    convertBtn.disabled  = true;
    showUpgrade("You've used all your free conversions this month.");
  }
}

// ── Drag & drop ───────────────────────────────────────────────────────────────
function setupDrop() {
  dropArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropArea.classList.add("drag-over");
  });
  dropArea.addEventListener("dragleave", () => dropArea.classList.remove("drag-over"));
  dropArea.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropArea.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (!file) return;
    mdInput.value = await file.text();
    setStatus(`Loaded: ${file.name}`, "info");
  });
}

// ── Convert ────────────────────────────────────────────────────────────────────
async function handleConvert() {
  const markdown = mdInput.value.trim();
  if (!markdown) {
    setStatus("Paste or drop some Markdown first.", "error");
    return;
  }

  convertBtn.disabled = true;
  setStatus("Converting…", "info");

  const apiKey    = localStorage.getItem("md2docx_api_key") ?? "anonymous";
  const headers   = {
    "Content-Type": "application/json",
    ...(apiKey !== "anonymous" ? { "X-Api-Key": apiKey } : {}),
  };

  try {
    const res = await fetch(`${API_BASE}/convert`, {
      method:  "POST",
      headers,
      body: JSON.stringify({
        markdown,
        font:      fontSel.value,
        base_font: baseFontSel.value,
      }),
    });

    if (res.status === 429) {
      const body = await res.json().catch(() => ({}));
      showUpgrade(body?.detail?.message ?? "Quota exceeded.");
      setStatus("Monthly quota reached — upgrade for unlimited.", "error");
      return;
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.detail ?? res.statusText);
    }

    const blob = await res.blob();
    downloadBlob(blob, "result.docx");
    setStatus("✓ result.docx downloaded!", "success");
    await loadQuota();

  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    convertBtn.disabled = false;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = Object.assign(document.createElement("a"), {
    href: url, download: filename,
  });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className   = `status ${type}`;
}

function showUpgrade(msg) {
  // Insert an upgrade banner if not already present
  if (document.getElementById("upgrade-banner")) return;
  const banner = document.createElement("div");
  banner.id    = "upgrade-banner";
  banner.className = "upgrade-banner";
  banner.innerHTML = `
    <span>${msg}</span>
    <a class="btn btn-primary" href="https://buy.stripe.com/your-link" target="_blank">
      Upgrade to Pro — $5/mo
    </a>
    <button class="close-btn" onclick="this.parentElement.remove()">✕</button>
  `;
  document.querySelector(".converter")?.prepend(banner);
}
