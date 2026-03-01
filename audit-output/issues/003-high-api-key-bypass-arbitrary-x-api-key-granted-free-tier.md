# [Severity: High] Arbitrary `X-Api-Key` is treated as valid free account (quota bypass)

## Summary
Any non-`anonymous` API key that is not found in the backend is automatically assigned `free` tier. Attackers can rotate random keys to repeatedly obtain fresh monthly quota without registration or payment.

## Affected Area
- Component: Backend quota/auth logic
- Environment: API runtime
- URL/Endpoint: `GET /quota`, `POST /convert`

## Steps to Reproduce
1. Send `GET /quota` with random `X-Api-Key` values.
2. Observe each unknown key receives `tier: "free"` with `limit: 25`.
3. Repeat with new random keys to get fresh quota pools.

## Expected Behavior
Unknown API keys should be rejected (401/403) or treated as `anonymous` limit only.

## Actual Behavior
Unknown keys are treated as `free`, enabling quota circumvention via key rotation.

## Evidence
- Code: [api/quota.py](/home/dev/dev-vm/Projects/tools-word/api/quota.py:145) returns `"free"` for unknown keys at line 158.
- Runtime test (local `TestClient`):
  - `random-0-* -> {'used': 0, 'limit': 25, 'remaining': 25, 'tier': 'free'}`
  - `random-1-* -> {'used': 0, 'limit': 25, 'remaining': 25, 'tier': 'free'}`
  - `random-2-* -> {'used': 0, 'limit': 25, 'remaining': 25, 'tier': 'free'}`

## Security Impact
Business logic abuse / authorization bypass of paid API key controls and quota policy.

## Suggested Fix
Require unknown keys to fail authorization (401/403), or degrade to anonymous limits without separate identity pools.

## Acceptance Criteria
- [ ] Unknown `X-Api-Key` does not receive free tier.
- [ ] Unknown keys return 401/403 (or anonymous-tier enforcement with shared identity model).
- [ ] Regression tests cover random key rotation abuse.

## Labels
`bug` `high` `security` `backend`
