# Clipboard Service Deployment Plan

Goal: replace local clipboard automation (`md2docx_clip.py` + COM copy) with a managed service users can consume from Word, browser extensions, or desktop helpers.

## Current state

- Local tool converts markdown -> `.docx` and uses Word COM to copy rich content into clipboard.
- This is fast for one machine but hard to distribute, monitor, and secure for end users.

## Service architecture (implemented foundation)

- Conversion API already exists: `POST /convert`.
- New endpoint now available: `POST /convert/base64`.
  - Returns `docx_base64` for direct insertion in Word (`insertFileFromBase64`).
  - Uses the same quota and API-key logic as `/convert`.

## Productization path

1. **Word add-in first (preferred UX)**
- Use the Office add-in in `office-addin/`.
- Users edit in-place in Word; no clipboard tricks, no second document.

2. **Desktop helper for non-add-in users**
- Small signed installer (Windows) with tray app + hotkey.
- App calls `/convert/base64`, then uses Word COM only for final paste if needed.
- Keep COM usage client-side; conversion remains in cloud service.

3. **Extension integration**
- Browser extension sends markdown to `/convert/base64`.
- Offer "Copy rich text for Word" by converting base64 -> temp file -> clipboard copy helper.

## Operational requirements

- Add rate limits beyond monthly quota (burst + abuse controls).
- Restrict CORS to approved domains before broad rollout.
- Add per-client telemetry: request id, user id/key tier, latency, error type.
- Add key management portal (issue/revoke keys, tier upgrades).

## Security model

- Never expose provider secrets in static clients for production.
- Use server-side token exchange or OAuth broker for LLM providers.
- Keep conversion keys scoped and revocable.
- Add signed client releases for desktop helper updates.

## Rollout phases

1. Alpha: internal users via sideloaded Word add-in.
2. Beta: invited users with API keys and quotas.
3. GA: Office Store listing + hosted docs + automated billing upgrade flow.

## Success metrics

- Time to first successful insert in Word.
- Conversion success rate and P95 latency.
- Number of users who no longer rely on clipboard COM workflow.
- Support ticket rate for installation and auth issues.
