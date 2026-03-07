Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [switch]$RemoveVolumes,
    [string]$ComposeFile = "docker-compose.yml"
)

$script:ComposeExe = ""
$script:ComposeSub = $null

function Resolve-ComposeCommand {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI not found. Install Docker Desktop for Windows 11."
    }

    & docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is not running. Start Docker Desktop and retry."
    }

    try {
        & docker compose version *> $null
        if ($LASTEXITCODE -eq 0) {
            $script:ComposeExe = "docker"
            $script:ComposeSub = "compose"
            return
        }
    } catch {
    }

    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $script:ComposeExe = "docker-compose"
        $script:ComposeSub = $null
        return
    }

    throw "Docker Compose command not found. Use Docker Desktop with Compose v2."
}

function Invoke-Compose {
    param([string[]]$Args)
    if ($script:ComposeSub) {
        & $script:ComposeExe $script:ComposeSub @Args
    } else {
        & $script:ComposeExe @Args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Compose command failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $repoRoot
try {
    Resolve-ComposeCommand
    if (-not (Test-Path $ComposeFile)) {
        throw "Compose file not found: $ComposeFile"
    }

    $args = @("-f", $ComposeFile, "down")
    if ($RemoveVolumes) {
        $args += "-v"
    }

    Invoke-Compose $args
    Write-Host "Services are stopped."
} finally {
    Pop-Location
}
