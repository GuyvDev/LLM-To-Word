[CmdletBinding()]
param(
    [string]$Hotkey = "CTRL+ALT+M",
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\md2docx",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProductName = "md2docx Clipboard"
$ShortcutPath = Join-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" "$ProductName.lnk"

if ($Uninstall) {
    if (Test-Path -LiteralPath $ShortcutPath) { Remove-Item -LiteralPath $ShortcutPath -Force }
    if (Test-Path -LiteralPath $InstallDir) {
        $resolved = [IO.Path]::GetFullPath($InstallDir)
        $allowedRoot = [IO.Path]::GetFullPath("$env:LOCALAPPDATA\Programs")
        if (-not $resolved.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a directory outside $allowedRoot"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    Write-Host "$ProductName removed."
    exit 0
}

if ([Environment]::OSVersion.Platform -ne "Win32NT") { throw "This installer supports Windows only." }
$SourceDir = $PSScriptRoot
$RequiredFiles = @("md2docx.py", "md2docx_clip.py", "requirements.txt", "clipboard-requirements.txt")
foreach ($name in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourceDir $name))) {
        throw "Missing $name. Run install.ps1 from the extracted md2docx release folder."
    }
}

$word = Get-Command "WINWORD.EXE" -ErrorAction SilentlyContinue
if (-not $word) {
    $wordPath = Get-ItemPropertyValue -LiteralPath "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe" -Name "(default)" -ErrorAction SilentlyContinue
    if (-not $wordPath) { throw "Microsoft Word desktop is required but was not found." }
}

$PythonExe = $null
if (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
    $PythonExe = (& py.exe -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
}
if (-not $PythonExe -and (Get-Command "python.exe" -ErrorAction SilentlyContinue)) {
    $PythonExe = (& python.exe -c "import sys; print(sys.executable)" | Select-Object -Last 1)
}
if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) { throw "Python 3.12 or newer is required." }
$VersionOk = & $PythonExe -c "import sys; print(int(sys.version_info >= (3, 12)))"
if ($VersionOk -ne "1") { throw "Python 3.12 or newer is required. Found: $(& $PythonExe --version)" }

Write-Host "Installing $ProductName to $InstallDir"
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
foreach ($name in $RequiredFiles) {
    $source = [IO.Path]::GetFullPath((Join-Path $SourceDir $name))
    $destination = [IO.Path]::GetFullPath((Join-Path $InstallDir $name))
    if (-not $source.Equals($destination, [StringComparison]::OrdinalIgnoreCase)) {
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}
$InstalledScript = [IO.Path]::GetFullPath((Join-Path $InstallDir "install.ps1"))
if (-not ([IO.Path]::GetFullPath($PSCommandPath)).Equals($InstalledScript, [StringComparison]::OrdinalIgnoreCase)) {
    Copy-Item -LiteralPath $PSCommandPath -Destination $InstalledScript -Force
}

$VenvDir = Join-Path $InstallDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) { & $PythonExe -m venv $VenvDir }
& $VenvPython -m pip install --disable-pip-version-check --upgrade pip
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $InstallDir "clipboard-requirements.txt")
& $VenvPython -c "import docx, lxml, latex2mathml, win32clipboard, win32com.client; print('Runtime check passed.')"

$LauncherPath = Join-Path $InstallDir "md2docx_clip_silent.vbs"
$Pythonw = Join-Path $VenvDir "Scripts\pythonw.exe"
$Helper = Join-Path $InstallDir "md2docx_clip.py"
$Vbs = @"
Set shell = CreateObject("WScript.Shell")
shell.Run Chr(34) & "$Pythonw" & Chr(34) & " " & Chr(34) & "$Helper" & Chr(34), 0, False
"@
Set-Content -LiteralPath $LauncherPath -Value $Vbs -Encoding ASCII

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$env:WINDIR\System32\wscript.exe"
$Shortcut.Arguments = "`"$LauncherPath`""
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Hotkey = $Hotkey
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Convert clipboard Markdown to native Word clipboard content"
$Shortcut.Save()

Write-Host ""
Write-Host "Installation complete."
Write-Host "1. Copy Markdown."
Write-Host "2. Press $Hotkey."
Write-Host "3. Paste into Word with Ctrl+V."
Write-Host ""
Write-Host "Uninstall: PowerShell -ExecutionPolicy Bypass -File `"$(Join-Path $InstallDir 'install.ps1')`" -Uninstall"
