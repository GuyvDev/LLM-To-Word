/**
 * content/hackmd.js — md2docx HackMD content script
 *
 * Injects a "Download as DOCX" button into HackMD's toolbar.
 * Works on both the editor view (hackmd.io/noteId) and published
 * note views.
 */

(function () {
  "use strict";

  const BUTTON_ID = "md2docx-hackmd-btn";

  // HackMD renders dynamically — poll briefly then fall back to observer
  let attempts = 0;
  const interval = setInterval(() => {
    if (tryInject() || ++attempts > 40) clearInterval(interval);
  }, 500);

  function tryInject() {
    if (document.getElementById(BUTTON_ID)) return true;

    // HackMD toolbar: look for the toolbar container
    // The export dropdown button has an SVG icon related to export
    const toolbar = (
      document.querySelector(".toolbar") ||
      document.querySelector('[class*="toolbar"]') ||
      document.querySelector(".ui-toolbar")
    );
    if (!toolbar) return false;

    const btn = document.createElement("button");
    btn.id          = BUTTON_ID;
    btn.type        = "button";
    btn.textContent = "⬇ .docx";
    btn.title       = "Download as Word document via md2docx";
    btn.style.cssText = [
      "margin:0 4px",
      "padding:4px 10px",
      "font-size:13px",
      "font-weight:600",
      "color:#fff",
      "background:#1e40af",
      "border:none",
      "border-radius:5px",
      "cursor:pointer",
      "height:30px",
      "vertical-align:middle",
    ].join(";");

    btn.addEventListener("click", handleClick);
    toolbar.appendChild(btn);
    return true;
  }

  async function handleClick() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn) return;
    btn.textContent = "Converting…";
    btn.disabled    = true;

    try {
      const markdown = extractMarkdown();

      const result = await chrome.runtime.sendMessage({
        type:   "CONVERT",
        markdown,
        filename: `${document.title || "note"}.docx`,
      });

      if (result.ok) {
        btn.textContent = "✓ Done";
        setTimeout(() => { btn.textContent = "⬇ .docx"; btn.disabled = false; }, 2500);
      } else if (result.status === 429) {
        btn.textContent = "Try again shortly";
        setTimeout(() => { btn.textContent = "⬇ .docx"; btn.disabled = false; }, 4000);
      } else {
        throw new Error(result.error ?? "Unknown error");
      }
    } catch (err) {
      btn.textContent = "Error";
      console.error("[md2docx]", err);
      setTimeout(() => { btn.textContent = "⬇ .docx"; btn.disabled = false; }, 3000);
    }
  }

  function extractMarkdown() {
    // Try CodeMirror editor textarea (edit mode)
    const cm = document.querySelector(".CodeMirror");
    if (cm?.CodeMirror) return cm.CodeMirror.getValue();

    // Try generic textarea
    const ta = document.querySelector("textarea");
    if (ta?.value) return ta.value;

    // Fall back to the rendered HTML text (published view)
    const article = document.querySelector("article") || document.querySelector(".markdown-body");
    if (article) return article.innerText;

    throw new Error("Could not extract Markdown content from this page.");
  }
})();
