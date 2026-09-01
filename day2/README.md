# Day 2: Response Format Control

This project sends the same user prompt to the same LLM model twice and compares the result:

1. **Without constraints**: the model receives only the user prompt.
2. **With constraints**: the model receives explicit format and length instructions, plus the API parameters `max_tokens` and `stop`.

## Controlled request

The controlled request asks the model to:

- Return exactly three numbered items.
- Use one sentence per item.
- Keep every item within 18 words.
- Stop at the `<END>` sequence.

The API request also sets `max_tokens: 600` and `stop: ["<END>"]`. OpenCode reasoning models can use part of the technical token budget before producing visible text, so `600` avoids an empty visible response while the explicit 18-word-per-item rule controls the user-facing answer.

## Run locally

```bash
npm install
cp .env.example .env
```

Add your OpenCode API key to `.env`, then start the app:

```bash
npm start
```

Open `http://localhost:3002`.

The API key is used only by the backend. `.env` is ignored by Git; `.env.example` is the safe template to commit.
