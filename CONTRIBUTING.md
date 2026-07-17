# Contributing

Issues and pull requests are welcome. Keep changes dependency-light, preserve
the no-login/no-charge design, add tests for behavior changes, and run these
commands before submitting:

```powershell
.\scripts\test_all.ps1 -IncludeDocker
.\scripts\package_release.ps1
python scripts/check_credentials.py
```

Do not commit credentials, personal documents, generated DOCX/PDF files, debug
artifacts, or screen captures.
