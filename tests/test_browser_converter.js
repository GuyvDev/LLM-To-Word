const test = require("node:test");
const assert = require("node:assert/strict");
const converter = require("../extension/md2docx.js");

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
