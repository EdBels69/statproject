# Desktop Test Setup (macOS)

This folder is a separate test fork of StatProject for desktop mode.

## What changed in this fork

- Ports are isolated from the original web instance:
  - Frontend: `http://localhost:3100`
  - Backend: `http://localhost:8100`
- Added Electron launcher in `desktop/`
- Added one-click script: `start-desktop-test.command`
- Docker backend is configured to use container workspace path (`/app/workspace`), so host absolute paths from local `.env` do not break startup.

## First run

1. Open Docker Desktop and wait until it is fully started.
2. Run:

```bash
cd "/Users/eduardbelskih/Проекты Github/statproject_desktop_test"
./start-desktop-test.command
```

This command will:
- install Electron deps (first run only),
- run `docker compose up -d`,
- open desktop window with StatProject UI.

## Stop services

```bash
cd "/Users/eduardbelskih/Проекты Github/statproject_desktop_test"
docker compose down
```

## Troubleshooting

- First Docker build can take 10-20+ minutes depending on network (large scientific Python wheels).
- If Docker is not running, launcher will stop with a clear message.
- If `3100` or `8100` is busy, free these ports or change them in `docker-compose.yml`.

## Notes

- This is a **test desktop wrapper** around the same local web stack.
- Data and behavior remain equivalent to the browser version.
