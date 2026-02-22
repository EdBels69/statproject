---
description: Как запустить проект локально для разработки
---

# Запуск проекта

## Быстрый старт

### Backend (Terminal 1)

// turbo

```bash
cd backend
python3 -m uvicorn app.main:app --reload --port 8000
```

Проверить: <http://localhost:8000/docs>

### Frontend (Terminal 2)

// turbo

```bash
cd frontend
npm run dev
```

Проверить: <http://localhost:5173>

## Docker (альтернатива)

// turbo

```bash
docker-compose up -d
```

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>

## Остановка

```bash
# Docker
docker-compose down

# Локально — просто Ctrl+C в терминалах
```
