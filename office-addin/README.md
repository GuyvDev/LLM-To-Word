# Word AI chat add-in (beta)

The task-pane add-in is a Word-oriented AI chat. It reads the current selection on request, injects a strict formatting contract into every AI conversation, and asks the model for a structured insert/replace/reply action. Markdown is converted locally to a DOCX package and inserted through `insertFileFromBase64`; document content is never sent to an md2docx conversion service.

This is prompt conditioning and deterministic rendering, not model fine-tuning. The model learns the required output contract within each conversation, while the local renderer—not the model—owns Word styles, RTL/BiDi properties, lists, tables, and OMML math.

## AI credentials

- User-supplied OpenAI, Anthropic, or Gemini keys are held only in the task-pane session.
- Selected Word text and chat messages go directly to the chosen provider.
- Browser-side provider keys are appropriate only for personal testing. Production deployments should replace direct provider calls with an organization-controlled credential broker.

## Deployment

1. Host `office-addin/` at the HTTPS paths referenced in `manifest.xml`.
2. Host `extension/md2docx.js` at `/extension/md2docx.js` on the same origin. This is a static local-conversion asset, not an API.
3. Validate `manifest.xml` with Microsoft’s add-in validator.
4. Sideload the manifest and run the Word visual checks from `AGENTS.md`.

No Docker container or md2docx API is required by the add-in.
