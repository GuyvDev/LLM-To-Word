const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const coreDir = path.join(__dirname, "..", "products", "chrome-extension", "core");
const gluePath = path.join(coreDir, "md2docx_core.js");
const wasmPath = path.join(coreDir, "md2docx_core_bg.wasm");

let core;
function loadCore() {
  if (core) return core;
  const glue = fs.readFileSync(gluePath, "utf8")
    .replace(/^let wasm_bindgen =/, "globalThis.wasm_bindgen =");
  vm.runInThisContext(glue, { filename: gluePath });
  globalThis.wasm_bindgen.initSync({ module: fs.readFileSync(wasmPath) });
  core = globalThis.wasm_bindgen;
  return core;
}

test("packaged WASM core auto-detects source profiles", () => {
  const wasm = loadCore();
  assert.equal(wasm.detected_profile("https://chatgpt.com/c/123"), "llm");
  assert.equal(wasm.detected_profile("https://github.com/org/repo"), "github");
  assert.equal(wasm.detected_profile("unknown-site"), "gfm");
});

test("packaged WASM creates DOCX and rich HTML for extended Markdown", () => {
  const wasm = loadCore();
  const markdown = "# כותרת\n\n| שם | ערך |\n|---|---|\n| אלף | 1 |\n\n```bash\necho ok\n```";
  const bytes = wasm.convert_docx(markdown, "chatgpt");
  assert.deepEqual([...bytes.subarray(0, 4)], [0x50, 0x4b, 0x03, 0x04]);
  const html = wasm.convert_html(markdown, "chatgpt");
  assert.match(html, /<h1 dir="rtl" style="[^"]+">כותרת<\/h1>/);
  assert.match(html, /<table dir="rtl" style=/);
  assert.match(html, /language-bash/);
});

test("downloaded DOCX renders the Hebrew benchmark with native math and centered cells", () => {
  const wasm = loadCore();
  const markdown = fs.readFileSync(path.join(__dirname, "fixtures", "hebrew_experiment_benchmark.md"), "utf8");
  const bytes = wasm.convert_docx(markdown, "chatgpt");
  const text = new TextDecoder().decode(bytes);
  assert.doesNotMatch(text, /<w:t[^>]*>\$\$<\/w:t>/);
  assert.match(text, /<m:sSub>/);
  assert.match(text, /θ/);
  assert.match(text, /α/);
  assert.match(text, /∇/);
  assert.match(text, /<w:bidiVisual\/>/);
  assert.match(text, /<w:jc w:val="center"\/>/);
  // Ordinary run-edge spaces can be moved or hidden by Word's BiDi layout.
  // Every language/symbol boundary therefore uses a visible-width NBSP.
  for (const boundary of [
    "דוגמה\u00a0</w:t>",
    "1\u00a0—\u00a0</w:t>",
    "של\u00a0</w:t>",
    "2026\u00a0</w:t>",
    "18%\u00a0</w:t>",
    "היה\u00a0</w:t>",
    "Customer Acquisition Cost (CAC),\u00a0</w:t>",
    "42\u00a0</w:t>",
    "אלגוריתם\u00a0</w:t>",
    "עם\u00a0</w:t>",
    "פתרונות\u00a0</w:t>",
  ]) assert.ok(text.includes(boundary), `missing Word-stable mixed-BiDi boundary ${boundary}`);
});

test("formatted clipboard renders the Hebrew benchmark as compact Word-ready HTML", () => {
  const wasm = loadCore();
  const markdown = fs.readFileSync(path.join(__dirname, "fixtures", "hebrew_experiment_benchmark.md"), "utf8");
  const html = wasm.convert_html(markdown, "chatgpt");

  assert.match(html, /^<!--StartFragment-->/);
  assert.match(html, /font-family:Arial/);
  assert.match(html, /<h1 dir="rtl" style="[^"]*font-size:21pt/);
  assert.match(html, /<table dir="rtl" style="[^"]*border-collapse:collapse/);
  assert.match(html, /font-size:11\.5pt/);
  assert.match(html, /<tr style="background:#f8fafc;">/);
  assert.equal((html.match(/<th style="[^"]*text-align:center;vertical-align:middle/g) || []).length, 4);
  assert.equal((html.match(/<td style="[^"]*text-align:center;vertical-align:middle/g) || []).length, 12);
  assert.equal((html.match(/md2docx-math-display/g) || []).length, 2);
  assert.match(html, /θ/);
  assert.match(html, /α/);
  assert.match(html, /∇/);
  assert.match(html, /<msup>/);
  assert.match(html, /<msub>/);
  assert.match(html, /<mfrac>/);
  assert.match(html, /xmlns="http:\/\/www\.w3\.org\/1998\/Math\/MathML"/);
  assert.match(html, /Status:<br \/>\n✅ Backend completed<br \/>/);
  assert.match(html, /config\/production\/settings\.yaml/);
  assert.doesNotMatch(html, /data-math-style/);
  assert.doesNotMatch(html, /\\theta|\\alpha|\\nabla|\\frac|\\sum/);
});

test("packaged WASM satisfies the shared dialect conformance corpus", () => {
  const wasm = loadCore();
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "markdown_conformance.json"), "utf8"));
  for (const item of cases) {
    const html = wasm.convert_html(item.markdown, item.source);
    for (const expected of item.html_contains) assert.ok(html.includes(expected), `${item.id}: HTML missing ${JSON.stringify(expected)}`);
    for (const forbidden of item.html_not_contains) assert.ok(!html.includes(forbidden), `${item.id}: HTML contains ${JSON.stringify(forbidden)}`);

    const bytes = wasm.convert_docx(item.markdown, item.source);
    assert.deepEqual([...bytes.subarray(0, 4)], [0x50, 0x4b, 0x03, 0x04], `${item.id}: ZIP signature`);
    const docx = new TextDecoder().decode(bytes);
    for (const expected of item.docx_contains) assert.ok(docx.includes(expected), `${item.id}: DOCX missing ${JSON.stringify(expected)}`);
    for (const forbidden of item.docx_not_contains) assert.ok(!docx.includes(forbidden), `${item.id}: DOCX contains ${JSON.stringify(forbidden)}`);
  }
});
