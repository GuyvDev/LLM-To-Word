[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ReleaseDir = if ($OutputDir) {
    [IO.Path]::GetFullPath($OutputDir)
} else {
    Join-Path $Root "dist\releases"
}
$DistRoot = [IO.Path]::GetFullPath((Join-Path $Root "dist"))
if (-not $ReleaseDir.StartsWith($DistRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Release output must stay inside $DistRoot"
}

function Copy-RequiredFile([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required release input is missing: $Source"
    }
    $parent = Split-Path $Destination -Parent
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Copy-RequiredDirectory([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Required release directory is missing: $Source"
    }
    New-Item -ItemType Directory -Path (Split-Path $Destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Compress-StagingDirectory([string]$Stage, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force }
    Add-Type -AssemblyName System.IO.Compression
    $stream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew)
    $archive = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        $fixedTimestamp = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
        foreach ($file in (Get-ChildItem -LiteralPath $Stage -Recurse -File | Sort-Object FullName)) {
            $relative = $file.FullName.Substring($Stage.Length).TrimStart('\', '/').Replace('\', '/')
            $entry = $archive.CreateEntry($relative, [IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = $fixedTimestamp
            $input = $file.OpenRead()
            $output = $entry.Open()
            try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
        }
    } finally {
        $archive.Dispose()
        $stream.Dispose()
    }
}

Push-Location $Root
try {
    if (-not $SkipBuild) {
        & (Join-Path $PSScriptRoot "build_converter_core.ps1")
        if ($LASTEXITCODE -ne 0) { throw "Canonical compiler build failed with exit code $LASTEXITCODE" }
    }

    $NativeCore = Join-Path $Root "dist\windows\md2docx-core.exe"
    $WasmCore = Join-Path $Root "products\chrome-extension\core\md2docx_core_bg.wasm"
    if (-not (Test-Path -LiteralPath $NativeCore -PathType Leaf)) { throw "Native compiler is missing: $NativeCore" }
    if (-not (Test-Path -LiteralPath $WasmCore -PathType Leaf)) { throw "WebAssembly compiler is missing: $WasmCore" }

    if (Test-Path -LiteralPath $ReleaseDir) { Remove-Item -LiteralPath $ReleaseDir -Recurse -Force }
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    $StageRoot = Join-Path $ReleaseDir ".staging"
    New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null

    $ChromeSource = Join-Path $Root "products\chrome-extension"
    $ChromeStage = Join-Path $StageRoot "chrome-extension"
    New-Item -ItemType Directory -Path $ChromeStage -Force | Out-Null
    foreach ($name in @("manifest.json", "background.js", "popup.html", "popup.js", "md2docx.js", "THIRD_PARTY_NOTICES.md")) {
        Copy-RequiredFile (Join-Path $ChromeSource $name) (Join-Path $ChromeStage $name)
    }
    foreach ($name in @("content", "core", "icons")) {
        Copy-RequiredDirectory (Join-Path $ChromeSource $name) (Join-Path $ChromeStage $name)
    }
    Compress-StagingDirectory $ChromeStage (Join-Path $ReleaseDir "chrome-extension.zip")

    $ClipboardSource = Join-Path $Root "products\clipboard-helper"
    $ClipboardStage = Join-Path $StageRoot "clipboard-helper"
    New-Item -ItemType Directory -Path $ClipboardStage -Force | Out-Null
    foreach ($name in @("install.ps1", "md2docx_clip.py", "requirements.txt", "README.md", "PLAN.md")) {
        Copy-RequiredFile (Join-Path $ClipboardSource $name) (Join-Path $ClipboardStage $name)
    }
    Copy-RequiredFile $NativeCore (Join-Path $ClipboardStage "md2docx-core.exe")
    Copy-RequiredFile (Join-Path $Root "LICENSE") (Join-Path $ClipboardStage "LICENSE")
    Copy-RequiredFile (Join-Path $Root "THIRD_PARTY_NOTICES.md") (Join-Path $ClipboardStage "THIRD_PARTY_NOTICES.md")
    Compress-StagingDirectory $ClipboardStage (Join-Path $ReleaseDir "clipboard-helper-windows-x64.zip")

    $Python = if (Test-Path -LiteralPath (Join-Path $Root ".venv-win\Scripts\python.exe")) {
        Join-Path $Root ".venv-win\Scripts\python.exe"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        (Get-Command python).Source
    } else {
        throw "Python 3 is required to package Skill One"
    }
    & $Python (Join-Path $Root "products\skill-one\package_skill.py") --output (Join-Path $ReleaseDir "skill-one.zip")
    if ($LASTEXITCODE -ne 0) { throw "Skill One packaging failed with exit code $LASTEXITCODE" }

    $AddinSource = Join-Path $Root "products\word-addin"
    $AddinStage = Join-Path $StageRoot "word-addin-host"
    foreach ($name in @("taskpane.html", "taskpane.css", "taskpane.js")) {
        Copy-RequiredFile (Join-Path $AddinSource $name) (Join-Path $AddinStage "addin\$name")
    }
    Copy-RequiredDirectory (Join-Path $AddinSource "assets") (Join-Path $AddinStage "addin\assets")
    Copy-RequiredFile (Join-Path $AddinSource "manifest.xml") (Join-Path $AddinStage "manifest.xml")
    Copy-RequiredFile (Join-Path $AddinSource "README.md") (Join-Path $AddinStage "README.md")
    Copy-RequiredFile (Join-Path $ChromeSource "md2docx.js") (Join-Path $AddinStage "extension\md2docx.js")
    Copy-RequiredDirectory (Join-Path $ChromeSource "core") (Join-Path $AddinStage "extension\core")
    Compress-StagingDirectory $AddinStage (Join-Path $ReleaseDir "word-addin-host.zip")

    Remove-Item -LiteralPath $StageRoot -Recurse -Force
    $Archives = Get-ChildItem -LiteralPath $ReleaseDir -Filter "*.zip" -File | Sort-Object Name
    $Checksums = foreach ($archive in $Archives) {
        $hash = (Get-FileHash -LiteralPath $archive.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $($archive.Name)"
    }
    Set-Content -LiteralPath (Join-Path $ReleaseDir "SHA256SUMS.txt") -Value $Checksums -Encoding ASCII
    $Archives | ForEach-Object { Write-Host ("Created {0}" -f $_.FullName) }
    Write-Host ("Created {0}" -f (Join-Path $ReleaseDir "SHA256SUMS.txt"))
} finally {
    Pop-Location
}
