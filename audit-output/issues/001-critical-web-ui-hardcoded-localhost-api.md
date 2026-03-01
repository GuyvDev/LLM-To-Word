# [Severity: Critical] Web UI hardcoded to localhost API breaks production conversion flow

## Summary
The web frontend is hardcoded to call `http://localhost:8000` for `/quota` and `/convert`. In production browsers this points to each end user's local machine, so core conversion and quota flows fail unless users are also running a local API server.

## Affected Area
- Component: Frontend web client
- Environment: Production/staging browser runtime
- URL/Endpoint: `web/app.js` calls to `${API_BASE}/quota` and `${API_BASE}/convert`

## Steps to Reproduce
1. Deploy `web/` as a static frontend (or open [index.html](/home/dev/dev-vm/Projects/tools-word/web/index.html)).
2. Ensure no API is running on the user's local `http://localhost:8000`.
3. Click "Download .docx" after entering markdown.

## Expected Behavior
The frontend should call the deployed API host and complete conversion.

## Actual Behavior
Frontend calls `http://localhost:8000`, producing connection errors and failed conversion/quota loading.

## Evidence
- Code: [web/app.js](/home/dev/dev-vm/Projects/tools-word/web/app.js:11) sets `const API_BASE = "http://localhost:8000"`.
- Runtime probe:
  - `http://localhost:8000` returned connection refused in link check.
  - External configured prod API host in comments (`https://api.md2docx.app`) is not used.

## Security Impact
N/A

## Suggested Fix
Use environment-based API base URL (build-time or runtime config), defaulting to production API in production builds.

## Acceptance Criteria
- [ ] `API_BASE` is environment-configured, not hardcoded to localhost in shipped frontend bundle.
- [ ] `/quota` and `/convert` succeed in deployed staging/prod without local API processes.
- [ ] CI check fails if `localhost` API base is present in production artifacts.

## Labels
`bug` `critical` `frontend`
