const test = require("node:test");
const assert = require("node:assert/strict");
const capture = require("../products/chrome-extension/content/llm-capture.js");

function text(value) { return { nodeType: 3, nodeValue: value, textContent: value }; }
function element(tagName, attributes = {}, children = []) {
  const node = {
    nodeType: 1,
    tagName: tagName.toUpperCase(),
    childNodes: children,
    children: children.filter((child) => child.nodeType === 1),
    className: attributes.class || "",
    getAttribute(name) { return attributes[name] ?? null; },
    matches(selector) { return selector.startsWith("annotation") && tagName === "annotation" && /tex/i.test(attributes.encoding || ""); },
    querySelector(selector) {
      const all = walk(this).filter((child) => child !== this);
      if (selector === "code") return all.find((child) => child.tagName === "CODE") || null;
      if (selector.startsWith("annotation")) return all.find((child) => child.tagName === "ANNOTATION" && /tex/i.test(child.getAttribute("encoding") || "")) || null;
      return null;
    },
  };
  Object.defineProperty(node, "textContent", { get() { return children.map((child) => child.textContent || child.nodeValue || "").join(""); } });
  Object.defineProperty(node, "innerText", { get() { return this.textContent; } });
  return node;
}
function walk(node) { return [node, ...(node.children || []).flatMap(walk)]; }

test("detects supported LLM hosts without prompt integration", () => {
  assert.equal(capture.detectProvider("chatgpt.com"), "chatgpt");
  assert.equal(capture.detectProvider("claude.ai"), "claude");
  assert.equal(capture.detectProvider("gemini.google.com"), "gemini");
  assert.equal(capture.detectProvider("copilot.microsoft.com"), "copilot");
  assert.equal(capture.detectProvider("unknown.example"), "generic");
});

test("reconstructs headings, inline styles, lists, tables, code, and TeX", () => {
  const response = element("article", { class: "markdown" }, [
    element("h2", {}, [text("Result")]),
    element("p", {}, [text("Use "), element("strong", {}, [text("bold")]), text(" and "), element("code", {}, [text("x()")]), text(".")]),
    element("ul", {}, [element("li", {}, [text("First")]), element("li", {}, [text("Second")])]),
    element("table", {}, [
      element("thead", {}, [element("tr", {}, [element("th", {}, [text("A")]), element("th", {}, [text("B")])])]),
      element("tbody", {}, [element("tr", {}, [element("td", {}, [text("1")]), element("td", {}, [text("2")])])]),
    ]),
    element("pre", {}, [element("code", { class: "language-js" }, [text("const x = 1;")])]),
    element("span", { class: "katex", "data-latex": "x^2" }, [text("rendered duplicate")]),
  ]);
  const markdown = capture.cleanMarkdown(capture.inlineText(response));
  for (const expected of ["## Result", "**bold**", "`x()`", "- First", "| A | B |", "```js", "$x^2$"]) assert.ok(markdown.includes(expected), expected);
  assert.ok(!markdown.includes("rendered duplicate"));
});

test("captures the latest matching response", () => {
  const first = element("article", { "data-message-author-role": "assistant" }, [text("Old response")]);
  const latest = element("article", { "data-message-author-role": "assistant" }, [text("Latest response")]);
  const document = {
    location: { hostname: "chatgpt.com" }, title: "Chat",
    querySelectorAll(selector) {
      if (selector === "*") return [];
      if (selector === '[data-message-author-role="assistant"]') return [first, latest];
      return [];
    },
  };
  const result = capture.captureLatest(document, "auto");
  assert.equal(result.ok, true);
  assert.equal(result.provider, "chatgpt");
  assert.equal(result.markdown, "Latest response");
});

test("reconstructs arbitrary code languages and extended inline styles", () => {
  const root = element("div", {}, [
    element("mark", {}, [text("highlight")]), text(" "),
    element("u", {}, [text("underline")]), text(" "),
    element("sub", {}, [text("2")]), text(" "),
    element("pre", { "data-language": "bash" }, [element("code", {}, [text("echo ok")])]),
  ]);
  const markdown = capture.cleanMarkdown(capture.inlineText(root));
  assert.match(markdown, /==highlight==/);
  assert.match(markdown, /__underline__/);
  assert.match(markdown, /~2~/);
  assert.match(markdown, /```bash\necho ok\n```/);
});

test("escapes literal Markdown punctuation and preserves bracket-heavy inline code", () => {
  const root = element("p", {}, [
    text("Literal *stars* [brackets](x) $cash$ #hash ~tilde~ {curly} > quote! "),
    element("code", {}, [text("call(`x`, [{a: 1}])")]),
  ]);
  const markdown = capture.cleanMarkdown(capture.inlineText(root));
  for (const escaped of ["\\*stars\\*", "\\[brackets\\](x)", "\\$cash\\$", "\\#hash", "\\~tilde\\~", "\\{curly\\}", "\\! "]) {
    assert.ok(markdown.includes(escaped), `${escaped}: ${markdown}`);
  }
  assert.match(markdown, /``call\(`x`, \[\{a: 1\}\]\)``/);
});
