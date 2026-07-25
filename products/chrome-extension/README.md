# Chrome extension

## Status

Verified in hands-on use. Rust, WebAssembly, service-worker, capture, Markdown
conformance, punctuation, RTL, math, DOCX, and clipboard tests pass. Remaining
release work is Chrome Web Store validation, signed packaging, and publication.

The Chrome extension is self-contained. It can capture the latest visible answer from major LLM chat pages, reconstruct clean Markdown, then either download a DOCX or replace the clipboard with formatted content. Its bundled Rust/WebAssembly compiler runs locally in the Manifest V3 service worker. It does not inject prompts or formatting instructions, call an md2docx API, require Docker, or upload document text.

Version 1.3.4 applies one shared polished theme to both delivery paths and uses Word-stable nonbreaking boundary spaces when Word switches between Hebrew/Arabic and English, numbers, currency, brackets, or punctuation. This avoids Word visually moving or suppressing an ordinary run-edge space. Downloaded DOCX files use compact 1.15 line rhythm, restrained headings, modern Arial typography, shaded tables with horizontally and vertically centered cells, and native Word equations for supported LaTeX. **Copy formatted** emits self-contained Word-compatible HTML with the same typography, heading measurements, explicit RTL/LTR direction, table banding, centered cells, code styling, and preserved LLM status lines. Equations are embedded as Presentation MathML, which current Microsoft 365 Word versions import as Office Math, instead of raw LaTeX or a CSS drawing. Reload the unpacked extension after updating the source directory so Chrome starts the new worker and WASM bundle.

Supported source choices are Auto-detect, Selected page content, ChatGPT, Claude, Gemini, Microsoft Copilot, Grok, Perplexity, DeepSeek, and Generic LLM page. Auto-detect uses the current website and captured provider to select the appropriate CommonMark/GFM/LLM profile; users normally do not choose a dialect. Provider-specific selectors are tried first; Selected page content is the reliable fallback when a provider changes its page markup.

Browsers expose the rendered page, not normally the provider's private raw API response. The capture layer therefore reconstructs Markdown from visible headings, paragraphs, emphasis, lists, tables, code blocks, links, blockquotes, and accessible TeX annotations. The compiler recognizes CommonMark, GFM tables/tasks/autolinks, arbitrary fenced-code language identifiers, footnotes, description lists, math, highlights, underline, subscript, and superscript. Hebrew/Arabic tables keep logical cell order and receive Word's visual RTL table property.

## Install from source

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the repository's `products/chrome-extension` directory.
5. Pin **md2docx — Markdown to Word**.

Open an LLM conversation, click the extension, leave the source on **Auto-detect LLM**, and select **Capture latest response**. Review the Markdown, then choose **Download .docx** or **Copy formatted**. Paste the latter directly into Word with normal paste (`Ctrl+V`); choosing “Keep Text Only” in Word intentionally discards the formatting. You may also paste Markdown directly or use the injected button on supported GitHub Markdown and HackMD pages. Active LLM pages are read only after the user clicks Capture through Chrome's temporary `activeTab` permission; no broad LLM host permissions are requested.

Run `.\scripts\test_all.ps1` from the repository root for Rust, regenerated
WASM, browser fallback, worker, capture, packaged-WASM, and Skill One tests. The
shared dialect/punctuation matrix is documented in
`tests/MARKDOWN_CONFORMANCE.md`. Add `-IncludeDocker` for the clean Python
Skill One gate, then perform the browser and Word visual checks in `AGENTS.md`.

Build a Web Store-shaped ZIP from the repository root with
`.\scripts\package_release.ps1`. The resulting `dist/releases/chrome-extension.zip`
has `manifest.json` at the archive root. Store validation and publication are
still manual release gates.
