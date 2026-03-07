# Windows 11 Deployment Guide

This guide is for local or server deployment on Windows 11 with Docker Desktop.

## Prerequisites

1. Windows 11 x64.
2. Docker Desktop (latest stable) with:
   - WSL2 backend enabled.
   - Docker Compose v2 enabled.
3. PowerShell 5.1+ (default on Windows 11) or PowerShell 7.
4. At least 8 GB RAM and 10 GB free disk space.

## 1. Prepare project

```powershell
git clone <repository-url>
cd statproject
```

Start Docker Desktop and wait until status is `Engine running`.

## 2. Deploy

Use PowerShell:

```powershell
.\deploy-win11.ps1
```

Or use CMD/batch wrapper:

```cmd
deploy-win11.bat
```

With full rebuild:

```powershell
.\deploy-win11.ps1 -NoCache
```

## 3. Verify service health

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`

## 4. Stop / restart

Stop:

```powershell
.\stop-win11.ps1
```

Stop and remove volumes:

```powershell
.\stop-win11.ps1 -RemoveVolumes
```

Restart (redeploy):

```powershell
.\restart-win11.ps1
```

## 5. Logs and status

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

## 6. Troubleshooting (Windows-specific)

### Script execution policy error

If PowerShell blocks scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or always run wrappers (`*.bat`) that pass `-ExecutionPolicy Bypass`.

### Docker daemon not running

Open Docker Desktop manually and retry after it reports `Engine running`.

### Ports 3000/8000 already used

Find process:

```powershell
netstat -ano | findstr :3000
netstat -ano | findstr :8000
```

Stop process:

```powershell
taskkill /PID <PID> /F
```

### WSL2/virtualization issues

- Ensure virtualization is enabled in BIOS.
- Enable Windows features `Virtual Machine Platform` and `Windows Subsystem for Linux`.
- Reboot and restart Docker Desktop.

## Notes

- Default compose file is `docker-compose.yml`.
- To use another compose file:

```powershell
.\deploy-win11.ps1 -ComposeFile docker-compose.optimized.yml
```
