# Word AI chat add-in

## Status

Beta and not end-to-end tested. The task pane, provider adapters, local
conversion path, JavaScript syntax, and manifest XML parse checks are
implemented. It has not yet passed a hosted deployment test, live provider
tests, Microsoft Word desktop/online tests, or Microsoft's add-in validator.

The task-pane add-in is a Word-oriented AI chat. It reads the current selection on request, injects a strict formatting contract into every AI conversation, and asks the model for a structured insert/replace/reply action. Markdown is converted locally to a DOCX package and inserted through `insertFileFromBase64`; document content is never sent to an md2docx conversion service.

This is prompt conditioning and deterministic rendering, not model fine-tuning. The model learns the required output contract within each conversation, while the local renderer—not the model—owns Word styles, RTL/BiDi properties, lists, tables, and OMML math.

## AI credentials

- User-supplied OpenAI, Anthropic, or Gemini keys are held only in the task-pane session.
- Selected Word text and chat messages go directly to the chosen provider.
- Browser-side provider keys are appropriate only for personal testing. Production deployments should replace direct provider calls with an organization-controlled credential broker.

## Deployment

1. Host `products/word-addin/` at the HTTPS paths referenced in `manifest.xml`.
2. Host `products/chrome-extension/md2docx.js` and `products/chrome-extension/core/` at the matching public `/extension/` paths on the same origin. The WebAssembly core is the primary converter and the JavaScript file is an offline compatibility fallback; neither is an API.
3. Validate `manifest.xml` with Microsoft’s add-in validator.
4. Sideload the manifest and run the Word visual checks from `AGENTS.md`.

No Docker container or md2docx API is required by the add-in.

## Implemented features

- OpenAI, Anthropic, and Gemini chat adapters.
- API keys kept in task-pane memory for the current session only.
- Word selection reading, conversation history, and generated Markdown review.
- Structured reply, insert, and replace-selection actions.
- Bundled WebAssembly conversion with a local JavaScript fallback.
- Native insertion with Office.js `insertFileFromBase64`.
- Formatting guidance for headings, lists, tables, code, RTL text, and math.

## Remaining release gates

- [ ] Replace the example `https://md2docx.app` origin with a controlled HTTPS
  deployment and verify every manifest path.
- [ ] Add an organization-controlled credential broker; direct browser API
  keys are for personal testing only.
- [ ] Test OpenAI, Anthropic, and Gemini success and error paths.
- [ ] Test selection read, insert, and replace in Word desktop and Word Online.
- [ ] Run Microsoft's manifest/add-in validation and accessibility review.
- [ ] Complete a Word visual acceptance matrix for RTL, BiDi, equations, lists,
  code, blockquotes, and tables.
