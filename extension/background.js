/**
 * background.js — md2docx Extension Service Worker (Manifest V3)
 *
 * Handles:
 *  - CONVERT messages from popup.js and content scripts
 *  - Fetches the API, receives binary .docx, triggers browser download
 *
 * Why do API calls in the background?
 *  Content scripts and popups can't use fetch() with binary responses
 *  and then trigger downloads reliably. The background service worker
 *  serialises the bytes as a base64 data-URL and calls chrome.downloads.
 */

const API_BASE = "https://md2docx.app";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "CONVERT") {
    handleConvert(msg).then(sendResponse);
    return true;   // keep message channel open for async response
  }
});

async function handleConvert({ markdown, apiKey = "anonymous", filename = "result.docx" }) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (apiKey && apiKey !== "anonymous") {
    headers["X-Api-Key"] = apiKey;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}/convert`, {
      method:  "POST",
      headers,
      body: JSON.stringify({ markdown }),
    });
  } catch (err) {
    return { ok: false, error: `Network error: ${err.message}` };
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body?.detail?.message ?? body?.detail ?? response.statusText;
    } catch {
      detail = response.statusText;
    }
    return { ok: false, status: response.status, error: detail };
  }

  // Convert binary response → base64 data URL for chrome.downloads
  const arrayBuf = await response.arrayBuffer();
  const base64   = bufferToBase64(arrayBuf);
  const dataUrl  = `data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,${base64}`;

  await chrome.downloads.download({
    url:      dataUrl,
    filename,
    saveAs:   false,
  });

  return { ok: true };
}

function bufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary  = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}
