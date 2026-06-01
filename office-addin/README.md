# Office Word Add-in (Windows / Microsoft 365)

This folder contains a Word task-pane add-in that lets users:

1. Chat with an LLM provider (`OpenAI`, `Claude`, or `Gemini`) using their own API key.
2. Produce markdown edits from prompts.
3. Convert markdown through `md2docx` and insert/replace content directly in Word.

This removes the clipboard roundtrip and does not require opening a second Word file.

## Files

- `manifest.xml`: Office add-in manifest (Word host, read/write document permission).
- `taskpane.html`, `taskpane.css`, `taskpane.js`: UI + provider calls + Word insertion logic.
- `assets/`: icons used by the manifest.

## Prerequisites

- Microsoft Word desktop (Microsoft 365).
- A hosted HTTPS URL for these static files.
- A reachable md2docx API (`/convert/base64` endpoint).
- A provider API key for at least one LLM provider.

## Local development

Serve this directory over HTTPS and update `manifest.xml` URLs if needed.
By default, the manifest expects:

- `https://localhost:3000/taskpane.html`
- `https://localhost:3000/assets/icon48.png`

## Sideload into Word

1. Open Word.
2. Insert -> Add-ins -> My Add-ins -> Upload My Add-in.
3. Select `office-addin/manifest.xml`.
4. Open the add-in and enter:
   - md2docx API base URL and optional md2docx API key
   - LLM provider and API key
   - instruction prompt

## Publish path (Office Store)

1. Host add-in assets on a stable HTTPS domain.
2. Replace localhost URLs in `manifest.xml` with production URLs.
3. Validate the manifest with the Microsoft add-in validator.
4. Submit to the Microsoft 365 admin center / AppSource pipeline.

## Security notes

- API keys are stored in browser local storage in the Word add-in context.
- For production, prefer an OAuth-backed broker service so provider keys are never stored client-side.
- Restrict CORS on the md2docx API to trusted domains before store release.
