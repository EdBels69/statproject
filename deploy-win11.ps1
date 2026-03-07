Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [switch]$NoCache,
    [int]$HealthTimeoutSec = 180,
    [string]$ComposeFile = "docker-compose.yml"
)

$script:ComposeExe = ""
$script:ComposeSub = $null
$script:ComposeDisplay = ""

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
            $script:ComposeDisplay = "docker compose"
            return
        }
    } catch {
    }

    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $script:ComposeExe = "docker-compose"
        $script:ComposeSub = $null
        $script:ComposeDisplay = "docker-compose"
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
        throw "$($script:ComposeDisplay) $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Invoke-ComposeAllowFailure {
    param([string[]]$Args)
    try {
        if ($script:ComposeSub) {
            & $script:ComposeExe $script:ComposeSub @Args
        } else {
            & $script:ComposeExe @Args
        }
    } catch {
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSec,
        [string]$Name
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Host "[OK] $Name is reachable: $Url"
                return $true
            }
        } catch {
        }

        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    return $false
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $repoRoot
try {
    Resolve-ComposeCommand
    if (-not (Test-Path $ComposeFile)) {
        throw "Compose file not found: $ComposeFile"
    }

    Write-Host "[1/4] Stopping existing containers..."
    Invoke-ComposeAllowFailure @("-f", $ComposeFile, "down")

    Write-Host "[2/4] Building images..."
    $buildArgs = @("-f", $ComposeFile, "build")
    if ($NoCache) {
        $buildArgs += "--no-cache"
    }
    Invoke-Compose $buildArgs

    Write-Host "[3/4] Starting services..."
    Invoke-Compose @("-f", $ComposeFile, "up", "-d")

    Write-Host "[4/4] Waiting for health checks..."
    if (-not (Wait-HttpReady -Url "http://localhost:8000/health" -TimeoutSec $HealthTimeoutSec -Name "Backend")) {
        throw "Backend health check timed out. See logs: $($script:ComposeDisplay) logs -f backend"
    }

    if (-not (Wait-HttpReady -Url "http://localhost:3000" -TimeoutSec 60 -Name "Frontend")) {
        Write-Warning "Frontend is not reachable yet. It may still be starting."
    }

    Write-Host ""
    Write-Host "Deployment completed."
    Write-Host "Frontend:    http://localhost:3000"
    Write-Host "Backend API: http://localhost:8000"
    Write-Host "API docs:    http://localhost:8000/docs"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  $($script:ComposeDisplay) -f $ComposeFile ps"
    Write-Host "  $($script:ComposeDisplay) -f $ComposeFile logs -f backend"
    Write-Host "  $($script:ComposeDisplay) -f $ComposeFile logs -f frontend"
} finally {
    Pop-Location
}
