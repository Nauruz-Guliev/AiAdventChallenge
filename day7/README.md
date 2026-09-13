# День 6: Первый LLM-агент

Учебный web-проект с отдельным Python-классом `Agent`. Пользователь вводит один запрос в React-интерфейсе, FastAPI передаёт его агенту, а агент обращается к DeepSeek через отдельный gateway.

## Что изучаем

Обычный вызов API выглядит так:

```text
route → DeepSeek API → response
```

В этом проекте вызов инкапсулирован в отдельной сущности:

```text
React → FastAPI route → Agent → LLMGateway → DeepSeek API → React
```

`Agent` не знает о HTTP, JSON или конкретном SDK. Он принимает пользовательский текст, формирует сообщения, вызывает контракт `LLMGateway` и возвращает `AgentResult`.

### Слои

- `domain` — модели результата, этапов и ошибки предметной области;
- `application/agent.py` — сценарий работы отдельного агента;
- `application/ports` — интерфейс `LLMGateway`;
- `infrastructure/deepseek_gateway.py` — адаптер DeepSeek API;
- `presentation` — FastAPI-схемы, dependency injection и route;
- `frontend` — React-чат и схема `UI → Agent → DeepSeek API`.

Главное преимущество такой границы: в тесте и в будущем можно заменить DeepSeek на `FakeLLMGateway` или другого провайдера, не переписывая Agent.

## Запуск backend

```bash
cd day6/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Открой `.env` и укажи собственный DeepSeek API key:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

Запусти FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

## Запуск frontend

В отдельном терминале:

```bash
cd day6/frontend
npm install
npm run dev
```

Открой адрес Vite, обычно `http://localhost:5173`.

Во время разработки Vite проксирует `/api` на FastAPI. API-ключ остаётся в backend и не попадает в браузер.

## API

Единственный endpoint принимает независимый одноходовый запрос:

```http
POST /api/chat
Content-Type: application/json

{"message":"Объясни, что такое API простыми словами"}
```

Ответ:

```json
{
  "answer": "API — это способ...",
  "model": "deepseek-chat",
  "duration_ms": 1840,
  "stages": [
    {"name": "UI", "status": "completed"},
    {"name": "Agent", "status": "completed"},
    {"name": "DeepSeek API", "status": "completed"}
  ]
}
```

Приложение не хранит историю, не использует streaming и не показывает скрытые рассуждения модели. Этапы на экране — безопасная учебная схема прохождения запроса.

## Тесты

Backend-тесты не требуют DeepSeek API key и не делают сетевых запросов:

```bash
cd day6/backend
. .venv/bin/activate
pytest -q
```

Frontend production build:

```bash
cd day6/frontend
npm run build
```

Unit-тесты используют `FakeGateway`, а API-тесты подменяют `Agent` через FastAPI dependency override. Поэтому отдельно проверяются Agent, адаптер провайдера и HTTP-слой.

## Обработка ошибок

- пустое или слишком длинное сообщение получает `422`;
- неверный ключ превращается в безопасное сообщение без деталей SDK;
- rate limit возвращает `429`;
- timeout возвращает `504`;
- ошибки провайдера возвращают безопасное сообщение и остаются в серверном логе.
