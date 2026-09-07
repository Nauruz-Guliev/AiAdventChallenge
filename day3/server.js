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

const TASK = `Задача «Четыре двери».
Вы находитесь в помещении, в котором есть маленькое окно, закрытое ставнями, и четыре двери. Двери заперты на замок, три из них фальшивые: за ними сразу стена. Четвёртая ведёт на улицу. Комната тёмная, из источников света у вас есть только свеча.

У вас есть ключ, которым можно открыть любую из четырёх дверей, но выбрать можно только одну из них. Вам нужно понять, какая дверь поможет выйти на улицу. Не спешите: у вас всего одна попытка.

Как вы будете искать единственную дверь, через которую можно выйти из комнаты? Обоснуй ответ и опиши безопасный порядок действий.`;

const REFERENCE_ANSWER = 'Нужно подставлять свечу по очереди к дверям, к щелям или к замочной скважине, и внимательно смотреть на пламя свечи. Колебание пламени укажет на поток воздуха и выход на улицу. Проверять нужно до выбора двери, не открывая двери ключом.';
const STEP_SYSTEM_PROMPT = 'Решай задачу пошагово: перечисли условия, проверь варианты и объясни вывод. В конце обязательно дай краткий ответ, даже если внутреннее рассуждение было длинным.';
const EXPERT_SYSTEM_PROMPT = 'Работай как группа из трёх экспертов. Аналитик выделит физические признаки выхода. Инженер составит безопасный порядок проверки. Критик попробует найти ошибку или опасный шаг. Пусть каждый эксперт сначала даст свой вывод, а затем координатор сравнит их и сформулирует итоговый ответ. В конце обязательно дай краткий итог.';
const PROMPT_BUILDER_SYSTEM_PROMPT = 'Ты prompt-инженер. Составь только reusable system prompt для другой модели. Не решай исходную задачу, не называй правильную дверь и не раскрывай фактический способ решения. Не упоминай свечу, пламя, поток воздуха или другие предметы из условия. Не повторяй текст задачи. Твой результат должен содержать только методические инструкции: как анализировать условия, проверять гипотезы, избегать случайного выбора и дать краткий обоснованный ответ по задаче из user message.';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://api.deepseek.com/v1',
  timeout: 180000,
  maxRetries: 0,
});

