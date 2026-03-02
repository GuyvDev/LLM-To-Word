# install.ps1
# Installs md2docx + md2docx_clip so they can be run from anywhere.
#
# What this script does:
#   1. Clones (or updates) the repo to C:\opt\md2docx
#   2. Creates a Python venv at C:\opt\md2docx\.venv and installs dependencies
#   3. Creates C:\opt\bin\md2docx.cmd and C:\opt\bin\md2docx_clip.cmd wrappers
#   4. Adds C:\opt\bin to the user's PATH (if not already there)
#
# Usage (run once, or re-run to upgrade):
#   PowerShell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$REPO_URL    = "https://github.com/GuyvDev/LLM-To-Word.git"
$INSTALL_DIR = "C:\opt\md2docx"
$BIN_DIR     = "C:\opt\bin"

# ── 1. Clone or pull ──────────────────────────────────────────────────────────
if (Test-Path "$INSTALL_DIR\.git") {
    Write-Host "Updating existing repo at $INSTALL_DIR ..."
    git -C $INSTALL_DIR pull
} else {
    Write-Host "Cloning repo to $INSTALL_DIR ..."
    New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
    git clone $REPO_URL $INSTALL_DIR
}

# ── 2. Create / refresh venv and install deps ─────────────────────────────────
$venv = "$INSTALL_DIR\.venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment ..."
    python -m venv $venv
}

Write-Host "Installing / upgrading Python dependencies ..."
& "$venv\Scripts\pip.exe" install --upgrade pip --quiet
& "$venv\Scripts\pip.exe" install -r "$INSTALL_DIR\requirements.txt" --quiet
& "$venv\Scripts\pip.exe" install pywin32 --quiet   # needed for md2docx_clip
Write-Host "Dependencies installed."

# ── 3. Write cmd wrappers ─────────────────────────────────────────────────────
New-Item -ItemType Directory -Path $BIN_DIR -Force | Out-Null

$cmd = @"
@echo off
"$venv\Scripts\python.exe" "$INSTALL_DIR\md2docx.py" %*
"@
Set-Content -Path "$BIN_DIR\md2docx.cmd" -Value $cmd -Encoding ASCII
Write-Host "Wrapper created at $BIN_DIR\md2docx.cmd"

$cmdClip = @"
@echo off
"$venv\Scripts\python.exe" "$INSTALL_DIR\md2docx_clip.py" %*
"@
Set-Content -Path "$BIN_DIR\md2docx_clip.cmd" -Value $cmdClip -Encoding ASCII
Write-Host "Wrapper created at $BIN_DIR\md2docx_clip.cmd"

# ── 4. Add C:\opt\bin to user PATH (if missing) ───────────────────────────────
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$BIN_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$BIN_DIR", "User")
    Write-Host "Added $BIN_DIR to your user PATH."
    Write-Host "NOTE: Open a new terminal window for PATH to take effect."
} else {
    Write-Host "$BIN_DIR is already in PATH."
}

# ── 5. Register Ctrl+Alt+M Windows shortcut for md2docx_clip ──────────────────
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$startMenu\md2docx_clip.lnk")
$lnk.TargetPath  = "wscript.exe"
$lnk.Arguments   = """$INSTALL_DIR\md2docx_clip_silent.vbs"""
$lnk.Hotkey      = "CTRL+ALT+M"
$lnk.WindowStyle = 7
$lnk.Description = "Convert clipboard markdown to Word format"
$lnk.Save()
Write-Host "Ctrl+Alt+M hotkey registered (Start Menu shortcut)."

Write-Host ""
Write-Host "Done! Usage:"
Write-Host "  md2docx input.txt -o output.docx"
Write-Host "  md2docx_clip               (convert clipboard, paste result into Word)"
Write-Host ""
Write-Host "To update to the latest version later:"
Write-Host "  git -C $INSTALL_DIR pull"
