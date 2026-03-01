# [Severity: High] Chrome extension uses localhost API and lacks matching host permission

## Summary
The extension popup/background are configured to call `http://localhost:8000`, while `manifest.json` host permissions do not include localhost (or the documented production API host). This makes conversion/quota calls unreliable or non-functional outside local dev.

## Affected Area
- Component: Browser extension (popup + service worker)
- Environment: Staging/production extension installation
- URL/Endpoint: Extension API calls to `${API_BASE}/quota` and `${API_BASE}/convert`

## Steps to Reproduce
1. Load unpacked extension from `extension/`.
2. Open popup and attempt conversion without a local API server at `localhost:8000`.
3. Observe quota fetch/convert failures.

## Expected Behavior
Extension should call the deployed API host and have explicit host permissions for that host.

## Actual Behavior
Extension uses localhost API values and manifest host permissions do not align with the API origin.

## Evidence
- [extension/popup.js](/home/dev/dev-vm/Projects/tools-word/extension/popup.js:10): `API_BASE = "http://localhost:8000"`.
- [extension/background.js](/home/dev/dev-vm/Projects/tools-word/extension/background.js:14): `API_BASE = "http://localhost:8000"`.
- [extension/manifest.json](/home/dev/dev-vm/Projects/tools-word/extension/manifest.json:14) host permissions include only:
  - `https://github.com/*`
  - `https://hackmd.io/*`
  - `https://md2docx.app/*`

## Security Impact
N/A

## Suggested Fix
Centralize API base configuration for extension build profiles and align `host_permissions` with the actual API origin(s) used in production/dev.

## Acceptance Criteria
- [ ] Extension uses production API host in release build.
- [ ] Dev build uses localhost only when explicitly selected.
- [ ] `host_permissions` include all intended API origins.
- [ ] Quota + convert succeed in extension E2E smoke test.

## Labels
`bug` `high` `extension`
