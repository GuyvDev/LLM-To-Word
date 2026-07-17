/* global Office, Word, Md2Docx, wasm_bindgen */
const STORAGE_KEYS = { provider: "md2docx_provider", model: "md2docx_model" };
const DEFAULT_MODELS = { openai: "gpt-5", anthropic: "claude-sonnet-4-5", gemini: "gemini-2.5-flash" };
const FORMAT_SYSTEM_PROMPT = `You are an expert Microsoft Word writing copilot.
Return exactly one JSON object: {"action":"insert_markdown|replace_selection|reply","markdown":"...","reply":"..."}.
Use reply only for conversational answers or necessary clarification. For document content, produce clean Markdown in markdown.
Formatting contract:
- Use # through ###### for a real heading hierarchy; never fake headings with bold text.
- Use short paragraphs, Markdown lists, pipe tables, > blockquotes, fenced code, and --- separators appropriately.
- Write inline equations as $LaTeX$ and display equations as a single $$LaTeX$$ line. Prefer standard LaTeX commands.
- Preserve Hebrew and Arabic naturally. Do not reverse characters. Keep English/code/math tokens in their natural order inside RTL text.
- Use **bold**, *italic*, ~~strike~~, and backticks only for semantic emphasis.
- Do not emit HTML, base64, OOXML, XML, or Markdown code fences around the full response.
- If Word text is selected and the user asks to edit it, choose replace_selection. Otherwise choose insert_markdown.
The add-in deterministically converts your Markdown into native Word styles, lists, tables, BiDi runs, and OMML math.`;

const coreReady = typeof wasm_bindgen === "function"
  ? wasm_bindgen({ module_or_path: "/extension/core/md2docx_core_bg.wasm" }).then(() => true).catch((error) => { console.warn("Canonical core unavailable; using compatibility renderer", error); return false; })
  : Promise.resolve(false);

const els = {}, history = [];
Office.onReady(() => {
  for (const id of ["settingsToggle", "settings", "provider", "model", "providerApiKey", "selectionSummary", "refreshSelection", "chat", "prompt", "send", "sendApply", "markdownDraft", "insertDraft", "replaceSelection", "status"]) els[id] = document.getElementById(id);
  loadSettings(); wireEvents(); refreshSelection().catch(showError);
});

