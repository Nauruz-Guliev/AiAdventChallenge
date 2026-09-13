# День 7: сохранение контекста

Самостоятельное продолжение `day6`. Агент сохраняет несколько независимых чатов в JSON и восстанавливает их после перезапуска backend.

`day6` не изменяется.

## Что изучаем

В `day6` каждый запрос был одноходовым:

```text
React → FastAPI → Agent → DeepSeek API → React
```

В `day7` Agent сначала загружает историю выбранного чата, отправляет её вместе с новым вопросом, а после успешного ответа сохраняет новый exchange:

```text
React
  → FastAPI
  → Agent
  → ChatRepository: загрузить историю
  → LLMGateway: отправить историю и новый вопрос
  → ChatRepository: сохранить user + assistant
  → React
```

История хранится в `backend/data/chats.json`. Файл создаётся автоматически при создании первого чата и не добавляется в Git.

## Структура

- `backend/app/domain` — модели сообщений, чатов и ошибки;
- `backend/app/application/agent.py` — Agent, который собирает контекст;
- `backend/app/application/ports/chat_repository.py` — контракт хранилища;
- `backend/app/infrastructure/json_chat_repository.py` — JSON persistence;
- `backend/app/infrastructure/deepseek_gateway.py` — адаптер DeepSeek API;
- `backend/app/presentation` — FastAPI endpoints и dependency injection;
- `frontend` — React-интерфейс со списком чатов и историей сообщений.

`system prompt` не сохраняется. Agent добавляет его при каждом вызове. В JSON сохраняются только `user` и `assistant` messages.

## Запуск backend

```bash
cd day7/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Создай `day7/backend/.env` и укажи ключ DeepSeek:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CONTEXT_FILE=data/chats.json
```

Запусти FastAPI из `day7/backend`:

```bash
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## Запуск frontend

В отдельном терминале:

```bash
cd day7/frontend
npm install
npm run dev
```

Открой `http://127.0.0.1:5173`.

Vite проксирует `/api` на FastAPI. API-ключ остаётся только в backend.

## API

Создать чат:

```http
POST /api/chats
```

Получить список чатов:

```http
GET /api/chats
```

Получить историю чата:

```http
GET /api/chats/{chat_id}
```

Отправить сообщение:

```http
POST /api/chats/{chat_id}/messages
Content-Type: application/json

{"message":"Как меня зовут?"}
```

Удалить чат вместе с историей:

```http
DELETE /api/chats/{chat_id}
```

После удаления выбранного чата интерфейс автоматически переключается на другой сохранённый чат. Если чатов больше нет, создаётся новый пустой чат.

Заголовок чата формируется из первого сообщения: берётся первое законченное предложение или начало текста по границе слов, максимум с коротким многоточием. Поэтому заголовок не обрывается посередине слова.

Ответ:

```json
{
  "chat_id": "uuid",
  "answer": "Тебя зовут Анна.",
  "model": "deepseek-chat",
  "duration_ms": 1200,
  "stages": [
    {"name": "UI", "status": "completed"},
    {"name": "Agent", "status": "completed"},
    {"name": "DeepSeek API", "status": "completed"}
  ]
}
```

История сохраняется только после успешного ответа LLM. Поэтому ошибка provider не оставляет незавершённое сообщение пользователя.

## Проверка persistence

1. Открой web-интерфейс.
2. Нажми `Новый чат`.
3. Отправь: `Меня зовут Анна`.
4. Убедись, что появился ответ и в `backend/data/chats.json` записались два сообщения.
5. Останови backend.
6. Запусти backend снова с тем же `CONTEXT_FILE`.
7. Обнови страницу и выбери сохранённый чат.
8. Отправь: `Как меня зовут?`.
9. Убедись, что агент использует контекст и отвечает про Анну.

## Тесты

Backend-тесты не используют реальный DeepSeek API:

```bash
cd day7/backend
. .venv/bin/activate
pytest -q
```

Frontend production build:

```bash
cd day7/frontend
npm run build
```

Проверка изоляции:

```bash
git diff --exit-code -- day6
git check-ignore -v day7/backend/.env day7/backend/data/chats.json
```

## Ошибки

- неизвестный `chat_id` возвращает `404`;
- пустое или слишком длинное сообщение возвращает `422`;
- неверный API-ключ возвращает безопасную ошибку `502`;
- rate limit возвращает `429`;
- timeout возвращает `504`;
- ошибка чтения или записи JSON возвращает безопасную ошибку `500`.
