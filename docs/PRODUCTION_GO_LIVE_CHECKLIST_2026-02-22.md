# StatProject Production Go-Live Checklist (2026-02-22)

Контекст: `/Users/eduardbelskih/Проекты Github/statproject_desktop_test`

## 1. Перед релизом (обязательно)

1. Выполнить preflight:

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject_desktop_test
./deploy_preflight.sh
```

2. Для полного регресса (дольше, но надежнее):

```bash
./deploy_preflight.sh full
```

3. Убедиться, что все шаги завершились с `PASS`.

## 2. Запуск прод-стека

1. Сборка и подъем сервисов:

```bash
docker compose up -d --build
```

Если порты заняты:

```bash
BACKEND_PORT=8200 FRONTEND_PORT=3200 docker compose up -d --build
```

2. Проверка здоровья backend:

```bash
curl http://localhost:8100/health
```

Если запускали с override `BACKEND_PORT=8200`, проверка:

```bash
curl http://localhost:8200/health
```

Ожидаемо: JSON со `status=healthy`.

3. Проверка UI:

- Открыть `http://localhost:3100`
- или `http://localhost:3200` (если запускали с override портов)
- Загрузить тестовый dataset
- Открыть Design Review
- Подтвердить дизайн
- Запустить анализ
- Проверить экспорт отчета

## 3. Stop / Rollback

Остановить сервисы:

```bash
docker compose down
```

Если после обновления есть проблема:

1. Вернуть предыдущий стабильный коммит (git checkout на known-good tag/commit).
2. Пересобрать:

```bash
docker compose up -d --build
```

## 4. Текущие не-блокирующие предупреждения

- Pydantic v2 deprecation warning (внешняя зависимость/миграционный техдолг).
- SciPy/Pingouin runtime warnings на синтетических edge-case данных в тестах.
- Vite предупреждает о большом `vendor-aggrid` chunk; приложение рабочее, но есть потенциал доп. code-splitting.
- В Docker-сборке frontend `npm install` сообщает о 5 уязвимостях зависимостей; нужен отдельный patch-cycle зависимостей.

Эти пункты не блокируют релиз, но должны быть в post-release backlog.
