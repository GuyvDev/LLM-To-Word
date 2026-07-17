const mdInput = document.getElementById("mdInput");
const sourceSelect = document.getElementById("llmSource");
const captureBtn = document.getElementById("captureBtn");
const convertBtn = document.getElementById("convertBtn");
const copyBtn = document.getElementById("copyBtn");
const statusEl = document.getElementById("status");
let capturedProvider = "auto";

chrome.storage.local.get("llmSource").then(({ llmSource }) => {
  if ([...sourceSelect.options].some((option) => option.value === llmSource)) sourceSelect.value = llmSource;
});
sourceSelect.addEventListener("change", () => chrome.storage.local.set({ llmSource: sourceSelect.value }));

captureBtn.addEventListener("click", async () => {
  setBusy(true);
  setStatus("Reading the latest visible response…");
  try {
    const result = await chrome.runtime.sendMessage({ type: "CAPTURE_ACTIVE_TAB", provider: sourceSelect.value });
    if (!result?.ok) throw new Error(result?.error || "No response was captured.");
    mdInput.value = result.markdown;
    capturedProvider = result.provider || "response";
    setStatus(`✓ Captured ${result.providerLabel || "LLM"} output. Review it or download Word.`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

convertBtn.addEventListener("click", async () => {
  const markdown = mdInput.value.trim();
  if (!markdown) return setStatus("Capture a response or paste Markdown first.", "error");
  setBusy(true);
  setStatus("Building the Word document locally…");
  try {
    const filename = `${safeFilename(capturedProvider)}-response.docx`;
    const result = await chrome.runtime.sendMessage({ type: "CONVERT", markdown, filename, source: capturedProvider });
    if (!result?.ok) throw new Error(result?.error || "Unknown conversion error");
    setStatus(`✓ Downloaded ${filename}`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

copyBtn.addEventListener("click", async () => {
  const markdown = mdInput.value.trim();
  if (!markdown) return setStatus("Capture a response or paste Markdown first.", "error");
  setBusy(true);
  setStatus("Building formatted clipboard content locally…");
  try {
    const result = await chrome.runtime.sendMessage({ type: "CONVERT_HTML", markdown, source: capturedProvider });
    if (!result?.ok) throw new Error(result?.error || "Unknown conversion error");
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([result.html], { type: "text/html" }),
      "text/plain": new Blob([markdown], { type: "text/plain" }),
    })]);
    setStatus("✓ Clipboard replaced with formatted content. Paste it into Word.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
});

function safeFilename(value) { return String(value || "llm").toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "llm"; }
function setBusy(busy) { captureBtn.disabled = busy; convertBtn.disabled = busy; copyBtn.disabled = busy; sourceSelect.disabled = busy; }
function setStatus(message, type = "") { statusEl.textContent = message; statusEl.className = `status ${type}`; }
