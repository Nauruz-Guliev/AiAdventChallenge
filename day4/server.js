require('dotenv').config();
const crypto = require('crypto');
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '32kb' }));
app.use(express.static(path.join(__dirname, 'public')));

const MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-chat';
const MAX_PROMPT_LENGTH = 8000;
const TASK = `Придумай 5 названий для мобильного приложения, которое помогает людям не забывать поливать комнатные растения.

Для каждого варианта дай:
1. Название из 1–3 слов.
2. Слоган не длиннее 8 слов.
3. Объяснение идеи не длиннее 20 слов.

Оформи ответ ровно пятью пронумерованными пунктами. Названия должны быть разными и запоминающимися. Не используй слово «зелёный» и его формы. Не повторяй одно и то же название или слоган.`;

const TEMPERATURES = [
  { id: 'cold', value: 0, label: 'Стабильный', note: 'Точность и повторяемость' },
  { id: 'balanced', value: 0.7, label: 'Сбалансированный', note: 'Баланс контроля и идей' },
  { id: 'hot', value: 1.2, label: 'Экспериментальный', note: 'Больше риска и неожиданности' },
];

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://api.deepseek.com/v1',
  timeout: 180000,
  maxRetries: 0,
});
const jobs = new Map();

function getText(completion) {
  return (completion.choices?.[0]?.message?.content || '').trim();
}

function getUsage(completion) {
  const usage = completion.usage || {};
  return {
    promptTokens: usage.prompt_tokens ?? null,
    completionTokens: usage.completion_tokens ?? null,
    totalTokens: usage.total_tokens ?? null,
  };
}

function evaluate(text) {
  const normalized = text.toLocaleLowerCase('ru-RU');
  const numbered = text.match(/(?:^|\n)\s*\d+[.)]\s+.+/g) || [];
  const forbiddenWord = /зелен/iu.test(normalized);
  const items = numbered.map(line => line.replace(/^\s*\d+[.)]\s*/u, '').trim().toLocaleLowerCase('ru-RU'));
  const uniqueLines = new Set(items);
  const words = normalized.match(/[а-яёa-z]{4,}/giu) || [];
  const uniqueWords = new Set(words);
  const itemWordSets = items.map(item => new Set(item.match(/[а-яёa-z]{4,}/giu) || []));
  let overlap = 0;
  let pairs = 0;
  itemWordSets.forEach((left, leftIndex) => itemWordSets.slice(leftIndex + 1).forEach(right => {
    const intersection = [...left].filter(word => right.has(word)).length;
    const union = new Set([...left, ...right]).size;
    overlap += union ? intersection / union : 0;
    pairs += 1;
  }));
  const formatScore = (numbered.length === 5 ? 55 : Math.min(55, numbered.length * 11))
    + (!forbiddenWord ? 25 : 0)
    + (uniqueLines.size === numbered.length ? 20 : Math.max(0, uniqueLines.size * 4));
  const lexicalVariety = words.length ? Math.round((uniqueWords.size / words.length) * 100) : 0;
  const diversityScore = pairs ? Math.round((1 - overlap / pairs) * 100) : 0;
  return {
    accuracy: Math.min(100, formatScore),
    creativity: Math.min(100, Math.round(lexicalVariety * 1.5)),
    diversity: diversityScore,
    signals: {
      numberedItems: numbered.length,
      forbiddenWord,
      uniqueItems: uniqueLines.size,
    },
  };
}

async function complete(prompt, temperature) {
  const startedAt = Date.now();
  const completion = await openai.chat.completions.create({
    model: MODEL,
    messages: [{ role: 'user', content: prompt }],
    temperature,
    max_tokens: 1800,
  });
  return {
    text: getText(completion),
    usage: getUsage(completion),
    finishReason: completion.choices?.[0]?.finish_reason || 'unknown',
    latencyMs: Date.now() - startedAt,
  };
}

function findTemperature(value) {
  return TEMPERATURES.find(item => item.value === Number(value));
}

function startJob(prompt, temperature) {
  const id = crypto.randomUUID();
  const job = { id, state: 'running', startedAt: Date.now(), result: null, error: null };
  jobs.set(id, job);
  complete(prompt, temperature).then(result => {
    job.state = 'complete';
    job.result = { ...result, temperature, evaluation: evaluate(result.text) };
  }).catch(error => {
    job.state = 'error';
    job.error = error.message;
  });
  return id;
}

app.get('/api/config', (req, res) => {
  res.json({ model: MODEL, task: TASK, temperatures: TEMPERATURES });
});

app.post('/api/run-temperature', (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : '';
  const temperature = findTemperature(req.body?.temperature);
  if (!temperature) return res.status(400).json({ error: 'Неизвестная температура.' });
  if (!prompt || prompt.length > MAX_PROMPT_LENGTH) return res.status(400).json({ error: 'Некорректное условие задачи.' });
  return res.status(202).json({ runId: startJob(prompt, temperature.value) });
});

app.get('/api/run/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'Запуск не найден.' });
  return res.json({
    state: job.state,
    elapsedMs: Date.now() - job.startedAt,
    result: job.result,
    error: job.error,
  });
});

const port = Number(process.env.PORT || 3004);
app.listen(port, () => console.log(`Day 4 server listening on http://localhost:${port}`));
