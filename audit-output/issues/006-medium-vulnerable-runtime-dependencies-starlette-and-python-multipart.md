# [Severity: Medium] Vulnerable runtime dependencies detected by `pip-audit`

## Summary
Dependency audit reported known vulnerabilities in runtime-relevant packages, including `starlette` and `python-multipart`.

## Affected Area
- Component: Backend dependency stack
- Environment: API runtime
- URL/Endpoint: N/A

## Steps to Reproduce
1. Run `pip-audit` against the installed Python environment.
2. Review reported vulnerabilities and fix versions.

## Expected Behavior
Production dependency set should be free from known high/medium CVEs/GHSAs.

## Actual Behavior
Known advisories are present in installed packages.

## Evidence
- Command: `~/.local/bin/pip-audit --path /home/dev/.local/lib/python3.8/site-packages --progress-spinner=off`
- Findings:
  - `starlette 0.44.0` -> `GHSA-2c2j-9gv5-cj73` (fix `0.47.2`)
  - `starlette 0.44.0` -> `GHSA-7f5h-v6xp-fcq8` (fix `0.49.1`)
  - `python-multipart 0.0.20` -> `GHSA-wp53-j4wj-2cfg` (fix `0.0.22`)

## Security Impact
Potential exposure to known vulnerabilities depending on exploitability in current deployment.

## Suggested Fix
Pin and upgrade vulnerable packages (directly or via compatible `fastapi` version update), then re-run audit in CI.

## Acceptance Criteria
- [ ] `pip-audit` reports zero known vulnerabilities for production lock set.
- [ ] Dependency versions are pinned and reproducible.
- [ ] CI includes vulnerability scan gate before deployment.

## Labels
`bug` `medium` `security` `dependencies`
