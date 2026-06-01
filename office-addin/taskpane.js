/* global Office, Word */

const STORAGE_KEYS = {
  apiBase: "md2docx_office_api_base",
  converterApiKey: "md2docx_office_converter_api_key",
  provider: "md2docx_office_provider",
  providerApiKey: "md2docx_office_provider_api_key",
  model: "md2docx_office_model",
};

const DEFAULT_MODELS = {
  openai: "gpt-4.1-mini",
  anthropic: "claude-3-5-sonnet-latest",
  gemini: "gemini-2.0-flash",
};

const TOOL_SPEC = [
  "You are an editing agent for Microsoft Word.",
  "Decide exactly one action and respond as strict JSON (no markdown fences, no extra text):",
  '{"action":"insert_markdown|replace_selection|reply","markdown":"...","reply":"..."}',
  "Use insert_markdown for adding new content at the cursor.",
  "Use replace_selection for editing/replacing selected text.",
  "Use reply only when you need clarification.",
  "If action is reply, keep markdown empty.",
].join("\n");

const els = {};

Office.onReady(() => {
  bindDom();
  loadState();
  wireEvents();
  refreshSelection().catch((err) => setStatus(err.message, true));
});

function bindDom() {
  [
    "apiBase",
    "converterApiKey",
    "provider",
    "model",
    "providerApiKey",
    "instruction",
    "selectionPreview",
    "markdownDraft",
    "refreshSelection",
    "askAi",
    "askAndApply",
    "insertDraft",
    "replaceSelection",
    "status",
  ].forEach((id) => {
    els[id] = document.getElementById(id);
  });
}

function wireEvents() {
  els.refreshSelection.addEventListener("click", () => {
    refreshSelection().catch((err) => setStatus(err.message, true));
  });

  els.askAi.addEventListener("click", () => {
    askAi(false).catch((err) => setStatus(err.message, true));
  });

  els.askAndApply.addEventListener("click", () => {
    askAi(true).catch((err) => setStatus(err.message, true));
  });

  els.insertDraft.addEventListener("click", () => {
    insertMarkdownFromDraft(false).catch((err) => setStatus(err.message, true));
  });

  els.replaceSelection.addEventListener("click", () => {
    insertMarkdownFromDraft(true).catch((err) => setStatus(err.message, true));
  });

  els.provider.addEventListener("change", () => {
    if (!els.model.value.trim()) {
      els.model.value = DEFAULT_MODELS[els.provider.value] || "";
    }
    persistState();
  });

  [
    "apiBase",
    "converterApiKey",
    "provider",
    "model",
    "providerApiKey",
  ].forEach((field) => {
    els[field].addEventListener("input", persistState);
  });
}

function loadState() {
  els.apiBase.value = localStorage.getItem(STORAGE_KEYS.apiBase) || "https://md2docx.app";
  els.converterApiKey.value = localStorage.getItem(STORAGE_KEYS.converterApiKey) || "";

  const provider = localStorage.getItem(STORAGE_KEYS.provider) || "openai";
  els.provider.value = provider;

  els.model.value =
    localStorage.getItem(STORAGE_KEYS.model) ||
    DEFAULT_MODELS[provider] ||
    "";

  els.providerApiKey.value = localStorage.getItem(STORAGE_KEYS.providerApiKey) || "";
}

function persistState() {
  localStorage.setItem(STORAGE_KEYS.apiBase, els.apiBase.value.trim());
  localStorage.setItem(STORAGE_KEYS.converterApiKey, els.converterApiKey.value.trim());
  localStorage.setItem(STORAGE_KEYS.provider, els.provider.value);
  localStorage.setItem(STORAGE_KEYS.model, els.model.value.trim());
  localStorage.setItem(STORAGE_KEYS.providerApiKey, els.providerApiKey.value.trim());
}

async function refreshSelection() {
  const text = await getSelectionText();
  els.selectionPreview.value = text || "";
  setStatus(text ? "Selection refreshed." : "No selected text.");
}

async function askAi(applyAction) {
  const provider = els.provider.value;
  const providerApiKey = els.providerApiKey.value.trim();
  const model = els.model.value.trim() || DEFAULT_MODELS[provider];
  const instruction = els.instruction.value.trim();

  if (!providerApiKey) {
    throw new Error("Provider API key is required.");
  }
  if (!instruction) {
    throw new Error("Instruction is required.");
  }

  setBusy(true, "Calling AI provider...");

  const selectedText = await getSelectionText();
  els.selectionPreview.value = selectedText || "";

  const prompt = applyAction
    ? [
        TOOL_SPEC,
        "",
        "Instruction:",
        instruction,
        "",
        "Current selected text:",
        selectedText || "<empty>",
      ].join("\n")
    : [
        "Return only markdown (no code fences).",
        "If text is selected, edit that selection according to the instruction.",
        "If no text is selected, produce new markdown content.",
        "",
        "Instruction:",
        instruction,
        "",
        "Current selected text:",
        selectedText || "<empty>",
      ].join("\n");

  const responseText = await callProvider({
    provider,
    apiKey: providerApiKey,
    model,
    prompt,
  });

  if (!applyAction) {
    els.markdownDraft.value = responseText;
    setBusy(false, "AI response received. Review and insert when ready.");
    return;
  }

  const toolAction = parseToolAction(responseText);
  if (toolAction.action === "reply") {
    const reply = toolAction.reply || "The model requested clarification.";
    setBusy(false, reply);
    return;
  }

  if (!toolAction.markdown.trim()) {
    throw new Error("Tool action did not include markdown content.");
  }

  els.markdownDraft.value = toolAction.markdown;
  await insertMarkdown(toolAction.markdown, toolAction.action === "replace_selection");
  setBusy(false, `Applied action: ${toolAction.action}.`);
}

