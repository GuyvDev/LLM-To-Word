/**
 * content/github.js — md2docx GitHub content script
 *
 * Injects a "Download as DOCX" button into GitHub's Markdown file view
 * (the toolbar above the rendered file, next to "Raw", "Blame", "History").
 *
 * Supports:
 *  - Standard file view:   github.com/owner/repo/blob/branch/file.md
 *  - Searches for the "Raw" button area and appends our button next to it.
 */

(function () {
  "use strict";

  const BUTTON_ID = "md2docx-github-btn";

  // GitHub is a SPA — observe DOM for navigation events
  const observer = new MutationObserver(tryInject);
  observer.observe(document.body, { childList: true, subtree: true });
  tryInject();   // also run immediately on first load

  function tryInject() {
    // Only on .md / .txt files
    const path = location.pathname.toLowerCase();
    if (!path.endsWith(".md") && !path.endsWith(".txt") && !path.endsWith(".markdown")) return;
    if (document.getElementById(BUTTON_ID)) return;   // already injected

    // Find the toolbar that contains the "Raw" button
    // GitHub uses aria-label="View raw" on the raw button link
    const rawBtn  = document.querySelector('[aria-label="View raw"], a[data-testid="raw-button"]');
    const toolbar = rawBtn?.closest("div, ul, nav[aria-label]");
    if (!toolbar) return;

    const btn = document.createElement("button");
    btn.id          = BUTTON_ID;
    btn.textContent = "⬇ Download .docx";
    btn.title       = "Convert this Markdown file to Word via md2docx";
    btn.style.cssText = [
      "margin-left:8px",
      "padding:4px 10px",
      "font-size:12px",
      "font-weight:600",
      "color:#fff",
      "background:#1e40af",
      "border:none",
      "border-radius:6px",
      "cursor:pointer",
      "line-height:1.5",
      "vertical-align:middle",
      "transition:opacity 0.15s",
    ].join(";");

    btn.addEventListener("mouseenter", () => { btn.style.opacity = "0.85"; });
    btn.addEventListener("mouseleave", () => { btn.style.opacity = "1"; });
    btn.addEventListener("click", handleClick);

    // Insert right after the raw button
    rawBtn.insertAdjacentElement("afterend", btn);
  }

  async function handleClick() {
    const btn = document.getElementById(BUTTON_ID);
    if (!btn) return;

    btn.textContent = "Converting…";
    btn.disabled    = true;

    try {
      // Fetch raw markdown text
      const rawUrl  = document.querySelector('[aria-label="View raw"], a[data-testid="raw-button"]')?.href;
      if (!rawUrl) throw new Error("Could not find raw URL");
      const rawRes  = await fetch(rawUrl);
      const markdown = await rawRes.text();

      // Derive filename from current page title or path
      const parts   = location.pathname.split("/");
      const rawName = parts[parts.length - 1]?.replace(/\.(md|txt|markdown)$/i, "") ?? "document";
      const filename = `${rawName}.docx`;

      // Dispatch to background service worker
      const result = await chrome.runtime.sendMessage({
        type: "CONVERT",
        markdown,
        filename,
      });

      if (result.ok) {
        btn.textContent = "✓ Downloaded!";
        setTimeout(() => {
          btn.textContent = "⬇ Download .docx";
          btn.disabled    = false;
        }, 2500);
      } else if (result.status === 429) {
        btn.textContent = "Try again shortly";
        setTimeout(() => { btn.textContent = "⬇ Download .docx"; btn.disabled = false; }, 4000);
      } else {
        throw new Error(result.error ?? "Conversion failed");
      }
    } catch (err) {
      btn.textContent = `Error: ${err.message}`;
      setTimeout(() => {
        btn.textContent = "⬇ Download .docx";
        btn.disabled    = false;
      }, 4000);
    }
  }
})();
