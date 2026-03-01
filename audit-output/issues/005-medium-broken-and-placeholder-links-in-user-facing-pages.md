# [Severity: Medium] User-facing links point to placeholders/broken destinations

## Summary
Multiple public links are still placeholder values (`your-org`, `your-link`) and fail destination integrity checks. This breaks expected navigation and upgrade/reporting flows.

## Affected Area
- Component: Frontend landing page + extension popup
- Environment: Web/extension UI
- URL/Endpoint: External anchors in HTML/JS

## Steps to Reproduce
1. Open the landing page.
2. Click "GitHub" or "Upgrade to Pro".
3. Observe invalid destination behavior.

## Expected Behavior
All navigation links should resolve to active, correct destinations.

## Actual Behavior
Placeholder links are shipped and fail integrity checks.

## Evidence
- [web/index.html](/home/dev/dev-vm/Projects/tools-word/web/index.html:18): `https://github.com/your-org/md2docx`
- [web/index.html](/home/dev/dev-vm/Projects/tools-word/web/index.html:125): `https://buy.stripe.com/your-link`
- [web/index.html](/home/dev/dev-vm/Projects/tools-word/web/index.html:150): same GitHub placeholder
- [web/app.js](/home/dev/dev-vm/Projects/tools-word/web/app.js:151): same Stripe placeholder in upgrade banner
- Runtime link check:
  - `https://github.com/your-org/md2docx` -> `404`
  - `https://buy.stripe.com/your-link` -> `403`

## Security Impact
N/A

## Suggested Fix
Replace placeholders with real production URLs and add CI link-checking for all public HTML/JS assets.

## Acceptance Criteria
- [ ] GitHub and Stripe links resolve to valid destinations.
- [ ] Link checker passes with no 4xx/5xx for required outbound URLs.
- [ ] No `your-org` / `your-link` placeholders remain in production assets.

## Labels
`bug` `medium` `frontend`
