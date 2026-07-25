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
  // Mixed content must be split into explicit Word RTL/LTR runs. Component
  // text remains in logical source order while Word controls visual ordering.
  for (const component of [
    "\u05d3\u05d5\u05d2\u05de\u05d4",
    "\u05e2\u05d1\u05e8\u05d9\u05ea",
    "\u05d0\u05e0\u05d2\u05dc\u05d9\u05ea",
    "2026",
    "Customer Acquisition Cost (CAC)",
    "\u05e9\u05d9\u05e8\u05d3",
    "\u05d0\u05dc\u05d2\u05d5\u05e8\u05d9\u05ea\u05dd",
    "Gradient Descent",
  ]) assert.ok(text.includes(component), `missing mixed-BiDi component ${component}`);
  assert.match(text, /<w:rtl\/>/);
  assert.match(text, /<w:rtl w:val="0"\/>/);
  assert.doesNotMatch(text, /[\u200e\u200f\u202a-\u202e\u2067\u2068]/);
  assert.equal((text.match(/\u2066/g) || []).length, (text.match(/\u2069/g) || []).length);
  assert.ok((text.match(/\u2066/g) || []).length > 0);
});

test("packaged WASM preserves Spotwize RTL order and mirrors prose arrows", () => {
  const wasm = loadCore();
  const markdown = fs.readFileSync(path.join(__dirname, "fixtures", "spotwize_bidi_regression.md"), "utf8");
  const docx = new TextDecoder().decode(wasm.convert_docx(markdown, "llm"));
  const html = wasm.convert_html(markdown, "llm");

  for (const output of [docx, html]) {
    assert.match(output, /תקציר מנהלים/);
    assert.match(output, /Roadmap/);
    assert.match(output, /תל אביב ← גוש דן ← ערים נבחרות בישראל/);
    assert.doesNotMatch(output, /→/);
  }
  assert.match(docx, /<w:rtl\/>/);
  assert.match(docx, /<w:rtl w:val="0"\/>/);
  assert.match(html, /<h2 dir="rtl"/);
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
