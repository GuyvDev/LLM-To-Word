[CmdletBinding()]
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Cargo = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
$WasmBindgen = Join-Path $env:USERPROFILE ".cargo\bin\wasm-bindgen.exe"
if (-not (Test-Path -LiteralPath $Cargo)) { throw "Rust is required. Install rustup and the stable toolchain first." }

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE." }
}

if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $VsWhere)) {
        $VsRoot = & $VsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($VsRoot) {
            $DevCmd = Join-Path $VsRoot "Common7\Tools\VsDevCmd.bat"
            & cmd.exe /d /s /c ('"' + $DevCmd + '" -arch=x64 -host_arch=x64 >nul && set') |
                ForEach-Object {
                    if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2] }
                }
        }
    }
}

Push-Location $Root
try {
    if (-not $SkipTests) { & $Cargo test --workspace; Assert-LastExit "Cargo tests" }
    & $Cargo build --release --package md2docx-core --bin md2docx-core-cli
    Assert-LastExit "Native core build"
    & $Cargo build --release --package md2docx-core --lib --target wasm32-unknown-unknown
    Assert-LastExit "WebAssembly core build"
    if (-not (Test-Path -LiteralPath $WasmBindgen)) {
        & $Cargo install wasm-bindgen-cli --version 0.2.126 --locked
        Assert-LastExit "wasm-bindgen installation"
    }
    $WebOut = Join-Path $Root "products\chrome-extension\core"
    New-Item -ItemType Directory -Path $WebOut -Force | Out-Null
    & $WasmBindgen --target no-modules --out-dir $WebOut --out-name md2docx_core "target\wasm32-unknown-unknown\release\md2docx_core.wasm"
    Assert-LastExit "WebAssembly binding generation"

    $NativeOut = Join-Path $Root "dist\windows"
    New-Item -ItemType Directory -Path $NativeOut -Force | Out-Null
    $NativeCore = Join-Path $NativeOut "md2docx-core.exe"
    Copy-Item -LiteralPath "target\release\md2docx-core-cli.exe" -Destination $NativeCore -Force
    $SkillBin = Join-Path $Root "products\skill-one\skill-one\bin"
    New-Item -ItemType Directory -Path $SkillBin -Force | Out-Null
    Copy-Item -LiteralPath $NativeCore -Destination (Join-Path $SkillBin "md2docx-core.exe") -Force
    Write-Host "Built canonical core:"
    Write-Host "  products\chrome-extension\core\md2docx_core.js"
    Write-Host "  products\chrome-extension\core\md2docx_core_bg.wasm"
    Write-Host "  dist\windows\md2docx-core.exe"
    Write-Host "  products\skill-one\skill-one\bin\md2docx-core.exe"
} finally {
    Pop-Location
}
