# Contributing

Issues and pull requests are welcome. Keep changes dependency-light, preserve
the no-login/no-charge design, add tests for behavior changes, and run these
commands before submitting:

```powershell
.\scripts\test_all.ps1 -IncludeDocker
.\scripts\package_release.ps1
python scripts/check_credentials.py
python scripts/check_repository.py
```

Do not commit credentials, personal documents, generated DOCX/PDF files, debug
artifacts, or screen captures.

## Publishing a release

1. Update product versions and release notes.
2. Run the verification and packaging commands above.
3. Create and push an annotated version tag such as `v1.4.0`.
4. Wait for both CI jobs to pass.

For a `v*` tag, CI publishes the verified ZIPs and `SHA256SUMS.txt` directly to
that tag's GitHub Release. Rerunning the release job safely replaces the assets.
