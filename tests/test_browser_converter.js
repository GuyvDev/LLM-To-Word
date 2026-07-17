const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const converter = require("../products/chrome-extension/md2docx.js");

function unzipStored(bytes) {
  const buffer = Buffer.from(bytes);
  const files = new Map();
  let offset = 0;
  while (buffer.readUInt32LE(offset) === 0x04034b50) {
    const size = buffer.readUInt32LE(offset + 18);
    const nameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const nameStart = offset + 30;
    const dataStart = nameStart + nameLength + extraLength;
    files.set(buffer.subarray(nameStart, nameStart + nameLength).toString("utf8"), buffer.subarray(dataStart, dataStart + size));
    offset = dataStart + size;
  }
  return files;
}

test("builds a self-contained DOCX with native Word structures", () => {
  const markdown = ["# \u05e9\u05dc\u05d5\u05dd main()", "", "Formula: $x^2 + \\frac{1}{2}$", "", "- one", "", "| A | B |", "|---|---|", "| 1 | 2 |", "", "```js", "console.log('ok')", "```"].join("\n");
  const files = unzipStored(converter.convert(markdown));
  for (const name of ["[Content_Types].xml", "word/document.xml", "word/styles.xml", "word/numbering.xml"]) assert.ok(files.has(name));
  const documentXml = files.get("word/document.xml").toString("utf8");
  for (const structure of [/<w:bidi\/>/, /<m:sSup>/, /<m:f>/, /<w:tbl>/, /<w:numPr>/, /Courier New/]) assert.match(documentXml, structure);
});

test("escapes user text and supports matrix OMML", () => {
  const documentXml = converter.markdownToDocumentXml("A < B & C\n\n$$\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}$$");
  assert.match(documentXml, /A &lt; B &amp; C/);
  assert.match(documentXml, /<m:m>/);
  assert.equal((documentXml.match(/<m:mr>/g) || []).length, 2);
});

test("Hebrew tables preserve logical columns and use Word visual RTL", () => {
  const files = unzipStored(converter.convert("| שם | ערך |\n|---|---|\n| אלף | 1 |"));
  const documentXml = files.get("word/document.xml").toString("utf8");
  assert.match(documentXml, /<w:bidiVisual\/>/);
  assert.ok(documentXml.indexOf("שם") < documentXml.indexOf("ערך"));
});

test("preserves arbitrary fenced-code language identifiers", () => {
  const documentXml = converter.markdownToDocumentXml("```bash\necho $HOME\n```");
  assert.match(documentXml, /bash/);
  assert.match(documentXml, /echo \$HOME/);
  assert.match(documentXml, /Courier New/);
  assert.match(documentXml, /w:shd/);
});

test("downloaded DOCX benchmark has native math, compact rhythm, and centered cells", () => {
  const markdown = fs.readFileSync(path.join(__dirname, "fixtures", "hebrew_experiment_benchmark.md"), "utf8");
  const files = unzipStored(converter.convert(markdown));
  const documentXml = files.get("word/document.xml").toString("utf8");
  const stylesXml = files.get("word/styles.xml").toString("utf8");

  assert.doesNotMatch(documentXml, /<w:t[^>]*>\$\$<\/w:t>/);
  assert.match(documentXml, /<m:sSub>/);
  assert.match(documentXml, /θ/);
  assert.match(documentXml, /α/);
  assert.match(documentXml, /∇/);
  assert.match(documentXml, /<w:bidiVisual\/>/);
  assert.doesNotMatch(documentXml, /<w:p><\/w:p>/);

  const cells = documentXml.match(/<w:tc>[\s\S]*?<\/w:tc>/g) || [];
  assert.equal(cells.length, 16);
  for (const cell of cells) {
    assert.match(cell, /<w:jc w:val="center"\/>/);
    assert.match(cell, /<w:vAlign w:val="center"\/>/);
  }
  assert.match(stylesXml, /w:after="80" w:line="276"/);
  assert.match(stylesXml, /w:styleId="Heading1"[\s\S]*?w:sz w:val="42"/);
  for (const boundary of [
    "דוגמה\u00a0</w:t>",
    "1\u00a0—\u00a0</w:t>",
    "של\u00a0</w:t>",
    "2026\u00a0</w:t>",
    "Customer Acquisition Cost (CAC),\u00a0</w:t>",
    "אלגוריתם\u00a0</w:t>",
    "עם\u00a0</w:t>",
    "פתרונות\u00a0</w:t>",
  ]) assert.ok(documentXml.includes(boundary), `fallback missing Word-stable mixed-BiDi boundary ${boundary}`);
});

test("filters illegal XML controls while preserving punctuation and brackets", () => {
  const input = "legal\tline\n illegal:\u0000\u0001\u0008\u000b\u000c\u001f [](){} <>& עברית 😀";
  const files = unzipStored(converter.convert(input));
  const documentXml = files.get("word/document.xml").toString("utf8");
  assert.doesNotMatch(documentXml, /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/);
  assert.match(documentXml, /\[\]\(\)\{\}/);
  assert.match(documentXml, /&lt;&gt;&amp;/);
  assert.match(documentXml, /עברית/);
  assert.match(documentXml, /😀/);
});

test("fallback handles tilde and long fences plus escaped table pipes", () => {
  const markdown = [
    "| Expression | Brackets |", "|---|---|", "| `a \\| b` | [{()}] |", "",
    "~~~bash extra=1", "printf '%s' '[(x)]'", "~~~", "",
    "````markdown", "```js", "const x = {a: [1]};", "```", "````",
  ].join("\n");
  const documentXml = converter.markdownToDocumentXml(markdown);
  assert.equal((documentXml.match(/<w:tc>/g) || []).length, 4);
  assert.match(documentXml, /a \| b/);
  assert.match(documentXml, /\[\{\(\)\}\]/);
  assert.match(documentXml, /bash/);
  assert.match(documentXml, /printf &apos;%s&apos; &apos;\[\(x\)\]&apos;/);
  assert.match(documentXml, /```js/);
  assert.match(documentXml, /const x = \{a: \[1\]\};/);
});
