/* Dependency-free Markdown -> DOCX engine for Chrome and Office webviews. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Md2Docx = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const M = "http://schemas.openxmlformats.org/officeDocument/2006/math";
  const RTL_RE = /[\u0590-\u05ff\u0600-\u06ff]/;
  const encoder = new TextEncoder();

  function xml(value) {
    return String(value ?? "").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;",
    })[char]);
  }
  function isRtl(value) { return RTL_RE.test(value); }
  const OPENING_PUNCTUATION = new Set(["(", "[", "{", "<", '"', "'", "“", "‘", "«", "‹", "（", "［", "｛", "【", "「", "『", "〈", "《", "$", "€", "£", "¥", "₪", "₹", "₩"]);
  function directionalParts(text) {
    const result = [];
    let buffer = "", neutrals = "", direction = null;
    for (const char of String(text)) {
      const next = isRtl(char) ? true : /[\p{L}\p{N}]/u.test(char) ? false : null;
      if (next === null) { neutrals += char; continue; }
      if (direction === null) {
        buffer += neutrals; neutrals = ""; direction = next;
      } else if (direction === next) {
        buffer += neutrals; neutrals = "";
      } else {
        const neutralChars = [...neutrals];
        const opening = neutralChars.findIndex((value) => OPENING_PUNCTUATION.has(value));
        const pivot = opening < 0 ? neutrals.length : neutralChars.slice(0, opening).join("").length;
        buffer += neutrals.slice(0, pivot).replace(/ /g, "\u00a0");
        if (buffer) result.push({ text: buffer, rtl: direction });
        buffer = neutrals.slice(pivot); neutrals = ""; direction = next;
      }
      buffer += char;
    }
    buffer += neutrals;
    if (buffer) result.push({ text: buffer, rtl: direction ?? false });
    return result;
  }
  function rawRun(text, options = {}) {
    if (!text) return "";
    const rtl = options.rtl ?? isRtl(text);
    const props = [
      options.bold ? "<w:b/>" : "", options.italic ? "<w:i/>" : "",
      options.strike ? "<w:strike/>" : "",
      options.mono ? '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/><w:sz w:val="20"/>' : "",
      rtl ? `<w:rFonts w:cs="${xml(options.font || "Arial")}"/><w:rtl/><w:lang w:bidi="he-IL"/>` : "",
    ].join("");
    return `<w:r>${props ? `<w:rPr>${props}</w:rPr>` : ""}<w:t xml:space="preserve">${xml(text)}</w:t></w:r>`;
  }
  function run(text, options = {}) {
    return directionalParts(text).map((part) => rawRun(part.text, { ...options, rtl: part.rtl })).join("");
  }

  const SYMBOLS = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", theta: "θ", lambda: "λ", mu: "μ",
    pi: "π", rho: "ρ", sigma: "σ", tau: "τ", phi: "φ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Pi: "Π", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
    pm: "±", mp: "∓", times: "×", cdot: "·", div: "÷", le: "≤", leq: "≤", ge: "≥", geq: "≥",
    neq: "≠", approx: "≈", infty: "∞", partial: "∂", nabla: "∇", sum: "∑", prod: "∏", int: "∫",
    oint: "∮", to: "→", rightarrow: "→", leftarrow: "←", leftrightarrow: "↔", in: "∈", notin: "∉",
    subset: "⊂", supset: "⊃", subseteq: "⊆", supseteq: "⊇", cup: "∪", cap: "∩", forall: "∀",
    exists: "∃", neg: "¬", land: "∧", lor: "∨", ldots: "…", cdots: "⋯", quad: "  ", qquad: "    ", degree: "°",
  };
  const WORDS = new Set(["sin", "cos", "tan", "log", "ln", "lim", "max", "min", "det"]);
  function mathRun(text) { return text ? `<m:r><m:t>${xml(text)}</m:t></m:r>` : ""; }
  function tokenizeLatex(source) {
    const tokens = [];
    for (let index = 0; index < source.length;) {
      const char = source[index];
      if (/\s/.test(char)) { index += 1; continue; }
      if (char === "\\") {
        if (source[index + 1] === "\\") { tokens.push({ type: "row" }); index += 2; continue; }
        const match = source.slice(index + 1).match(/^[A-Za-z]+/);
        if (match) { tokens.push({ type: "command", value: match[0] }); index += match[0].length + 1; continue; }
        if (index + 1 < source.length) { tokens.push({ type: "char", value: source[index + 1] }); index += 2; continue; }
      }
      tokens.push({ type: ({ "{": "open", "}": "close", "^": "sup", "_": "sub", "&": "cell" })[char] || "char", value: char });
      index += 1;
    }
    return tokens;
  }
  function latexToOmml(source) {
    const matrix = source.match(/\\begin\{(?:bmatrix|pmatrix|matrix)\}([\s\S]*?)\\end\{(?:bmatrix|pmatrix|matrix)\}/);
    if (matrix) {
      const rows = matrix[1].split(/\\\\/).map((rowText) => rowText.split("&"));
      const body = rows.map((cells) => `<m:mr>${cells.map((cell) => `<m:e>${latexToOmml(cell.trim())}</m:e>`).join("")}</m:mr>`).join("");
      return `<m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr><m:e><m:m>${body}</m:m></m:e></m:d>`;
    }
    const tokens = tokenizeLatex(source);
    let pos = 0;
    function group() {
      if (tokens[pos]?.type === "open") { pos += 1; const value = sequence("close"); if (tokens[pos]?.type === "close") pos += 1; return value; }
      return atom();
    }
    function atom() {
      const token = tokens[pos++];
      if (!token) return "";
      if (token.type === "open") { const value = sequence("close"); if (tokens[pos]?.type === "close") pos += 1; return value; }
      if (token.type === "command") {
        if (["frac", "dfrac", "tfrac"].includes(token.value)) return `<m:f><m:num>${group()}</m:num><m:den>${group()}</m:den></m:f>`;
        if (token.value === "sqrt") return `<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>${group()}</m:e></m:rad>`;
        if (["text", "mathrm", "operatorname"].includes(token.value)) return group();
        if (["left", "right", "displaystyle"].includes(token.value)) return "";
        return mathRun(SYMBOLS[token.value] || (WORDS.has(token.value) ? token.value : `\\${token.value}`));
      }
      return mathRun(token.value || "");
    }
    function scripted(base) {
      let sub = "", sup = "";
      while (["sub", "sup"].includes(tokens[pos]?.type)) { const type = tokens[pos++].type; if (type === "sub") sub = group(); else sup = group(); }
      if (sub && sup) return `<m:sSubSup><m:e>${base}</m:e><m:sub>${sub}</m:sub><m:sup>${sup}</m:sup></m:sSubSup>`;
      if (sub) return `<m:sSub><m:e>${base}</m:e><m:sub>${sub}</m:sub></m:sSub>`;
      if (sup) return `<m:sSup><m:e>${base}</m:e><m:sup>${sup}</m:sup></m:sSup>`;
      return base;
    }
    function sequence(until) {
      let result = "";
      while (pos < tokens.length && tokens[pos].type !== until) {
        if (["close", "cell", "row"].includes(tokens[pos].type)) break;
        result += scripted(atom());
      }
      return result;
    }
    return sequence("never");
  }
  function math(source, display = false) {
    const inner = latexToOmml(source.trim());
    return display ? `<m:oMathPara><m:oMath>${inner}</m:oMath></m:oMathPara>` : `<m:oMath>${inner}</m:oMath>`;
  }

  const INLINE_RE = /(\$\$[^$]+\$\$|\$[^$]+\$|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~)/g;
  function inline(source, font = "Arial", inherited = {}) {
    let output = "", cursor = 0;
    for (const match of source.matchAll(INLINE_RE)) {
      output += run(source.slice(cursor, match.index), { ...inherited, font });
      const token = match[0];
      if (token.startsWith("$$")) output += math(token.slice(2, -2));
      else if (token.startsWith("$")) output += math(token.slice(1, -1));
      else if (token.startsWith("`")) output += run(token.slice(1, -1), { ...inherited, font, mono: true });
      else if (token.startsWith("**")) output += inline(token.slice(2, -2), font, { ...inherited, bold: true });
      else if (token.startsWith("~~")) output += inline(token.slice(2, -2), font, { ...inherited, strike: true });
      else output += inline(token.slice(1, -1), font, { ...inherited, italic: true });
      cursor = match.index + token.length;
    }
    return output + run(source.slice(cursor), { ...inherited, font });
  }
  function paragraph(content, options = {}) {
    const alignment = options.center ? '<w:jc w:val="center"/>' : options.rtl ? '<w:jc w:val="start"/>' : "";
    const pPr = [options.style ? `<w:pStyle w:val="${xml(options.style)}"/>` : "", options.rtl ? "<w:bidi/>" : "", alignment,
      options.compact ? '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>' : options.center ? '<w:spacing w:before="60" w:after="60"/>' : "",
      options.numberId ? `<w:numPr><w:ilvl w:val="0"/><w:numId w:val="${options.numberId}"/></w:numPr>` : "",
      options.indent ? `<w:ind w:${options.indentSide || "left"}="${options.indent}"/>` : "", options.shade ? `<w:shd w:val="clear" w:fill="${options.shade === true ? "F3F4F6" : options.shade}"/>` : "", options.border ? `<w:pBdr><w:${options.border} w:val="single" w:sz="${options.border === "bottom" ? 6 : 14}" w:space="${options.border === "bottom" ? 4 : 5}" w:color="${options.borderColor || "5B7FA3"}"/></w:pBdr>` : ""].join("");
    return `<w:p>${pPr ? `<w:pPr>${pPr}</w:pPr>` : ""}${content}</w:p>`;
  }
  function splitTableRow(line) {
    let value = String(line).trim();
    if (value.startsWith("|")) value = value.slice(1);
    if (value.endsWith("|")) value = value.slice(0, -1);
    const cells = [];
    let buffer = "", codeFence = 0;
    for (let index = 0; index < value.length; index += 1) {
      const char = value[index];
      if (char === "\\" && value[index + 1] === "|") { buffer += "|"; index += 1; continue; }
      if (char === "`") {
        let end = index;
        while (value[end] === "`") end += 1;
        const length = end - index;
        codeFence = codeFence === length ? 0 : codeFence || length;
        buffer += "`".repeat(length);
        index = end - 1;
        continue;
      }
      if (char === "|" && codeFence === 0) { cells.push(buffer.trim()); buffer = ""; continue; }
      buffer += char;
    }
    cells.push(buffer.trim());
    return cells;
  }
  function table(lines, font) {
    let headerSeen = false, header = null;
    const rows = [];
    for (const line of lines) {
      const cells = splitTableRow(line);
      if (cells.every((cell) => /^:?-+:?$/.test(cell))) { headerSeen = true; continue; }
      if (!headerSeen) header = cells; else rows.push(cells);
    }
    const allRows = header ? [header, ...rows] : rows;
    if (!allRows.length) return "";
    const columns = Math.max(...allRows.map((row) => row.length));
    const rtl = allRows.some((row) => row.some(isRtl));
    const grid = `<w:tblGrid>${Array.from({ length: columns }, () => '<w:gridCol w:w="2400"/>').join("")}</w:tblGrid>`;
    const body = allRows.map((cells, rowIndex) => `<w:tr>${Array.from({ length: columns }, (_, index) => {
      const value = cells[index] || "";
      const shade = rowIndex === 0 ? '<w:shd w:val="clear" w:fill="EAF0F6"/>' : rowIndex % 2 === 0 ? '<w:shd w:val="clear" w:fill="F8FAFC"/>' : "";
      return `<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/><w:vAlign w:val="center"/>${shade}</w:tcPr>${paragraph(rowIndex === 0 ? inline(value, font, { bold: true }) : inline(value, font), { rtl: rtl || isRtl(value), center: true, compact: true })}</w:tc>`;
    }).join("")}</w:tr>`).join("");
    return `<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/><w:jc w:val="center"/>${rtl ? "<w:bidiVisual/>" : ""}<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar><w:tblBorders><w:top w:val="single" w:sz="6" w:color="B7C9DB"/><w:left w:val="single" w:sz="6" w:color="B7C9DB"/><w:bottom w:val="single" w:sz="6" w:color="B7C9DB"/><w:right w:val="single" w:sz="6" w:color="B7C9DB"/><w:insideH w:val="single" w:sz="4" w:color="D9E2EC"/><w:insideV w:val="single" w:sz="4" w:color="D9E2EC"/></w:tblBorders></w:tblPr>${grid}${body}</w:tbl>`;
  }
  function markdownToDocumentXml(markdown, options = {}) {
    const font = options.font || "Arial", lines = String(markdown).replace(/\r\n?/g, "\n").split("\n"), body = [];
    let tableLines = [], inFence = false, fenceChar = "", fenceLength = 0, codeLines = [], codeLanguage = "", inDisplayMath = false, mathLines = [];
    function flushTable() { if (tableLines.length) { body.push(table(tableLines, font)); tableLines = []; } }
    function flushCode() {
      if (!codeLines.length && !codeLanguage) return;
      const label = codeLanguage ? `${run(codeLanguage, { mono: true, bold: true })}<w:r><w:br/></w:r>` : "";
      body.push(paragraph(`${label}${run(codeLines.join("\n"), { mono: true })}`, { indent: 360, border: "left", shade: true }));
      codeLines = []; codeLanguage = ""; fenceChar = ""; fenceLength = 0;
    }
    function flushMath() {
      const latex = mathLines.join(" ").trim();
      if (latex) body.push(paragraph(math(latex, true), { center: true }));
      mathLines = [];
    }
    for (const raw of lines) {
      const line = raw.replace(/\s+$/, "");
      const fence = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
      if (fence) {
        if (inFence) {
          const closes = fence[1][0] === fenceChar && fence[1].length >= fenceLength && !fence[2].trim();
          if (closes) { flushCode(); inFence = false; continue; }
          codeLines.push(line); continue;
        }
        inFence = true; fenceChar = fence[1][0]; fenceLength = fence[1].length;
        codeLanguage = fence[2].trim().split(/\s+/)[0] || "";
        continue;
      }
      if (inFence) { codeLines.push(line); continue; }
      if (line.trim() === "$$") { flushTable(); if (inDisplayMath) flushMath(); inDisplayMath = !inDisplayMath; continue; }
      if (inDisplayMath) { mathLines.push(line); continue; }
      if (line.startsWith("|")) { tableLines.push(line); continue; }
      flushTable();
      const heading = line.match(/^(#{1,6})\s+(.+)$/), unordered = line.match(/^[-*+]\s+(.+)$/), ordered = line.match(/^\d+\.\s+(.+)$/);
      if (heading) body.push(paragraph(inline(heading[2], font), { style: `Heading${heading[1].length}`, rtl: isRtl(heading[2]) }));
      else if (/^\$\$.+\$\$$/.test(line)) body.push(paragraph(math(line.slice(2, -2), true), { center: true }));
      else if (/^(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) body.push(paragraph("", { border: "bottom" }));
      else if (line.startsWith("> ")) { const rtl = isRtl(line); body.push(paragraph(inline(line.slice(2), font, { italic: true }), { rtl, indent: 360, indentSide: rtl ? "right" : "left", border: rtl ? "right" : "left", shade: "F8FAFC" })); }
      else if (unordered) body.push(paragraph(inline(unordered[1], font), { rtl: isRtl(unordered[1]), numberId: 1 }));
      else if (ordered) body.push(paragraph(inline(ordered[1], font), { rtl: isRtl(ordered[1]), numberId: 2 }));
      else if (line.trim()) body.push(paragraph(inline(line, font), { rtl: isRtl(line) }));
    }
    flushTable(); if (inFence || codeLines.length || codeLanguage) flushCode(); if (inDisplayMath) flushMath();
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="${W}" xmlns:m="${M}"><w:body>${body.join("")}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>`;
  }
  function stylesXml(baseFont) {
    const headings = [[1, 42, "17365D", 0, 100], [2, 32, "1F4E79", 180, 60], [3, 27, "334155", 140, 40], [4, 24, "334155", 120, 40], [5, 22, "475569", 100, 30], [6, 21, "475569", 80, 30]];
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="${W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="${xml(baseFont)}" w:hAnsi="${xml(baseFont)}" w:cs="Arial"/><w:sz w:val="23"/><w:szCs w:val="23"/><w:color w:val="1F2937"/><w:lang w:val="en-US" w:bidi="he-IL"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>${headings.map(([level, size, color, before, after]) => `<w:style w:type="paragraph" w:styleId="Heading${level}"><w:name w:val="heading ${level}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="${before}" w:after="${after}"/>${level === 1 ? '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="D9E2F3"/></w:pBdr>' : ""}</w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:b/><w:color w:val="${color}"/><w:sz w:val="${size}"/><w:szCs w:val="${size}"/></w:rPr></w:style>`).join("")}<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>`;
  }
  const numberingXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="${W}"><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>`;

  const crcTable = (() => { const table = new Uint32Array(256); for (let n = 0; n < 256; n += 1) { let c = n; for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1); table[n] = c >>> 0; } return table; })();
  function crc32(bytes) { let crc = 0xffffffff; for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8); return (crc ^ 0xffffffff) >>> 0; }
  function u16(value) { return Uint8Array.of(value & 255, (value >>> 8) & 255); }
  function u32(value) { return Uint8Array.of(value & 255, (value >>> 8) & 255, (value >>> 16) & 255, (value >>> 24) & 255); }
  function concat(parts) { const result = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0)); let offset = 0; for (const part of parts) { result.set(part, offset); offset += part.length; } return result; }
  function zip(files) {
    const local = [], central = []; let offset = 0;
    for (const [name, content] of Object.entries(files)) {
      const nameBytes = encoder.encode(name), data = typeof content === "string" ? encoder.encode(content) : content, crc = crc32(data);
      const header = concat([u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0), u32(crc), u32(data.length), u32(data.length), u16(nameBytes.length), u16(0), nameBytes]);
      local.push(header, data);
      central.push(concat([u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0), u32(crc), u32(data.length), u32(data.length), u16(nameBytes.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(offset), nameBytes]));
      offset += header.length + data.length;
    }
    const centralBytes = concat(central);
    return concat([...local, centralBytes, u32(0x06054b50), u16(0), u16(0), u16(central.length), u16(central.length), u32(centralBytes.length), u32(offset), u16(0)]);
  }
  function convert(markdown, options = {}) {
    const baseFont = options.baseFont || "Arial";
    return zip({
      "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>',
      "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>',
      "word/document.xml": markdownToDocumentXml(markdown, options), "word/styles.xml": stylesXml(baseFont), "word/numbering.xml": numberingXml,
      "word/_rels/document.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>',
      "docProps/core.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>md2docx document</dc:title><dc:creator>md2docx local converter</dc:creator></cp:coreProperties>',
      "docProps/app.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>md2docx</Application></Properties>',
    });
  }
  function toBase64(bytes) { let result = ""; for (let index = 0; index < bytes.length; index += 0x8000) result += String.fromCharCode(...bytes.subarray(index, index + 0x8000)); return btoa(result); }
  function toBlob(markdown, options = {}) { return new Blob([convert(markdown, options)], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }); }
  return { convert, toBase64, toBlob, latexToOmml, markdownToDocumentXml };
});
