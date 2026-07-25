[CmdletBinding()]
param([switch]$SkipManifestCheck)

$ErrorActionPreference = "Stop"
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Output = Join-Path $Root "products\skill-one\skill-one\bin\md2docx-core-linux-x64"
$ManifestPath = Join-Path $Root "products\skill-one\skill-one\assets\runtime-manifest.json"
$Export = Join-Path ([IO.Path]::GetTempPath()) ("md2docx-linux-" + [Guid]::NewGuid().ToString("N"))
$BuildId = [Guid]::NewGuid().ToString("N")
$Image = "md2docx-linux-build:$BuildId"
$Container = "md2docx-linux-export-$BuildId"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to build the pinned Linux runtime."
}

try {
    New-Item -ItemType Directory -Path $Export -Force | Out-Null
    Push-Location $Root
    try {
        & docker build --file products/skill-one/Dockerfile.build-linux --tag $Image .
        if ($LASTEXITCODE -ne 0) { throw "Pinned Linux core build failed." }
        & docker create --name $Container --entrypoint /md2docx-core-linux-x64 $Image | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Pinned Linux export container creation failed." }
        & docker cp "${Container}:/md2docx-core-linux-x64" $Export
        if ($LASTEXITCODE -ne 0) { throw "Pinned Linux core export failed." }
    } finally {
        Pop-Location
    }
    Copy-Item -LiteralPath (Join-Path $Export "md2docx-core-linux-x64") -Destination $Output -Force
    $Actual = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $SkipManifestCheck) {
        $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
        $Expected = $Manifest.binaries.'bin/md2docx-core-linux-x64'
        if ($Actual -ne $Expected) {
            throw "Linux runtime hash differs from runtime-manifest.json. Expected=$Expected Actual=$Actual"
        }
    }
    Write-Host "Built pinned Linux core: $Actual"
} finally {
    & docker rm --force $Container 2>$null | Out-Null
    & docker image rm --force $Image 2>$null | Out-Null
    if (Test-Path -LiteralPath $Export) {
        $Resolved = [IO.Path]::GetFullPath($Export)
        $TempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $Resolved.StartsWith($TempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove non-temporary path: $Resolved"
        }
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}
