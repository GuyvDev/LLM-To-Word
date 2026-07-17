/* Capture the latest visible LLM response and reconstruct clean Markdown. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root.document && !root.__MD2DOCX_LLM_CAPTURE__) {
    root.__MD2DOCX_LLM_CAPTURE__ = api;
    if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
        if (message.type !== "MD2DOCX_CAPTURE_LLM") return false;
        try { sendResponse(api.captureLatest(root.document, message.provider || "auto")); }
        catch (error) { sendResponse({ ok: false, error: error.message }); }
        return false;
      });
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PROVIDERS = {
    chatgpt: {
      label: "ChatGPT",
      hosts: [/(^|\.)chatgpt\.com$/, /(^|\.)chat\.openai\.com$/],
      selectors: ['[data-message-author-role="assistant"] .markdown', '[data-message-author-role="assistant"]'],
    },
    claude: {
      label: "Claude",
      hosts: [/(^|\.)claude\.ai$/],
      selectors: ['[data-testid="assistant-message"]', '.font-claude-message', '[data-is-streaming] .prose'],
    },
    gemini: {
      label: "Gemini",
      hosts: [/(^|\.)gemini\.google\.com$/],
      selectors: ['model-response .model-response-text', 'model-response message-content', 'model-response'],
    },
    copilot: {
      label: "Microsoft Copilot",
      hosts: [/(^|\.)copilot\.microsoft\.com$/, /(^|\.)m365\.cloud\.microsoft$/],
      selectors: ['cib-message-group[source="bot"] cib-message', '[data-content="ai-message"]', '[data-testid="ai-message"]'],
    },
    grok: {
      label: "Grok",
      hosts: [/(^|\.)grok\.com$/, /(^|\.)x\.com$/],
      selectors: ['[data-testid="assistant-message"]', '[data-testid="message-bubble"] .prose', '.message-bubble .prose'],
    },
    perplexity: {
      label: "Perplexity",
      hosts: [/(^|\.)perplexity\.ai$/],
      selectors: ['[data-testid="answer"]', '[data-testid="copilot-answer"]', '.prose'],
    },
    deepseek: {
      label: "DeepSeek",
      hosts: [/(^|\.)chat\.deepseek\.com$/],
      selectors: ['.ds-markdown', '[class*="ds-markdown"]', '[class*="markdown"]'],
    },
    generic: {
      label: "Generic LLM page",
      hosts: [],
      selectors: [
        '[data-message-author-role="assistant"]', '[data-role="assistant"]',
        '[data-testid*="assistant"]', '[class*="assistant-message"]',
        '[class*="model-response"]', '.markdown', '.prose', 'article',
      ],
    },
  };

  function detectProvider(hostname = "") {
    const normalized = hostname.toLowerCase().replace(/^www\./, "");
    for (const [name, definition] of Object.entries(PROVIDERS)) {
      if (name !== "generic" && definition.hosts.some((pattern) => pattern.test(normalized))) return name;
    }
    return "generic";
  }

  function shadowRoots(document) {
    const roots = [document];
    for (let index = 0; index < roots.length; index += 1) {
      const root = roots[index];
      if (!root.querySelectorAll) continue;
      for (const element of root.querySelectorAll("*")) if (element.shadowRoot) roots.push(element.shadowRoot);
    }
    return roots;
  }

  function deepQueryAll(document, selector) {
    const found = [];
    for (const root of shadowRoots(document)) {
      try { found.push(...root.querySelectorAll(selector)); } catch { /* Provider DOM changed. */ }
    }
    return [...new Set(found)];
  }

  function isVisible(element) {
    if (!element || element.getAttribute?.("aria-hidden") === "true") return false;
    if (typeof getComputedStyle === "function") {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") return false;
    }
    return true;
  }

  function selectedFragment(document) {
    const selection = document.defaultView?.getSelection?.();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
    const wrapper = document.createElement("div");
    for (let index = 0; index < selection.rangeCount; index += 1) wrapper.appendChild(selection.getRangeAt(index).cloneContents());
    return wrapper;
  }

  function chooseLatest(document, provider) {
    const definition = PROVIDERS[provider] || PROVIDERS.generic;
    for (const selector of definition.selectors) {
      const candidates = deepQueryAll(document, selector).filter(isVisible).filter((element) => (element.innerText || element.textContent || "").trim().length > 1);
      if (candidates.length) return candidates[candidates.length - 1];
    }
    return null;
  }

  function classText(element) {
    return typeof element.className === "string" ? element.className : element.getAttribute?.("class") || "";
  }

  function mathLatex(element) {
    const direct = element.getAttribute?.("data-latex") || element.getAttribute?.("data-tex") || element.getAttribute?.("data-math") || element.getAttribute?.("alttext");
    if (direct) return direct;
    const annotation = element.matches?.('annotation[encoding*="tex" i]') ? element : element.querySelector?.('annotation[encoding*="tex" i]');
    return annotation?.textContent?.trim() || "";
  }

  function inlineText(node, context = {}) {
    if (!node) return "";
    if (node.nodeType === 3) {
      const value = String(node.nodeValue || "").replace(/\u00a0/g, " ");
      return context.literal ? value : escapeMarkdownText(value);
    }
    if (node.nodeType !== 1 && node.nodeType !== 11) return "";
    const tag = String(node.tagName || "").toLowerCase();
    if (["script", "style", "button", "svg", "noscript", "template"].includes(tag)) return "";
    if (node.getAttribute?.("aria-hidden") === "true") return "";
    const testId = node.getAttribute?.("data-testid") || "";
    if (/copy|feedback|action|toolbar/i.test(testId)) return "";

    const classes = classText(node);
    const tex = /katex|mathjax|math-container|math-block/i.test(classes) || ["math", "mjx-container"].includes(tag) ? mathLatex(node) : "";
    if (tex) {
      const display = node.getAttribute?.("display") === "block" || /display|block/i.test(classes);
      return display ? `\n\n$$${tex}$$\n\n` : `$${tex}$`;
    }

    if (tag === "br") return "\n";
    if (tag === "pre") {
      const code = (node.textContent || "").replace(/^\n|\n$/g, "");
      const codeElement = node.querySelector?.("code");
      const declaredLanguage = codeElement?.getAttribute?.("data-language") || node.getAttribute?.("data-language") || "";
      const classLanguage = [codeElement?.getAttribute?.("class"), node.getAttribute?.("class")]
        .filter(Boolean).map((value) => String(value).match(/(?:^|\s)(?:language|lang)-([\w.+-]+)/i)?.[1] || "").find(Boolean) || "";
      const language = String(declaredLanguage).trim().split(/\s+/)[0] || classLanguage;
      return `\n\n\`\`\`${language}\n${code}\n\`\`\`\n\n`;
    }
    const children = (childContext = context) => Array.from(node.childNodes || []).map((child) => inlineText(child, childContext)).join("");
    if (tag === "code") {
      if (context.inPre) return node.textContent || "";
      const literal = String(node.textContent || "");
      const longest = Math.max(0, ...(literal.match(/`+/g) || []).map((value) => value.length));
      const fence = "`".repeat(longest + 1);
      const padding = /^`|`$|^\s|\s$/.test(literal) ? " " : "";
      return `${fence}${padding}${literal}${padding}${fence}`;
    }
    if (["strong", "b"].includes(tag)) return `**${children()}**`;
    if (["em", "i"].includes(tag)) return `*${children()}*`;
    if (["s", "del", "strike"].includes(tag)) return `~~${children()}~~`;
    if (tag === "mark") return `==${children()}==`;
    if (tag === "ins") return `++${children()}++`;
    if (tag === "u") return `__${children()}__`;
    if (tag === "sub") return `~${children()}~`;
    if (tag === "sup") return `^${children()}^`;
    if (tag === "a") {
      const label = children().trim(), href = node.getAttribute?.("href") || "";
      const destination = String(href).replace(/>/g, "%3E").replace(/\s/g, (value) => encodeURIComponent(value));
      return href && label && !href.startsWith("javascript:") ? `[${label}](<${destination}>)` : label;
    }
    if (tag === "img") return node.getAttribute?.("alt") ? `![${node.getAttribute("alt")}](${node.getAttribute("src") || ""})` : "";
    if (/^h[1-6]$/.test(tag)) return `\n\n${"#".repeat(Number(tag[1]))} ${children().trim()}\n\n`;
    if (tag === "blockquote") return `\n\n${children().trim().split("\n").map((line) => `> ${line}`).join("\n")}\n\n`;
    if (tag === "hr") return "\n\n---\n\n";
    if (tag === "table") return tableToMarkdown(node);
    if (tag === "ul" || tag === "ol") return listToMarkdown(node, tag === "ol", context.depth || 0);
    if (tag === "li") return children();
    const value = children();
    if (["p", "article", "section"].includes(tag)) return `\n\n${value.trim()}\n\n`;
    if (tag === "div" && /markdown|prose|response|message|content/i.test(classes)) return `${value}\n`;
    return value;
  }

  function directChildren(element, tags) {
    return Array.from(element.children || []).filter((child) => tags.includes(String(child.tagName || "").toLowerCase()));
  }

  function listToMarkdown(list, ordered, depth) {
    const items = directChildren(list, ["li"]);
    const lines = items.map((item, index) => {
      const parts = Array.from(item.childNodes || []);
      const nested = parts.filter((node) => ["ul", "ol"].includes(String(node.tagName || "").toLowerCase()));
      const content = parts.filter((node) => !nested.includes(node)).map((node) => inlineText(node, { depth: depth + 1 })).join("").trim();
      const prefix = ordered ? `${index + 1}. ` : "- ";
      const nestedText = nested.map((node) => listToMarkdown(node, String(node.tagName).toLowerCase() === "ol", depth + 1).trimEnd()).join("\n");
      return `${"  ".repeat(depth)}${prefix}${content}${nestedText ? `\n${nestedText}` : ""}`;
    });
    return `\n${lines.join("\n")}\n`;
  }

  function tableToMarkdown(table) {
    const rows = deepRows(table);
    if (!rows.length) return "";
    const values = rows.map((row) => directChildren(row, ["th", "td"]).map((cell) => cleanMarkdown(inlineText(cell)).replace(/\|/g, "\\|").replace(/\n/g, " ")));
    const width = Math.max(...values.map((row) => row.length));
    const normalized = values.map((row) => Array.from({ length: width }, (_, index) => row[index] || ""));
    const separator = Array.from({ length: width }, () => "---");
    return `\n\n| ${normalized[0].join(" | ")} |\n| ${separator.join(" | ")} |\n${normalized.slice(1).map((row) => `| ${row.join(" | ")} |`).join("\n")}\n\n`;
  }

  function deepRows(table) {
    const direct = directChildren(table, ["tr"]);
    if (direct.length) return direct;
    return directChildren(table, ["thead", "tbody", "tfoot"]).flatMap((group) => directChildren(group, ["tr"]));
  }

  function cleanMarkdown(value) {
    return String(value || "")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/^[ \t]+|[ \t]+$/gm, "")
      .trim();
  }

  function escapeMarkdownText(value) {
    return String(value || "")
      .replace(/\\/g, "\\\\")
      .replace(/([`*_[\]{}<>#$~^+=!])/g, "\\$1")
      .replace(/(^|\n)([ \t]*)([-+>])/g, "$1$2\\$3");
  }

  function captureLatest(document, requested = "auto") {
    const detected = detectProvider(document.location?.hostname || "");
    const provider = requested === "auto" ? detected : requested;
    const selected = provider === "selection" ? selectedFragment(document) : null;
    if (provider === "selection" && !selected) return { ok: false, error: "Select response text on the page first." };
    const element = selected || chooseLatest(document, provider);
    if (!element) return { ok: false, error: `Could not find a ${PROVIDERS[provider]?.label || "LLM"} response. Try Selected text or Generic.` };
    const markdown = cleanMarkdown(inlineText(element));
    if (!markdown) return { ok: false, error: "The captured response was empty." };
    return { ok: true, markdown, provider, providerLabel: PROVIDERS[provider]?.label || "Selected text", title: document.title || "LLM response" };
  }

  return { PROVIDERS, detectProvider, inlineText, cleanMarkdown, escapeMarkdownText, captureLatest, tableToMarkdown, listToMarkdown };
});
