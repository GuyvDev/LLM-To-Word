# Clipboard helper

Verified Windows clipboard replacement product. `install.ps1`
places the helper and native shared compiler in the user's local application
directory, installs its local dependency, and creates the `Ctrl+Alt+M`
shortcut.

## Features

- Uses the canonical native Rust compiler; there is no separate Python
  Markdown renderer.
- Reads Markdown from the clipboard or an optional UTF-8 file.
- Uses Microsoft Word to materialize Word-native clipboard formats.
- Preserves an existing Word process and closes only the temporary document.
- Installs into `%LOCALAPPDATA%`, creates a private Python environment, and
  registers a configurable Start Menu hotkey.
- Supports safe rerun for repair/upgrade and guarded uninstall.
- Requires no API, account, Docker runtime, or hosted service.

## Install from source

```powershell
.\scripts\build_converter_core.ps1
PowerShell -ExecutionPolicy Bypass -File .\products\clipboard-helper\install.ps1
```

Release users should use `clipboard-helper-windows-x64.zip`, which already
contains the native compiler. See [PLAN.md](PLAN.md) for the architecture and
complete usage instructions.

## Status and remaining publication work

- [x] Native compiler integration.
- [x] One-command install, repair, hotkey, visible errors, and uninstall logic.
- [x] Installer creates its target directory before copying release files.
- [x] Shared Markdown, DOCX, RTL, BiDi, math, and table tests.
- [x] Hands-on installation, shortcut, conversion, and Word paste use.
- [ ] Sign the native executable and release archive.
