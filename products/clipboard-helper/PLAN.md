# Clipboard and Word Integration

The Windows clipboard helper is local-only. It reads clipboard Markdown,
converts it with the same native Rust core used as WebAssembly by Chrome and
the Word add-in, asks Microsoft Word to materialize native rich clipboard
formats, and leaves the result ready for `Ctrl+V`. Installation fails clearly
if the release does not include the native compiler; there is no second
converter implementation.

## One-command installation

Requirements: Windows, Microsoft Word desktop, Python 3.12 or newer, and internet access during installation for Python packages.

From an extracted release folder, run:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer copies the native core and clipboard runtime to `%LOCALAPPDATA%\Programs\md2docx`, creates a small private Python environment for Windows/Word automation, verifies it, and creates a Start Menu shortcut with the global `Ctrl+Alt+M` hotkey. It is safe to rerun for repair or upgrade. Shortcut-launched errors appear in a Windows dialog.

Usage: copy Markdown, press `Ctrl+Alt+M`, then paste into Word. Choose another hotkey with `-Hotkey "CTRL+ALT+W"`.

Uninstall with:

```powershell
PowerShell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\md2docx\install.ps1" -Uninstall
```

The helper and installer do not use an API, Docker, an account, or a hosted service. Microsoft Word is required because it creates the native clipboard representation.
