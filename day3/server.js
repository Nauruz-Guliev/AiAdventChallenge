require('dotenv').config();
const crypto = require('crypto');
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '32kb' }));
app.use(express.static(path.join(__dirname, 'public')));

const MODEL = 'deepseek-v4-pro';
const MAX_PROMPT_LENGTH = 8000;
const EXPECTED_ORDER = ['Дина', 'Вера', 'Егор', 'Борис', 'Алина', 'Глеб'];
const NAMES = ['Алина', 'Борис', 'Вера', 'Глеб', 'Дина', 'Егор'];

const TASK = `Логическая задача «Расписание презентаций».
Шесть человек — Алина, Борис, Вера, Глеб, Дина и Егор — выступают по одному разу с понедельника по субботу. Нужно определить порядок выступлений.

Условия:
1. Глеб выступает в субботу.
2. Борис выступает ровно за два места до Глеба.
3. Дина выступает непосредственно перед Верой.
4. Дина выступает раньше Егора.
5. Егор выступает раньше Алины.
6. Алина не выступает в понедельник и не выступает в субботу.

Определи единственный порядок от понедельника до субботы. Обоснуй решение. Последняя строка ответа должна иметь строго такой формат: «Итоговый порядок: Имя 1, Имя 2, Имя 3, Имя 4, Имя 5, Имя 6».`;

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://api.deepseek.com/v1',
  timeout: 120000,
  maxRetries: 0,
});

const CALL_TITLES = {
  direct: '01 · Прямой ответ',
  step: '02 · Пошаговый ответ',
  'prompt-builder': '03 · Конструктор промпта',
  generated: '04 · Решение по сгенерированному промпту',
  experts: '05 · Группа экспертов',
};

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
    reasoningTokens: usage.completion_tokens_details?.reasoning_tokens ?? null,
  };
}

function addUsage(first, second) {
  const sum = (left, right) => left == null || right == null ? null : left + right;
  return {
    promptTokens: sum(first.promptTokens, second.promptTokens),
    completionTokens: sum(first.completionTokens, second.completionTokens),
    totalTokens: sum(first.totalTokens, second.totalTokens),
    reasoningTokens: sum(first.reasoningTokens, second.reasoningTokens),
  };
}

function buildCallPreview(prompt, generatedPrompt = '') {
  const request = (messages, maxTokens) => ({ model: MODEL, messages, temperature: 0.2, max_tokens: maxTokens });
  return [
    { id: 'direct', title: CALL_TITLES.direct, request: request([{ role: 'user', content: prompt }], 5000) },
    { id: 'step', title: CALL_TITLES.step, request: request([{ role: 'user', content: `${prompt}\n\nРешай задачу пошагово: перечисли ограничения, проверь варианты и объясни вывод.` }], 5000) },
    { id: 'prompt-builder', title: CALL_TITLES['prompt-builder'], request: request([{ role: 'user', content: `Ты prompt-инженер. Составь подробный, но компактный промпт для другой модели, который поможет надёжно решить эту задачу. Промпт должен включать саму задачу, требование проверить все ограничения, не выдумывать условия и завершать ответ строкой в формате «Итоговый порядок: ...». Верни только готовый промпт для решающей модели, не длиннее 250 слов.\n\n${prompt}` }], 5000) },
    { id: 'generated', title: CALL_TITLES.generated, request: request([{ role: 'user', content: generatedPrompt || '[Будет заменено результатом вызова «Конструктор промпта»]' }], 6000) },
    { id: 'experts', title: CALL_TITLES.experts, request: request([{ role: 'user', content: `${prompt}\n\nРаботай как группа из трёх экспертов: аналитик составит таблицу ограничений; инженер проверит решение перебором; критик попробует найти ошибку. Затем координатор сравнит выводы и укажет итоговый порядок.` }], 5000) },
  ];
}

async function complete(messages, maxTokens = 5000, callKey, onUpdate = () => {}) {
  const startedAt = Date.now();
  const request = { model: MODEL, messages, temperature: 0.2, max_tokens: maxTokens };
  onUpdate(callKey, { status: 'running', request, startedAt });
  try {
    const completion = await openai.chat.completions.create(request);
    const result = {
      text: getText(completion),
      usage: getUsage(completion),
      finishReason: completion.choices?.[0]?.finish_reason || 'unknown',
      latencyMs: Date.now() - startedAt,
    };
    onUpdate(callKey, { status: 'complete', finishReason: result.finishReason, latencyMs: result.latencyMs, usage: result.usage });
    return result;
  } catch (error) {
    onUpdate(callKey, { status: 'error', latencyMs: Date.now() - startedAt, error: error.message });
    throw error;
  }
}

