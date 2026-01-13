---
description: Как деплоить проект в production
---

# Деплой

## Перед деплоем

// turbo

```bash
cd backend && python3 -m pytest tests/ -v
```

Убедиться что все тесты проходят.

## Docker деплой

// turbo

```bash
docker-compose build --no-cache
docker-compose up -d
```

## Проверка

// turbo

```bash
curl http://localhost:8000/health
curl http://localhost:3000
```

## Логи

```bash
docker-compose logs -f
```

## Остановка

```bash
docker-compose down
```

## Откат

```bash
git checkout HEAD~1
docker-compose build
docker-compose up -d
```
