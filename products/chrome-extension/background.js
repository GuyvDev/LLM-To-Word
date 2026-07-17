/** Manifest V3 worker: convert Markdown locally and download/copy the result. */
importScripts("md2docx.js");

let coreScriptLoaded = false;
try {
  importScripts("core/md2docx_core.js");
  coreScriptLoaded = typeof wasm_bindgen === "function";
} catch (_error) {
  // Source checkouts can run the JavaScript fallback before the WASM build.
}

let corePromise;
function loadCore() {
  if (!coreScriptLoaded) return Promise.resolve(false);
  if (!corePromise) {
    corePromise = wasm_bindgen({ module_or_path: chrome.runtime.getURL("core/md2docx_core_bg.wasm") })
      .then(() => true)
      .catch((error) => {
        console.warn("md2docx WASM core unavailable; using fallback", error);
        return false;
      });
  }
  return corePromise;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CONVERT") {
    handleConvert({ ...message, source: message.source || sender.tab?.url || "auto" }).then(sendResponse);
    return true;
  }
  if (message.type === "CONVERT_HTML") {
    handleConvertHtml(message).then(sendResponse);
    return true;
  }
  if (message.type === "CAPTURE_ACTIVE_TAB") {
    captureActiveTab(message.provider).then(sendResponse);
    return true;
  }
  return false;
});

async function captureActiveTab(provider = "auto") {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("No active browser tab was found.");
    if (/^(chrome|edge|about|view-source):/i.test(tab.url || "")) throw new Error("Chrome does not allow extensions to read this internal page.");
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content/llm-capture.js"] });
    return await chrome.tabs.sendMessage(tab.id, { type: "MD2DOCX_CAPTURE_LLM", provider });
  } catch (error) {
    return { ok: false, error: `Capture failed: ${error.message}` };
  }
}

async function docxBytes(markdown, source = "auto") {
  if (await loadCore()) return { bytes: wasm_bindgen.convert_docx(markdown, source), engine: "canonical-wasm" };
  return {
    bytes: self.Md2Docx.convert(markdown, { font: "Arial", baseFont: "Arial" }),
    engine: "compatibility-js",
  };
}

async function handleConvert({ markdown, filename = "result.docx", source = "auto" }) {
  try {
    const { bytes, engine } = await docxBytes(markdown, source);
    const base64 = self.Md2Docx.toBase64(bytes);
    const url = `data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,${base64}`;
    await chrome.downloads.download({ url, filename, saveAs: false });
    return { ok: true, engine };
  } catch (error) {
    return { ok: false, error: `Local conversion failed: ${error.message}` };
  }
}

async function handleConvertHtml({ markdown, source = "auto" }) {
  try {
    if (!(await loadCore())) throw new Error("The formatted clipboard core has not been built yet.");
    return { ok: true, html: wasm_bindgen.convert_html(markdown, source), engine: "canonical-wasm" };
  } catch (error) {
    return { ok: false, error: `Local conversion failed: ${error.message}` };
  }
}