function extractNames(text) {
  const normalized = text.toLocaleLowerCase('ru-RU');
  return NAMES.map(name => ({
    name,
    index: normalized.indexOf(name.toLocaleLowerCase('ru-RU')),
  })).filter(item => item.index >= 0).sort((left, right) => left.index - right.index).map(item => item.name);
}

function getOrder(text) {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const finalLineIndex = lines.findIndex(line => /итоговый порядок\s*:/iu.test(line));
  if (finalLineIndex >= 0) {
    const finalNames = extractNames(lines[finalLineIndex]);
    if (finalNames.length === EXPECTED_ORDER.length) return finalNames;
  }

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const names = extractNames(lines[index]);
    if (names.length === EXPECTED_ORDER.length) return names;
  }
  return [];
}

function evaluate(text) {
  const order = getOrder(text);
  const positionsCorrect = order.reduce((total, name, index) => total + (name === EXPECTED_ORDER[index] ? 1 : 0), 0);
  const exact = order.length === EXPECTED_ORDER.length && positionsCorrect === EXPECTED_ORDER.length;
  return {
    order,
    exact,
    positionsCorrect,
    score: Math.round((positionsCorrect / EXPECTED_ORDER.length) * 100),
    status: exact ? 'Точный ответ' : order.length ? 'Частично совпадает' : 'Итог не распознан',
  };
}

function methodResult(key, title, description, result, extras = {}) {
  return {
    key,
    title,
    description,
    text: result.text,
    usage: result.usage,
    finishReason: result.finishReason,
    latencyMs: result.latencyMs,
    evaluation: evaluate(result.text),
    ...extras,
  };
}

async function safeRun(key, title, description, operation) {
  try {
    return await operation();
  } catch (error) {
    console.error(`${key} error:`, error.message);
    return {
      key,
      title,
      description,
      error: error.message,
      text: '',
      usage: { promptTokens: null, completionTokens: null, totalTokens: null, reasoningTokens: null },
      evaluation: { order: [], exact: false, positionsCorrect: 0, score: 0, status: 'Ошибка запроса' },
    };
  }
}

