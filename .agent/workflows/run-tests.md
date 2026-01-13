---
description: Как запустить все тесты проекта
---

# Тестирование

## Запуск всех backend тестов

// turbo

```bash
cd backend && python3 -m pytest tests/ -v
```

## Запуск конкретного теста

// turbo

```bash
cd backend && python3 -m pytest tests/test_full_flow.py -v
```

## Запуск с coverage

```bash
cd backend && python3 -m pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

## Frontend тесты (если есть)

```bash
cd frontend && npm test
```

## Что считается успехом

- Все тесты PASSED
- Warnings допустимы (кроме deprecation в нашем коде)
- 1 skipped тест — норма (E2E требует браузер)
