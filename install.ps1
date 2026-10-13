# Installs only the Skill Hub manager skill, not the shared library.
# Preview by default. Explicit -Apply creates junctions; existing entries are never overwritten.
param(
    [switch] $Apply,
    [ValidateSet('codex','claude','cursor','gemini','opencode')]
    [string[]] $Agents = @('codex','claude')
)
$ErrorActionPreference = 'Stop'
$manager = (Resolve-Path (Join-Path $PSScriptRoot 'skill-hub')).Path
$homes = @{
    codex = Join-Path $HOME '.agents\skills'
    claude = Join-Path $HOME '.claude\skills'
    cursor = Join-Path $HOME '.cursor\skills'
    gemini = Join-Path $HOME '.gemini\skills'
    opencode = Join-Path $HOME '.config\opencode\skills'
}
foreach ($agent in $Agents) {
    $dstRoot = $homes[$agent]
    $dst = Join-Path $dstRoot 'skill-hub'
    if (Test-Path -LiteralPath $dst) {
        Write-Host "SKIP ($agent): already exists: $dst"
        continue
    }
    if (-not $Apply) {
        Write-Host "PREVIEW ($agent): would link '$dst' -> '$manager'"
    } else {
        New-Item -ItemType Directory -Force -Path $dstRoot | Out-Null
        New-Item -ItemType Junction -Path $dst -Target $manager | Out-Null
        Write-Host "OK ($agent): $dst -> $manager"
    }
}
if (-not $Apply) { Write-Host 'Preview only. Add -Apply to install.' }
