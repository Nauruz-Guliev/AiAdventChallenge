require('dotenv').config();
const crypto = require('crypto');
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '32kb' }));
app.use(express.static(path.join(__dirname, 'public')));

const MAX_PROMPT_LENGTH = 8000;
const TASK = `Реши задачу портфельного выбора для совета директоров. Доступно 12 инженерных недель, можно выбрать не более 3 проектов, и среди выбранных должен быть минимум один проект с меткой SAFETY.

Проекты:
- Альфа: 6 недель, ценность 16, требует Бету.
- Бета: 4 недели, ценность 10, SAFETY.
- Гамма: 5 недель, ценность 14, несовместима с Дельтой.
- Дельта: 3 недели, ценность 8, SAFETY.
- Эпсилон: 2 недели, ценность 5, требует Альфу.
- Зета: 4 недели, ценность 11, без зависимостей.

Выбери допустимый набор с максимальной суммой ценности. Ответь ровно в 4 нумерованных секциях Markdown: 1) выбор и общие суммы; 2) проверка бюджета, лимита и зависимостей; 3) почему следующий вариант хуже; 4) один практический риск. Не добавляй вступление, не меняй исходные числа и не показывай скрытые рассуждения.`;

const MODELS = [
  {
    id: 'deepseek-v4-flash',
    tier: 'weak',
    label: 'Слабая',
    description: 'Flash-модель с малой активной частью',
    inputPrice: 0.22,
    outputPrice: 0.66,
    hfModel: 'deepseek-ai/DeepSeek-V4-Flash',
    sourceLabel: 'Карточка Hugging Face',
    sourceUrl: 'https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash',
  },
  {
    id: 'glm-5.3-flash',
    tier: 'medium',
    label: 'Средняя',
    description: 'Flash-модель с сильным instruction-following',
    inputPrice: 0.07,
    outputPrice: 0.25,
    hfModel: 'zai-org/GLM-5.3-Flash',
    sourceLabel: 'Карточка Hugging Face',
    sourceUrl: 'https://huggingface.co/zai-org/GLM-5.3-Flash',
  },
  {
    id: 'kimi-k3',
    tier: 'strong',
    label: 'Сильная',
    description: 'Дорогой верхний уровень каталога',
    inputPrice: 3,
    outputPrice: 15,
    hfModel: 'moonshotai/Kimi-K3',
    sourceLabel: 'Карточка Hugging Face',
    sourceUrl: 'https://huggingface.co/moonshotai/Kimi-K3',
  },
];

const modelById = new Map(MODELS.map(model => [model.id, model]));
const openaiOptions = {
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://opencode.ai/zen/go/v1',
  timeout: 180000,
  maxRetries: 0,
};
const jobs = new Map();

function createClient(sessionId) {
  return new OpenAI({
    ...openaiOptions,
    defaultHeaders: {
      'x-opencode-session': sessionId,
      'User-Agent': 'ai-advent-challenge-day5/1.0',
    },
  });
}

function getUsage(completion) {
  const usage = completion.usage || {};
  return {
    promptTokens: usage.prompt_tokens ?? null,
    completionTokens: usage.completion_tokens ?? null,
    totalTokens: usage.total_tokens ?? null,
  };
}

function estimateCost(usage, model) {
  if (usage.promptTokens == null || usage.completionTokens == null) return null;
  return Number(((usage.promptTokens / 1000000) * model.inputPrice
    + (usage.completionTokens / 1000000) * model.outputPrice).toFixed(6));
}

function evaluate(text) {
  const normalized = text.toLocaleLowerCase('ru-RU');
  const sections = normalized.match(/(?:^|\n)\s*(?:#{1,3}\s*)?\d+[.)]\s+.+/g) || [];
  const chosenPortfolio = /альф[аы][\s,и+/-]+бет[ау][\s,и+/-]+эпсилон/iu.test(normalized)
    || /альф[аы].*бет[ау].*эпсилон/isu.test(normalized);
  const hasBudget = /12\s*(?:недель|недел|week)/iu.test(normalized);
  const hasValue = /31/iu.test(normalized);
  const checksDependencies = /зависим|требу|несовмест|лимит|safety/iu.test(normalized);
  const requiredSignals = [sections.length >= 4, chosenPortfolio, hasBudget, hasValue, checksDependencies];
  return {
    rubricScore: Math.round((requiredSignals.filter(Boolean).length / requiredSignals.length) * 100),
    signals: {
      fourSections: sections.length >= 4,
      optimalPortfolio: chosenPortfolio,
      budgetMentioned: hasBudget,
      optimalValueMentioned: hasValue,
      constraintsChecked: checksDependencies,
    },
  };
}

async function complete(model, prompt, sessionId) {
  const startedAt = Date.now();
  const completion = await createClient(sessionId).chat.completions.create({
    model: model.id,
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.2,
    max_tokens: 1800,
  });
  const usage = getUsage(completion);
  return {
    text: (completion.choices?.[0]?.message?.content || '').trim(),
    usage,
    estimatedCostUsd: estimateCost(usage, model),
    finishReason: completion.choices?.[0]?.finish_reason || 'unknown',
    latencyMs: Date.now() - startedAt,
  };
}

function startJob(model, prompt) {
  const id = crypto.randomUUID();
  const sessionId = crypto.randomUUID();
  const job = { id, state: 'running', startedAt: Date.now(), result: null, error: null };
  jobs.set(id, job);
  complete(model, prompt, sessionId).then(result => {
    job.state = 'complete';
    job.result = { ...result, model: model.id, evaluation: evaluate(result.text) };
  }).catch(error => {
    job.state = 'error';
    job.error = error.message;
  });
  return id;
}

app.get('/api/config', (req, res) => {
  res.json({
    task: TASK,
    models: MODELS,
    pricingNote: 'Стоимость — расчёт по reference-тарифам моделей, не отдельное списание OpenCode Go.',
  });
});

app.post('/api/run-model', (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : '';
  const model = modelById.get(req.body?.model);
  if (!model) return res.status(400).json({ error: 'Неизвестная модель.' });
  if (!prompt || prompt.length > MAX_PROMPT_LENGTH) return res.status(400).json({ error: 'Некорректное условие задачи.' });
  return res.status(202).json({ runId: startJob(model, prompt) });
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

const port = Number(process.env.PORT || 3005);
app.listen(port, () => console.log(`Day 5 server listening on http://localhost:${port}`));
