# [Severity: Medium] Anonymous quota can be bypassed by spoofing `X-Forwarded-For`

## Summary
The API trusts client-supplied `X-Forwarded-For` unconditionally when deriving identity for anonymous usage. Direct clients can spoof IPs to reset quota buckets.

## Affected Area
- Component: Backend identity/quota extraction
- Environment: API runtime (especially when directly internet-exposed)
- URL/Endpoint: `GET /quota`, `POST /convert`

## Steps to Reproduce
1. Send 6 conversion requests with header `X-Forwarded-For: 1.2.3.4`.
2. Confirm quota reaches 429 after limit.
3. Send another request with `X-Forwarded-For: 5.6.7.8`.
4. Observe quota resets and request succeeds.

## Expected Behavior
Only trusted proxy headers should be honored; direct clients should not control effective identity.

## Actual Behavior
Any client can set `X-Forwarded-For` and obtain a new anonymous quota pool.

## Evidence
- Code: [api/main.py](/home/dev/dev-vm/Projects/tools-word/api/main.py:147) returns first `x-forwarded-for` value without trust checks.
- Runtime test:
  - IP A hit limit and received 429.
  - IP B header immediately received `200` with remaining quota.

## Security Impact
Rate-limit and abuse-control bypass for anonymous tier.

## Suggested Fix
Trust `X-Forwarded-For` only from known reverse proxies/load balancers; otherwise use `request.client.host`. Optionally sign/verify proxy headers.

## Acceptance Criteria
- [ ] Direct client-supplied `X-Forwarded-For` cannot alter identity in untrusted contexts.
- [ ] Proxy-trust configuration is explicit and environment-driven.
- [ ] Tests cover spoof attempts and expected quota behavior.

## Labels
`bug` `medium` `security` `backend`
