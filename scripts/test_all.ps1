[CmdletBinding()]
param(
    [switch]$SkipPython,
    [switch]$IncludeDocker
)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE." }
}

Push-Location $Root
try {
    foreach ($PowerShellScript in @("scripts\build_converter_core.ps1", "scripts\build_linux_core.ps1", "scripts\test_skill_cross_platform.ps1", "scripts\package_release.ps1", "scripts\test_all.ps1", "products\clipboard-helper\install.ps1")) {
        $tokens = $null
        $parseErrors = $null
        [Management.Automation.Language.Parser]::ParseFile((Join-Path $Root $PowerShellScript), [ref]$tokens, [ref]$parseErrors) | Out-Null
        if ($parseErrors.Count) { throw "PowerShell syntax failed for $PowerShellScript`: $($parseErrors[0].Message)" }
    }

    & cargo fmt --all -- --check
    Assert-LastExit "Rust formatting"
    & cargo clippy --workspace --all-targets -- -D warnings
    Assert-LastExit "Rust lint"

    & (Join-Path $PSScriptRoot "build_converter_core.ps1")
    Assert-LastExit "Canonical core build and Rust tests"

    $NodeTests = Get-ChildItem -LiteralPath (Join-Path $Root "tests") -Filter "test_*.js" -File | Sort-Object Name | Select-Object -ExpandProperty FullName
    & node --test @NodeTests
    Assert-LastExit "Node/WASM/extension tests"

    foreach ($Script in @("products\chrome-extension\background.js", "products\chrome-extension\popup.js", "products\chrome-extension\md2docx.js", "products\chrome-extension\content\llm-capture.js", "products\word-addin\taskpane.js")) {
        & node --check (Join-Path $Root $Script)
        Assert-LastExit "JavaScript syntax: $Script"
    }

    if (-not $SkipPython) {
        $Python = if ($env:MD2DOCX_TEST_PYTHON) { $env:MD2DOCX_TEST_PYTHON }
            elseif (Test-Path -LiteralPath (Join-Path $Root ".venv-win\Scripts\python.exe")) { Join-Path $Root ".venv-win\Scripts\python.exe" }
            elseif (Test-Path -LiteralPath (Join-Path $Root ".venv\Scripts\python.exe")) { Join-Path $Root ".venv\Scripts\python.exe" }
            else { $null }
        if (-not $Python) { throw "Python test environment not found. Set MD2DOCX_TEST_PYTHON or create .venv-win; use -SkipPython only for converter-only work." }
        & $Python -m py_compile products/clipboard-helper/md2docx_clip.py products/skill-one/package_skill.py products/skill-one/skill-one/scripts/docx_brain.py products/skill-one/skill-one/scripts/visual_gate.py scripts/check_credentials.py scripts/check_repository.py scripts/generate_readme_examples.py scripts/validate_visual_regression.py
        Assert-LastExit "Python syntax checks"
        & $Python -m unittest discover -s tests -v
        Assert-LastExit "Python tests"
        & $Python scripts/check_credentials.py
        Assert-LastExit "Credential scan"
        & $Python scripts/check_repository.py
        Assert-LastExit "Repository publication audit"
    }

    if ($IncludeDocker) {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker was requested but is not installed." }
        & (Join-Path $PSScriptRoot "build_linux_core.ps1") -UpdateManifest
        Assert-LastExit "Pinned Linux core build"
        & docker build -f products/skill-one/Dockerfile.test -t skill-one:test .
        Assert-LastExit "Skill One Docker build"
        & docker run --rm skill-one:test
        Assert-LastExit "Skill One Docker smoke test"
        & (Join-Path $PSScriptRoot "test_skill_cross_platform.ps1") -Image skill-one:test
        Assert-LastExit "Skill One cross-platform parity"
        $VisualOutput = Join-Path ([IO.Path]::GetTempPath()) ("md2docx-visual-" + [Guid]::NewGuid().ToString("N"))
        try {
            New-Item -ItemType Directory -Path $VisualOutput -Force | Out-Null
            & docker build -f tests/visual/Dockerfile -t md2docx-visual:test .
            Assert-LastExit "Pinned visual-regression Docker build"
            & docker run --rm -v "${VisualOutput}:/visual-output" md2docx-visual:test --output /visual-output
            Assert-LastExit "Exact DOCX-to-PDF-to-PNG regression gate"
        } finally {
            if (Test-Path -LiteralPath $VisualOutput) {
                $ResolvedVisualOutput = [IO.Path]::GetFullPath($VisualOutput)
                $TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
                if (-not $ResolvedVisualOutput.StartsWith($TempRoot, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "Refusing to remove non-temporary path: $ResolvedVisualOutput"
                }
                Remove-Item -LiteralPath $ResolvedVisualOutput -Recurse -Force
            }
        }
    }

    Write-Host "All requested test suites passed."
} finally {
    Pop-Location
}