function parseToolAction(raw) {
  const fallback = {
    action: "reply",
    markdown: "",
    reply: raw,
  };

  const jsonText = extractJsonObject(raw);
  if (!jsonText) return fallback;

  try {
    const parsed = JSON.parse(jsonText);
    const action = ["insert_markdown", "replace_selection", "reply"].includes(parsed.action)
      ? parsed.action
      : "reply";
    return {
      action,
      markdown: typeof parsed.markdown === "string" ? parsed.markdown : "",
      reply: typeof parsed.reply === "string" ? parsed.reply : "",
    };
  } catch {
    return fallback;
  }
}

function extractJsonObject(text) {
  const trimmed = text.trim();
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    return trimmed;
  }

  const match = trimmed.match(/\{[\s\S]*\}/);
  return match ? match[0] : "";
}

async function insertMarkdownFromDraft(replaceSelection) {
  const markdown = els.markdownDraft.value.trim();
  if (!markdown) {
    throw new Error("Markdown draft is empty.");
  }

  setBusy(true, "Converting markdown to DOCX...");
  await insertMarkdown(markdown, replaceSelection);
  setBusy(false, replaceSelection ? "Selection replaced." : "Draft inserted.");
}

async function insertMarkdown(markdown, replaceSelection) {
  const apiBase = els.apiBase.value.trim().replace(/\/$/, "");
  if (!apiBase) {
    throw new Error("md2docx API base URL is required.");
  }

  const converterApiKey = els.converterApiKey.value.trim();
  const headers = {
    "Content-Type": "application/json",
  };
  if (converterApiKey) {
    headers["X-Api-Key"] = converterApiKey;
  }

  const res = await fetch(`${apiBase}/convert/base64`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      markdown,
      font: "Arial",
      base_font: "Times New Roman",
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = body?.detail?.message || body?.detail || body?.error || res.statusText;
    throw new Error(`Conversion failed: ${msg}`);
  }

  const payload = await res.json();
  if (!payload.docx_base64) {
    throw new Error("Invalid conversion response: missing base64 data.");
  }

  await Word.run(async (context) => {
    const selection = context.document.getSelection();
    selection.insertFileFromBase64(
      payload.docx_base64,
      replaceSelection ? Word.InsertLocation.replace : Word.InsertLocation.after
    );
    await context.sync();
  });
}

async function callProvider({ provider, apiKey, model, prompt }) {
  if (provider === "openai") {
    return callOpenAI(apiKey, model, prompt);
  }
  if (provider === "anthropic") {
    return callAnthropic(apiKey, model, prompt);
  }
  if (provider === "gemini") {
    return callGemini(apiKey, model, prompt);
  }
  throw new Error(`Unsupported provider: ${provider}`);
}

async function callOpenAI(apiKey, model, prompt) {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      temperature: 0.2,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload?.error?.message || "OpenAI request failed.");
  }

  return payload?.choices?.[0]?.message?.content || "";
}

async function callAnthropic(apiKey, model, prompt) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: 1200,
      temperature: 0.2,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload?.error?.message || "Anthropic request failed.");
  }

  const content = Array.isArray(payload?.content) ? payload.content : [];
  return content
    .filter((item) => item?.type === "text")
    .map((item) => item.text)
    .join("\n")
    .trim();
}

async function callGemini(apiKey, model, prompt) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      contents: [
        {
          role: "user",
          parts: [{ text: prompt }],
        },
      ],
      generationConfig: {
        temperature: 0.2,
      },
    }),
  });

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload?.error?.message || "Gemini request failed.");
  }

  const parts = payload?.candidates?.[0]?.content?.parts || [];
  return parts
    .map((part) => part?.text || "")
    .join("\n")
    .trim();
}

async function getSelectionText() {
  return Word.run(async (context) => {
    const selection = context.document.getSelection();
    selection.load("text");
    await context.sync();
    return selection.text || "";
  });
}

function setBusy(on, message) {
  [
    "refreshSelection",
    "askAi",
    "askAndApply",
    "insertDraft",
    "replaceSelection",
  ].forEach((id) => {
    els[id].disabled = on;
  });

  if (message) {
    els.status.className = on ? "status busy" : "status";
    els.status.textContent = message;
  }
}

function setStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.className = isError ? "status error" : "status";
}