function wireEvents() {
  els.settingsToggle.addEventListener("click", () => { els.settings.hidden = !els.settings.hidden; els.settingsToggle.setAttribute("aria-expanded", String(!els.settings.hidden)); });
  els.refreshSelection.addEventListener("click", () => refreshSelection().catch(showError));
  els.send.addEventListener("click", () => sendChat(false).catch(showError));
  els.sendApply.addEventListener("click", () => sendChat(true).catch(showError));
  els.insertDraft.addEventListener("click", () => insertMarkdown(els.markdownDraft.value, false).catch(showError));
  els.replaceSelection.addEventListener("click", () => insertMarkdown(els.markdownDraft.value, true).catch(showError));
  els.provider.addEventListener("change", () => { els.model.value = DEFAULT_MODELS[els.provider.value]; saveSettings(); });
  els.model.addEventListener("input", saveSettings);
  els.prompt.addEventListener("keydown", (event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) sendChat(false).catch(showError); });
}
function loadSettings() {
  const provider = localStorage.getItem(STORAGE_KEYS.provider) || "openai";
  els.provider.value = provider; els.model.value = localStorage.getItem(STORAGE_KEYS.model) || DEFAULT_MODELS[provider]; els.providerApiKey.value = "";
}
function saveSettings() { localStorage.setItem(STORAGE_KEYS.provider, els.provider.value); localStorage.setItem(STORAGE_KEYS.model, els.model.value.trim()); }
async function refreshSelection() {
  const selected = await getSelectionText();
  els.selectionSummary.textContent = selected ? `Selected: ${selected.slice(0, 90)}${selected.length > 90 ? "…" : ""}` : "No Word selection";
  return selected;
}
async function sendChat(applyImmediately) {
  const prompt = els.prompt.value.trim(), apiKey = els.providerApiKey.value.trim();
  if (!prompt) throw new Error("Write a message first.");
  if (!apiKey) { els.settings.hidden = false; throw new Error("Enter your provider API key in Settings."); }
  setBusy(true, "Asking the AI with Word formatting guidance…");
  addMessage("user", prompt); els.prompt.value = "";
  const selectedText = await refreshSelection();
  const userContext = selectedText ? `${prompt}\n\nCurrent Word selection:\n${selectedText}` : `${prompt}\n\nThere is no selected Word text.`;
  history.push({ role: "user", content: userContext });
  const raw = await callProvider(els.provider.value, apiKey, els.model.value.trim(), history);
  const result = parseAction(raw);
  history.push({ role: "assistant", content: raw });
  const visible = result.reply || (result.markdown ? "I prepared formatted Word content. Review it below or apply it to the document." : raw);
  addMessage("assistant", visible);
  if (result.markdown) els.markdownDraft.value = result.markdown;
  if (applyImmediately && result.markdown) await insertMarkdown(result.markdown, result.action === "replace_selection");
  setBusy(false, applyImmediately && result.markdown ? "Applied to Word." : "Response ready.");
}
function parseAction(raw) {
  try {
    const match = raw.trim().match(/\{[\s\S]*\}/), value = JSON.parse(match ? match[0] : raw);
    return { action: ["insert_markdown", "replace_selection", "reply"].includes(value.action) ? value.action : "reply", markdown: typeof value.markdown === "string" ? value.markdown : "", reply: typeof value.reply === "string" ? value.reply : "" };
  } catch { return { action: "reply", markdown: "", reply: raw }; }
}
async function insertMarkdown(markdown, replaceSelection) {
  if (!markdown.trim()) throw new Error("There is no generated Markdown to insert.");
  setBusy(true, "Building native Word content locally…");
  const source = { openai: "chatgpt", anthropic: "claude", gemini: "gemini" }[els.provider.value] || "llm";
  const coreAvailable = await coreReady;
  const bytes = coreAvailable
    ? wasm_bindgen.convert_docx(markdown, source)
    : Md2Docx.convert(markdown, { font: "Arial", baseFont: "Arial" });
  const base64 = Md2Docx.toBase64(bytes);
  await Word.run(async (context) => {
    const selection = context.document.getSelection();
    selection.insertFileFromBase64(base64, replaceSelection ? Word.InsertLocation.replace : Word.InsertLocation.after);
    await context.sync();
  });
  setBusy(false, replaceSelection ? "Selection replaced with formatted content." : "Formatted content inserted.");
}
async function callProvider(provider, apiKey, model, messages) {
  if (provider === "openai") {
    const response = await fetch("https://api.openai.com/v1/responses", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` }, body: JSON.stringify({ model, instructions: FORMAT_SYSTEM_PROMPT, input: messages.map((item) => ({ role: item.role, content: item.content })) }) });
    const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload?.error?.message || "OpenAI request failed.");
    return payload.output_text || (payload.output || []).flatMap((item) => item.content || []).filter((item) => item.type === "output_text").map((item) => item.text).join("\n");
  }
  if (provider === "anthropic") {
    const response = await fetch("https://api.anthropic.com/v1/messages", { method: "POST", headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" }, body: JSON.stringify({ model, max_tokens: 2400, system: FORMAT_SYSTEM_PROMPT, messages }) });
    const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload?.error?.message || "Anthropic request failed.");
    return (payload.content || []).filter((item) => item.type === "text").map((item) => item.text).join("\n");
  }
  if (provider === "gemini") {
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
    const contents = messages.map((item) => ({ role: item.role === "assistant" ? "model" : "user", parts: [{ text: item.content }] }));
    const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ system_instruction: { parts: [{ text: FORMAT_SYSTEM_PROMPT }] }, contents, generationConfig: { temperature: 0.2 } }) });
    const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload?.error?.message || "Gemini request failed.");
    return (payload?.candidates?.[0]?.content?.parts || []).map((item) => item.text || "").join("\n");
  }
  throw new Error(`Unsupported provider: ${provider}`);
}
async function getSelectionText() { return Word.run(async (context) => { const selection = context.document.getSelection(); selection.load("text"); await context.sync(); return selection.text || ""; }); }
function addMessage(role, text) { const article = document.createElement("article"); article.className = `message ${role}`; const label = document.createElement("strong"), content = document.createElement("p"); label.textContent = role === "user" ? "You" : "Assistant"; content.textContent = text; article.append(label, content); els.chat.appendChild(article); els.chat.scrollTop = els.chat.scrollHeight; }
function setBusy(busy, message) { for (const id of ["send", "sendApply", "refreshSelection", "insertDraft", "replaceSelection"]) els[id].disabled = busy; els.status.textContent = message; els.status.className = busy ? "status busy" : "status"; }
function showError(error) { setBusy(false, error.message || String(error)); els.status.className = "status error"; }
