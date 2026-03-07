Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [switch]$NoCache,
    [int]$HealthTimeoutSec = 180,
    [string]$ComposeFile = "docker-compose.yml"
)

$deployScript = Join-Path $PSScriptRoot "deploy-win11.ps1"
if (-not (Test-Path $deployScript)) {
    throw "Cannot find deploy script: $deployScript"
}

$args = @{
    ComposeFile = $ComposeFile
    HealthTimeoutSec = $HealthTimeoutSec
}
if ($NoCache) {
    $args["NoCache"] = $true
}

& $deployScript @args
