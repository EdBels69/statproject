# GLM Agent Server

Сервер агента для автоматизации разработки через n8n.

## Описание

`agent_server.py` - это FastAPI сервер, который работает как GLM агент для автоматизации проекта Stat Analyzer через n8n.

### Функциональность

- **POST /api/task** - принимает задачи от n8n и генерирует код через GLM API
- **POST /api/review** - endpoint для code review (для Gemini3 Pro агента)
- **GET /health** - health check endpoint
- Автоматическое создание файлов на диске по запросу GLM

## Установка и запуск

### 1. Настройка переменных окружения

Создайте или обновите файл `.env` в корне проекта:

```env
# GLM API (обязательно для работы)
GLM_API_KEY=your_glm_api_key_here
GLM_API_URL=https://openrouter.ai/api/v1/chat/completions
GLM_MODEL=xiaomi/mimo-v2-flash:free
```

### 2. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### 3. Запуск сервера

```bash
python backend/agent_server.py
```

Или напрямую:

```bash
cd backend
python agent_server.py
```

Сервер будет доступен по адресу: **http://localhost:8000**

## API

### POST /api/task

Принимает задачу от n8n и генерирует код через GLM API.

**Request:**

```json
{
  "task": "Создай новый компонент React для визуализации данных",
  "context": {
    "branch": "feature/new-component",
    "repository": "username/statproject",
    "files": [
      {
        "path": "frontend/src/app/components/DataViz.jsx",
        "action": "create"
      }
    ]
  }
}
```

**Response:**

```json
{
  "status": "success",
  "changes": [
    {
      "path": "frontend/src/app/components/DataViz.jsx",
      "content": "import React from 'react';\n...",
      "operation": "create"
    }
  ],
  "message": "Компонент создан успешно",
  "files_created": ["/workspaces/statproject/frontend/src/app/components/DataViz.jsx"]
}
```

### POST /api/review

Endpoint для code review (для Gemini3 Pro агента).

**Request:**

```json
{
  "task": "Review pull request #42",
  "context": {
    "pr_number": 42,
    "title": "Add new visualization component",
    "repository": "username/statproject"
  }
}
```

**Response:**

```json
{
  "status": "approved",
  "comments": [],
  "summary": "Review выполнен GLM агентом"
}
```

## Формат ответа GLM

GLM должен возвращать файлы в следующем формате:

```
FILE: путь/к/файлу.py
```
содержимое файла
```

FILE: путь/к/другому/файлу.jsx
```
содержимое файла
```

Краткое описание выполненных действий.
```
