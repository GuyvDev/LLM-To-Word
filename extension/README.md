# Chrome extension

The Chrome extension is self-contained. Markdown conversion runs in its Manifest V3 service worker and produces the DOCX package locally. It does not call an md2docx API, require Docker, or upload document text.

## Install from source

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose this `extension` directory.
5. Pin **md2docx — Markdown to Word**.

Paste Markdown into the popup, or use the injected button on supported GitHub Markdown and HackMD pages. The only host permissions are for those optional page integrations.

Run `node --test tests/test_browser_converter.js` from the repository root, then perform the browser and Word visual checks listed in `AGENTS.md`.
