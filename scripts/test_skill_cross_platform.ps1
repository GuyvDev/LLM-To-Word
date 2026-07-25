[CmdletBinding()]
param([string]$Image = "skill-one:test")

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Python = if ($env:MD2DOCX_TEST_PYTHON) { $env:MD2DOCX_TEST_PYTHON }
    elseif (Test-Path -LiteralPath (Join-Path $Root ".venv-win\Scripts\python.exe")) { Join-Path $Root ".venv-win\Scripts\python.exe" }
    elseif (Test-Path -LiteralPath (Join-Path $Root ".venv\Scripts\python.exe")) { Join-Path $Root ".venv\Scripts\python.exe" }
    else { throw "Python test environment not found." }
$Work = Join-Path ([IO.Path]::GetTempPath()) ("md2docx-parity-" + [Guid]::NewGuid().ToString("N"))

try {
    New-Item -ItemType Directory -Path $Work -Force | Out-Null
    $Brain = Join-Path $Root "products\skill-one\skill-one\scripts\docx_brain.py"
    $Input = Join-Path $Root "products\skill-one\skill-one\assets\example.md"
    $WindowsOutput = Join-Path $Work "windows.docx"
    & $Python $Brain build $Input $WindowsOutput --source llm | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Windows parity build failed." }

    & docker run --rm --mount "type=bind,source=$Work,target=/out" $Image `
        python skill-one/scripts/docx_brain.py build `
        skill-one/assets/example.md /out/linux.docx --source llm | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Linux parity build failed." }

    $LinuxOutput = Join-Path $Work "linux.docx"
    $WindowsHash = (Get-FileHash -LiteralPath $WindowsOutput -Algorithm SHA256).Hash
    $LinuxHash = (Get-FileHash -LiteralPath $LinuxOutput -Algorithm SHA256).Hash
    if ($WindowsHash -ne $LinuxHash) {
        throw "Cross-platform DOCX mismatch. Windows=$WindowsHash Linux=$LinuxHash"
    }
    Write-Host "Cross-platform DOCX parity passed: $WindowsHash"
} finally {
    if (Test-Path -LiteralPath $Work) {
        $Resolved = [IO.Path]::GetFullPath($Work)
        $TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $Resolved.StartsWith($TempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove non-temporary path: $Resolved"
        }
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}
