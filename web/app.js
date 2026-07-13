// Public md2docx web client. Set window.__MD2DOCX_API_BASE__ before this script
// when the static site and API are hosted on different origins.
const API_BASE = (window.__MD2DOCX_API_BASE__ || window.location.origin).replace(/\/$/, "");
const dropArea = document.getElementById("dropArea");
const mdInput = document.getElementById("mdInput");
const fontSel = document.getElementById("fontSel");
const baseFontSel = document.getElementById("baseFontSel");
const convertBtn = document.getElementById("convertBtn");
const statusEl = document.getElementById("status");

setupDrop();
convertBtn.addEventListener("click", handleConvert);

function setupDrop() {
  dropArea.addEventListener("dragover", (event) => { event.preventDefault(); dropArea.classList.add("drag-over"); });
  dropArea.addEventListener("dragleave", () => dropArea.classList.remove("drag-over"));
  dropArea.addEventListener("drop", async (event) => {
    event.preventDefault(); dropArea.classList.remove("drag-over");
    const file = event.dataTransfer.files[0];
    if (!file) return;
    mdInput.value = await file.text();
    setStatus(`Loaded: ${file.name}`, "info");
  });
}

async function handleConvert() {
  const markdown = mdInput.value.trim();
  if (!markdown) return setStatus("Paste or drop some Markdown first.", "error");
  convertBtn.disabled = true;
  setStatus("Converting…", "info");
  try {
    const response = await fetch(`${API_BASE}/convert`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown, font: fontSel.value, base_font: baseFontSel.value }) });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || response.statusText);
    downloadBlob(await response.blob(), "result.docx");
    setStatus("✓ result.docx downloaded!", "success");
  } catch (error) {
    setStatus(`Error: ${error.message}`, "error");
  } finally { convertBtn.disabled = false; }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
function setStatus(message, type = "") { statusEl.textContent = message; statusEl.className = `status ${type}`; }
