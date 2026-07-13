# Clipboard and Word Integration Plan

The local `md2docx_clip.py` helper converts clipboard Markdown to a DOCX and uses Word COM for the final paste. It remains a Windows-only optional convenience tool.

For a managed or self-hosted alternative, use the public `POST /convert/base64` endpoint from the Word add-in. It returns a DOCX payload suitable for `insertFileFromBase64`.

## Operational guidance

- Keep conversion stateless: do not persist request bodies or generated files.
- Apply request-size, concurrency, and reverse-proxy rate limits to public deployments.
- Sign desktop releases and document the Windows/Word prerequisites.
- Prefer the Word add-in for in-document editing; no account or payment system is required.