async function runExperiment(prompt, onUpdate = () => {}) {
  const direct = safeRun('direct', 'Прямой ответ', 'Только исходная задача, без инструкции о способе рассуждения.', async () => {
    const result = await complete([{ role: 'user', content: prompt }], 5000, 'direct', onUpdate);
    return methodResult('direct', 'Прямой ответ', 'Только исходная задача, без инструкции о способе рассуждения.', result);
  });

  const stepByStep = safeRun('step', 'Пошаговое решение', 'К исходной задаче добавлена инструкция «решай пошагово».', async () => {
    const result = await complete([{ role: 'user', content: `${prompt}\n\nРешай задачу пошагово: перечисли ограничения, проверь варианты и объясни вывод.` }], 5000, 'step', onUpdate);
    return methodResult('step', 'Пошаговое решение', 'К исходной задаче добавлена инструкция «решай пошагово».', result);
  });

  const experts = safeRun('experts', 'Группа экспертов', 'Аналитик, инженер и критик решают задачу независимо, затем координатор сверяет выводы.', async () => {
    const result = await complete([{ role: 'user', content: `${prompt}\n\nРаботай как группа из трёх экспертов:\n- аналитик составит таблицу ограничений и найдёт порядок;\n- инженер проверит решение перебором позиций;\n- критик попробует найти ошибку или альтернативный порядок.\nПусть каждый эксперт сначала даст свой вывод, а затем координатор сравнит их. В последней строке снова укажи итоговый порядок строго в заданном формате.` }], 5000, 'experts', onUpdate);
    return methodResult('experts', 'Группа экспертов', 'Аналитик, инженер и критик решают задачу независимо, затем координатор сверяет выводы.', result);
  });

  const promptBuilder = safeRun('prompt-builder', 'Конструктор промпта', 'Отдельный вызов сначала создаёт промпт для решения задачи.', async () => {
    const result = await complete([{ role: 'user', content: `Ты prompt-инженер. Составь подробный, но компактный промпт для другой модели, который поможет надёжно решить эту задачу. Промпт должен включать саму задачу, требование проверить все ограничения, не выдумывать условия и завершать ответ строкой в формате «Итоговый порядок: ...». Верни только готовый промпт для решающей модели, не длиннее 250 слов.\n\n${prompt}` }], 5000, 'prompt-builder', onUpdate);
    return result;
  });

  const [directResult, stepResult, expertResult, builderResult] = await Promise.all([direct, stepByStep, experts, promptBuilder]);
  const generatedPrompt = builderResult.text;
  const generatedPromptSolver = builderResult.error
    ? await safeRun('generated', 'Сгенерированный промпт', 'Сначала модель составила промпт, затем этот промпт был использован для решения.', async () => {
      onUpdate('generated', { status: 'error', error: `Конструктор промпта не ответил: ${builderResult.error}` });
      throw new Error(`Конструктор промпта не ответил: ${builderResult.error}`);
    })
    : await safeRun('generated', 'Сгенерированный промпт', 'Сначала модель составила промпт, затем этот промпт был использован для решения.', async () => {
    const result = await complete([{ role: 'user', content: `${generatedPrompt}\n\nДополнительное требование эксперимента: реши исходную задачу кратко, проверь ограничения и последней строкой укажи итоговый порядок в формате «Итоговый порядок: Имя 1, Имя 2, Имя 3, Имя 4, Имя 5, Имя 6».` }], 6000, 'generated', onUpdate);
    return methodResult('generated', 'Сгенерированный промпт', 'Сначала модель составила промпт, затем этот промпт был использован для решения.', result, {
      generatedPrompt,
      generatedPromptLength: generatedPrompt.length,
      builderError: builderResult.error || null,
      builderUsage: builderResult.usage,
      builderLatencyMs: builderResult.latencyMs,
      usage: addUsage(builderResult.usage, result.usage),
      latencyMs: builderResult.latencyMs + result.latencyMs,
    });
  });

  const methods = [directResult, stepResult, generatedPromptSolver, expertResult];
  const exactCount = methods.filter(method => method.evaluation?.exact).length;
  const best = methods.filter(method => !method.error).sort((left, right) => (right.evaluation?.score || 0) - (left.evaluation?.score || 0) || (left.usage?.totalTokens || Infinity) - (right.usage?.totalTokens || Infinity))[0];
  return {
    model: MODEL,
    task: prompt,
    expectedOrder: EXPECTED_ORDER,
    methods,
    summary: {
      exactCount,
      totalMethods: methods.length,
      bestMethod: best?.key || null,
      bestTitle: best?.title || null,
      criterion: 'Точность определяется сравнением распознанного итогового порядка с эталоном из ограничений задачи.',
    },
  };
}

app.get('/api/config', (req, res) => {
  res.json({ model: MODEL, task: TASK, expectedOrder: EXPECTED_ORDER, methods: ['direct', 'step', 'generated', 'experts'], calls: buildCallPreview(TASK), apiKeyConfigured: Boolean(process.env.OPENAI_API_KEY) });
});

app.post('/api/run', async (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : TASK;
  if (!prompt || prompt.length > MAX_PROMPT_LENGTH) {
    return res.status(400).json({ error: `Задача должна содержать от 1 до ${MAX_PROMPT_LENGTH} символов.` });
  }
  const id = crypto.randomUUID();
  const job = { id, prompt, state: 'running', calls: buildCallPreview(prompt).map(call => ({ ...call, status: 'waiting' })), startedAt: Date.now() };
  jobs.set(id, job);
  res.status(202).json({ runId: id, state: job.state, calls: job.calls });
  runExperiment(prompt, (key, event) => {
    const call = job.calls.find(item => item.id === key);
    if (call) Object.assign(call, event);
    job.updatedAt = Date.now();
  }).then(result => {
    job.state = 'complete';
    job.result = result;
    job.updatedAt = Date.now();
  }).catch(error => {
    job.state = 'error';
    job.error = error.message;
    job.updatedAt = Date.now();
  });
});

app.get('/api/run/:id', (req, res) => {
  const job = jobs.get(req.params.id);
  if (!job) return res.status(404).json({ error: 'Запуск не найден или уже удалён.' });
  res.json({ id: job.id, state: job.state, calls: job.calls, result: job.result || null, error: job.error || null, elapsedMs: (job.state === 'running' ? Date.now() : job.updatedAt) - job.startedAt });
});

const PORT = process.env.PORT || 3003;
app.listen(PORT, () => console.log(`Day 3 reasoning comparison running at http://localhost:${PORT}`));
