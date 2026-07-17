const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const extensionDir = path.join(__dirname, "..", "products", "chrome-extension");
const wasmBytes = fs.readFileSync(path.join(extensionDir, "core", "md2docx_core_bg.wasm"));

function startWorker() {
  let listener;
  let downloaded;
  const context = vm.createContext({
    Blob,
    Request,
    Response,
    TextDecoder,
    TextEncoder,
    URL,
    Uint8Array,
    WebAssembly,
    btoa: (value) => Buffer.from(value, "binary").toString("base64"),
    console,
  });
  context.self = context;
  context.fetch = async (url) => {
    assert.match(String(url), /md2docx_core_bg\.wasm$/);
    return new Response(wasmBytes, { headers: { "Content-Type": "application/wasm" } });
  };
  context.importScripts = (...names) => {
    for (const name of names) {
      const source = fs.readFileSync(path.join(extensionDir, name), "utf8");
      vm.runInContext(source, context, { filename: name });
    }
  };
  context.chrome = {
    runtime: {
      getURL: (name) => `https://extension.test/${name}`,
      onMessage: { addListener: (value) => { listener = value; } },
    },
    downloads: { download: async (options) => { downloaded = options; } },
  };
  vm.runInContext(fs.readFileSync(path.join(extensionDir, "background.js"), "utf8"), context, { filename: "background.js" });
  return {
    downloaded: () => downloaded,
    send: (message) => new Promise((resolve) => {
      assert.equal(listener(message, {}, resolve), true);
    }),
  };
}

test("extension worker uses packaged core for HTML clipboard conversion", async () => {
  const worker = startWorker();
  const result = await worker.send({
    type: "CONVERT_HTML",
    source: "chatgpt",
    markdown: "| שם | ערך |\n|---|---|\n| א | 1 |\n\n```bash\necho ok\n```",
  });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.engine, "canonical-wasm");
  assert.match(result.html, /<table dir="rtl" style=/);
  assert.match(result.html, /language-bash/);
});

test("extension worker returns the benchmark's Word-ready clipboard payload", async () => {
  const worker = startWorker();
  const markdown = fs.readFileSync(path.join(__dirname, "fixtures", "hebrew_experiment_benchmark.md"), "utf8");
  const result = await worker.send({ type: "CONVERT_HTML", source: "chatgpt", markdown });
  assert.equal(result.ok, true, result.error);
  assert.match(result.html, /^<!--StartFragment-->/);
  assert.match(result.html, /md2docx-math-display/);
  assert.match(result.html, /text-align:center;vertical-align:middle/);
  assert.doesNotMatch(result.html, /\\theta|\\frac|data-math-style/);
});

test("extension worker downloads a DOCX produced by the packaged core", async () => {
  const worker = startWorker();
  const result = await worker.send({ type: "CONVERT", source: "gemini", markdown: "# כותרת", filename: "answer.docx" });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.engine, "canonical-wasm");
  assert.equal(worker.downloaded().filename, "answer.docx");
  assert.match(worker.downloaded().url, /^data:application\/vnd\.openxmlformats-officedocument\.wordprocessingml\.document;base64,UEsDB/);
});
