# Day 2: Response Format Control

This project sends the same user prompt to the same LLM model twice and compares the result:

1. **Without constraints**: the model receives only the user prompt.
2. **With constraints**: the model receives explicit format and length instructions, plus the API parameters `max_tokens` and `stop`.

Both requests use the powerful DeepSeek API model `deepseek-v4-pro`.

## Controlled request

The controlled request asks the model to:

- Return exactly three numbered items.
- Use one sentence per item.
- Keep every item within 18 words.
- Stop at the `[[DONE]]` sequence.

The API request also sets `max_tokens: 2000` and `stop: ["[[DONE]]"]`. DeepSeek reasoning can use part of the technical token budget before producing visible text, so `2000` avoids an empty visible response while the explicit 18-word-per-item rule controls the user-facing answer.

Both calls use the same model and `temperature: 0.2`; the controlled call is the only one that adds response-format instructions, `max_tokens`, and `stop`. DeepSeek API usage may be billed according to the account plan.

## Run locally

```bash
npm install
cp .env.example .env
```

Add your DeepSeek API key to `.env`, then start the app:

```bash
npm start
```

Open `http://localhost:3002`.

The API key is used only by the backend. `.env` is ignored by Git; `.env.example` is the safe template to commit.