const CALL_TITLES = {
  direct: '01 · Прямой ответ',
  step: '02 · Пошаговый ответ',
  'prompt-builder': '03 · Конструктор промпта',
  generated: '04 · Решение по сгенерированному промпту',
  experts: '05 · Группа экспертов',
  judge: '06 · Верификатор ответов',
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

function buildCallPreview(prompt, generatedPrompt = '', methodOutputs = '') {
  const request = (messages, maxTokens) => ({ model: MODEL, messages, temperature: 0.2, max_tokens: maxTokens });
  return [
    { id: 'direct', title: CALL_TITLES.direct, request: request([{ role: 'user', content: prompt }], 1600) },
    { id: 'step', title: CALL_TITLES.step, request: request([{ role: 'system', content: STEP_SYSTEM_PROMPT }, { role: 'user', content: prompt }], 2200) },
    { id: 'prompt-builder', title: CALL_TITLES['prompt-builder'], request: request([{ role: 'system', content: PROMPT_BUILDER_SYSTEM_PROMPT }, { role: 'user', content: `Создай system prompt для решения задачи из этого user message. Итоговый prompt будет передан решающей модели отдельно от задачи. Верни только system prompt, не решение и не пересказ условия.\n\nКонтекст задачи для тебя (не повторяй его):\n${prompt}` }], 1800) },
    { id: 'generated', title: CALL_TITLES.generated, request: request([{ role: 'system', content: generatedPrompt || '[БУДЕТ ПОДСТАВЛЕН СФОРМИРОВАННЫЙ SYSTEM PROMPT]' }, { role: 'user', content: prompt }], 1800) },
    { id: 'experts', title: CALL_TITLES.experts, request: request([{ role: 'system', content: EXPERT_SYSTEM_PROMPT }, { role: 'user', content: prompt }], 2600) },
    { id: 'judge', title: CALL_TITLES.judge, request: request([{ role: 'user', content: methodOutputs || '[Сюда будут подставлены четыре ответа и эталон проверки]' }], 3500) },
  ];
}

function getPromptBuilderRequest(prompt) {
  return buildCallPreview(prompt).find(call => call.id === 'prompt-builder').request;
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

function evaluate(text) {
  const normalized = text.toLocaleLowerCase('ru-RU');
  const criteria = [
    { label: 'свеча', matched: /свеч/iu.test(normalized) },
    { label: 'проверка у дверей', matched: /двер.{0,30}(щел|скваж)|щел.{0,30}двер|скважин/iu.test(normalized) },
    { label: 'наблюдение за пламенем', matched: /плам|огон.{0,20}свеч/iu.test(normalized) },
    { label: 'колебание пламени', matched: /колеб|дрож|движен|наклон|мерцан/iu.test(normalized) },
    { label: 'поток воздуха или улица', matched: /воздух|сквозняк|поток|улиц|выход/iu.test(normalized) },
  ];
  const matchedCriteria = criteria.filter(item => item.matched).map(item => item.label);
  const score = Math.round((matchedCriteria.length / criteria.length) * 100);
  return {
    exact: matchedCriteria.length === criteria.length,
    score,
    matchedCriteria,
    status: matchedCriteria.length === criteria.length ? 'Все ключевые идеи найдены' : `${matchedCriteria.length}/${criteria.length} идей найдены`,
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
      evaluation: { exact: false, score: 0, matchedCriteria: [], status: 'Ошибка запроса' },
    };
  }
}

function buildJudgePrompt(methods) {
  const answers = methods.map(method => `\n--- ${method.title} (${method.key}) ---\n${method.text || '[Ответ не получен]'}`).join('');
  return `Ты независимый верификатор ответов на логическую задачу. Сравни четыре ответа с эталонным принципом решения.

Эталонный принцип: ${REFERENCE_ANSWER}

Ответ считается корректным, если в нём есть все ключевые идеи: свечу подносят к каждой двери или её щели/замочной скважине до выбора; наблюдают за пламенем; колебание пламени означает поток воздуха и указывает на дверь, ведущую наружу; дверь не открывают до проверки.

Верни только JSON без markdown в формате:
{"direct":{"correct":true,"score":100,"reason":"краткое объяснение"},"step":{"correct":true,"score":100,"reason":"..."},"generated":{"correct":true,"score":100,"reason":"..."},"experts":{"correct":true,"score":100,"reason":"..."}}
Оцени каждый ответ независимо. Если пропущена ключевая идея, correct должен быть false, а score от 0 до 99.${answers}`;
}

function parseJudge(text) {
  try {
    const jsonText = text.replace(/^```json\s*/iu, '').replace(/\s*```$/u, '').match(/\{[\s\S]*\}/)?.[0];
    return jsonText ? JSON.parse(jsonText) : null;
  } catch (error) {
    return null;
  }
}

function applyJudge(methods, judgeText) {
  const judged = parseJudge(judgeText);
  if (!judged) return false;
  methods.forEach(method => {
    const result = judged[method.key];
    if (!result || typeof result.correct !== 'boolean') return;
    method.evaluation = {
      ...method.evaluation,
      exact: result.correct,
      score: Number.isFinite(result.score) ? result.score : result.correct ? 100 : method.evaluation.score,
      judgeCorrect: result.correct,
      judgeReason: result.reason || 'Верификатор не добавил объяснение.',
      status: result.correct ? 'Верификатор: корректно' : 'Верификатор: есть ошибка',
    };
  });
  return true;
}

async function executeMethod(method, prompt, generatedPrompt, onUpdate) {
  const definitions = {
    direct: {
      title: 'Прямой ответ',
      description: 'Только исходная задача. Никаких дополнительных инструкций.',
      messages: [{ role: 'user', content: prompt }],
      maxTokens: 1600,
    },
    step: {
      title: 'Пошаговое решение',
      description: 'К задаче добавлен отдельный system prompt с просьбой рассуждать пошагово.',
      messages: [{ role: 'system', content: STEP_SYSTEM_PROMPT }, { role: 'user', content: prompt }],
      maxTokens: 2200,
    },
    generated: {
      title: 'Сгенерированный промпт',
      description: 'Сначала сформирован system prompt, затем с ним выполнен отдельный запрос.',
      messages: [{ role: 'system', content: generatedPrompt }, { role: 'user', content: prompt }],
      maxTokens: 1800,
    },
    experts: {
      title: 'Группа экспертов',
      description: 'Один system prompt создаёт аналитика, инженера, критика и координатора.',
      messages: [{ role: 'system', content: EXPERT_SYSTEM_PROMPT }, { role: 'user', content: prompt }],
      maxTokens: 2600,
    },
  };
  const definition = definitions[method];
  if (!definition) throw new Error('Неизвестный вариант решения.');
  if (method === 'generated' && !generatedPrompt) throw new Error('Сначала сформируйте промпт.');
  const result = await complete(definition.messages, definition.maxTokens, method, onUpdate);
  return methodResult(method, definition.title, definition.description, result, method === 'generated' ? { generatedPrompt, generatedPromptLength: generatedPrompt.length } : {});
}

async function runExperiment(prompt, onUpdate = () => {}, providedGeneratedPrompt = '') {
  const direct = safeRun('direct', 'Прямой ответ', 'Только исходная задача, без инструкции о способе рассуждения.', async () => {
    const result = await complete([{ role: 'user', content: prompt }], 5000, 'direct', onUpdate);
    return methodResult('direct', 'Прямой ответ', 'Только исходная задача, без инструкции о способе рассуждения.', result);
  });

  const stepByStep = safeRun('step', 'Пошаговое решение', 'К исходной задаче добавлена инструкция «решай пошагово».', async () => {
    const result = await complete([{ role: 'system', content: STEP_SYSTEM_PROMPT }, { role: 'user', content: prompt }], 7000, 'step', onUpdate);
    return methodResult('step', 'Пошаговое решение', 'К исходной задаче добавлена инструкция «решай пошагово».', result);
  });

  const experts = safeRun('experts', 'Группа экспертов', 'Аналитик, инженер и критик решают задачу независимо, затем координатор сверяет выводы.', async () => {
    const result = await complete([{ role: 'system', content: EXPERT_SYSTEM_PROMPT }, { role: 'user', content: prompt }], 7000, 'experts', onUpdate);
    return methodResult('experts', 'Группа экспертов', 'Аналитик, инженер и критик решают задачу независимо, затем координатор сверяет выводы.', result);
  });

  const promptBuilder = providedGeneratedPrompt
    ? Promise.resolve({ text: providedGeneratedPrompt, usage: { promptTokens: null, completionTokens: null, totalTokens: null, reasoningTokens: null }, latencyMs: 0, finishReason: 'provided' })
    : safeRun('prompt-builder', 'Конструктор промпта', 'Отдельный вызов сначала создаёт промпт для решения задачи.', async () => {
      const request = getPromptBuilderRequest(prompt);
      const result = await complete(request.messages, request.max_tokens, 'prompt-builder', onUpdate);
      return result;
    });

  const [directResult, stepResult, expertResult, builderResult] = await Promise.all([direct, stepByStep, experts, promptBuilder]);
  if (providedGeneratedPrompt) onUpdate('prompt-builder', { status: 'provided', request: getPromptBuilderRequest(prompt) });
  const generatedPrompt = builderResult.text;
  const generatedPromptSolver = builderResult.error
    ? await safeRun('generated', 'Сгенерированный промпт', 'Сначала модель составила промпт, затем этот промпт был использован для решения.', async () => {
      onUpdate('generated', { status: 'error', error: `Конструктор промпта не ответил: ${builderResult.error}` });
      throw new Error(`Конструктор промпта не ответил: ${builderResult.error}`);
    })
    : await safeRun('generated', 'Сгенерированный промпт', 'Сначала модель составила промпт, затем этот промпт был использован для решения.', async () => {
    const result = await complete([{ role: 'system', content: generatedPrompt }, { role: 'user', content: prompt }], 6000, 'generated', onUpdate);
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
  const judgePrompt = buildJudgePrompt(methods);
  const judgeResult = await safeRun('judge', 'Верификатор ответов', 'Отдельный API-запрос сравнивает четыре ответа с эталонным принципом.', async () => complete([{ role: 'user', content: judgePrompt }], 3500, 'judge', onUpdate));
  const judgeParsed = applyJudge(methods, judgeResult.text || '');
  const exactCount = methods.filter(method => method.evaluation?.exact).length;
  const best = methods.filter(method => !method.error).sort((left, right) => (right.evaluation?.score || 0) - (left.evaluation?.score || 0) || (left.usage?.totalTokens || Infinity) - (right.usage?.totalTokens || Infinity))[0];
  return {
    model: MODEL,
    task: prompt,
    referenceAnswer: REFERENCE_ANSWER,
    methods,
    verification: { text: judgeResult.text || '', parsed: judgeParsed, usage: judgeResult.usage, latencyMs: judgeResult.latencyMs, finishReason: judgeResult.finishReason },
    summary: {
      exactCount,
      totalMethods: methods.length,
      bestMethod: best?.key || null,
      bestTitle: best?.title || null,
      criterion: 'Точность определяет отдельный API-верификатор по эталонному принципу решения.',
    },
  };
}

app.get('/api/config', (req, res) => {
  res.json({ model: MODEL, task: TASK, referenceAnswer: REFERENCE_ANSWER, methods: ['direct', 'step', 'generated', 'experts'], calls: buildCallPreview(TASK), apiKeyConfigured: Boolean(process.env.OPENAI_API_KEY) });
});

app.post('/api/generate-prompt', async (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : TASK;
  const id = crypto.randomUUID();
  const job = { id, prompt, state: 'running', calls: [{ ...buildCallPreview(prompt).find(call => call.id === 'prompt-builder'), status: 'waiting' }], startedAt: Date.now() };
  jobs.set(id, job);
  res.status(202).json({ runId: id, state: job.state, calls: job.calls });
  complete(getPromptBuilderRequest(prompt).messages, getPromptBuilderRequest(prompt).max_tokens, 'prompt-builder', (key, event) => {
    const call = job.calls.find(item => item.id === key);
    if (call) Object.assign(call, event);
    job.updatedAt = Date.now();
  }).then(result => {
    job.state = 'complete';
    job.result = { prompt: result.text, usage: result.usage, latencyMs: result.latencyMs, finishReason: result.finishReason };
    job.updatedAt = Date.now();
  }).catch(error => {
    job.state = 'error';
    job.error = error.message;
    job.updatedAt = Date.now();
  });
});

app.post('/api/run-method', async (req, res) => {
  const method = typeof req.body?.method === 'string' ? req.body.method : '';
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : TASK;
  const generatedPrompt = typeof req.body?.generatedPrompt === 'string' ? req.body.generatedPrompt.trim() : '';
  if (!['direct', 'step', 'generated', 'experts'].includes(method)) return res.status(400).json({ error: 'Неизвестный вариант решения.' });
  const id = crypto.randomUUID();
  const preview = buildCallPreview(prompt, generatedPrompt).find(call => call.id === method);
  const job = { id, prompt, method, state: 'running', calls: [{ ...preview, status: 'waiting' }], startedAt: Date.now() };
  jobs.set(id, job);
  res.status(202).json({ runId: id, state: job.state, calls: job.calls });
  executeMethod(method, prompt, generatedPrompt, (key, event) => {
    const call = job.calls.find(item => item.id === key);
    if (call) Object.assign(call, event);
    job.updatedAt = Date.now();
  }).then(result => {
    job.state = 'complete';
    job.result = { method: result };
    job.updatedAt = Date.now();
  }).catch(error => {
    job.state = 'error';
    job.error = error.message;
    job.updatedAt = Date.now();
  });
});

app.post('/api/run', async (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : TASK;
  const generatedPrompt = typeof req.body?.generatedPrompt === 'string' ? req.body.generatedPrompt.trim() : '';
  if (!prompt || prompt.length > MAX_PROMPT_LENGTH) {
    return res.status(400).json({ error: `Задача должна содержать от 1 до ${MAX_PROMPT_LENGTH} символов.` });
  }
  const id = crypto.randomUUID();
  const job = { id, prompt, state: 'running', calls: buildCallPreview(prompt, generatedPrompt).map(call => ({ ...call, status: call.id === 'prompt-builder' && generatedPrompt ? 'provided' : 'waiting' })), startedAt: Date.now() };
  jobs.set(id, job);
  res.status(202).json({ runId: id, state: job.state, calls: job.calls });
  runExperiment(prompt, (key, event) => {
    const call = job.calls.find(item => item.id === key);
    if (call) Object.assign(call, event);
    job.updatedAt = Date.now();
  }, generatedPrompt).then(result => {
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
