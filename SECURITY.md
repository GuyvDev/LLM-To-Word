# Security policy

## Supported versions

Until the first signed public release, security fixes are applied to the latest
commit on `main`. Older source snapshots and unsigned development archives are
not supported release channels.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for this repository when available.
Do not open a public issue for a suspected vulnerability, exposed credential,
or private document.

Include:

- The affected product and version or commit.
- Reproduction steps and the expected security boundary.
- Impact and any known prerequisites.
- A minimal sanitized proof of concept.

Never include real API keys, credentials, private documents, desktop captures,
or unrelated personal data. The maintainer will acknowledge the report,
investigate it, and coordinate disclosure and remediation through the private
report.

## Product boundaries

- Chrome extension, clipboard helper, and Skill One conversion is local.
- The Word add-in sends content only to the provider selected by the user. Its
  direct browser-key mode is for personal testing, not managed deployment.
- Download release packages from this repository's GitHub Releases and verify
  them with `SHA256SUMS.txt`. Native Windows packages remain unsigned until the
  signing release gate is complete.
