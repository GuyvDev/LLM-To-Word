const mdInput = document.getElementById("mdInput");
const convertBtn = document.getElementById("convertBtn");
const statusEl = document.getElementById("status");
convertBtn.addEventListener("click", async () => {
  const markdown = mdInput.value.trim();
  if (!markdown) return setStatus("Paste some Markdown first.", "error");
  convertBtn.disabled = true; setStatus("Converting…");
  const result = await chrome.runtime.sendMessage({ type: "CONVERT", markdown });
  convertBtn.disabled = false;
  setStatus(result.ok ? "✓ Downloaded result.docx" : `Error: ${result.error || "unknown error"}`, result.ok ? "success" : "error");
});
function setStatus(message, type = "") { statusEl.textContent = message; statusEl.className = `status ${type}`; }
