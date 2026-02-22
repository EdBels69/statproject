# Release Readiness (2026-02-22)

Контекст: `/Users/eduardbelskih/Проекты Github/statproject_desktop_test`

## Go/No-Go

Статус: **GO (staging/production candidate)**

## Проверки, выполненные перед релизом

1. Backend full regression:

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject_desktop_test/backend
python3 -m pytest -q
```

Результат: `238 passed, 6 skipped`.

2. Frontend quality gates:

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject_desktop_test/frontend
npm run test:run
npm run lint
npm run build
```

Результат: `29 passed`, lint pass, build pass.

3. Unified preflight:

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject_desktop_test
./deploy_preflight.sh
```

Результат: `PASS`.

4. Docker deployment smoke:

```bash
BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build
curl http://localhost:8200/health
curl -I http://localhost:3200
```

Результат:
- backend healthy (`status=healthy`),
- frontend отвечает `HTTP/1.1 200 OK`.

## Технические правки, закрывающие прод-риски

1. FastAPI startup deprecation устранен через `lifespan`.
2. `update_cell` в dataset modify стал dtype-safe (включая overflow integer dtype).
3. Docker compose порты параметризованы (`BACKEND_PORT` / `FRONTEND_PORT`) для бесконфликтного запуска.
4. Frontend Docker build upgraded to `node:20-alpine` (совместимо с Vite 7).
5. Добавлен автоматический preflight script + go-live checklist.

## Остаточные риски (не блокируют запуск)

1. Pydantic v2 deprecation warning (миграционный техдолг).
2. Крупный frontend chunk `vendor-aggrid` (>500kB) — влияет на perf, не на корректность.
3. `npm audit` в Docker build сообщает о 5 уязвимостях зависимостей — нужен отдельный dependency hardening cycle.

## Рекомендация по запуску

- Если порты свободны: стандартный запуск по `docker compose up -d --build`.
- Если порты заняты: `BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build`.
- После запуска: пройти smoke из чеклиста `docs/PRODUCTION_GO_LIVE_CHECKLIST_2026-02-22.md`.
