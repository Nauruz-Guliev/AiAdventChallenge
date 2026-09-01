require('dotenv').config();
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '16kb' }));
app.use(express.static(path.join(__dirname, 'public')));

const MODEL = 'deepseek-v4-pro';
const MAX_PROMPT_LENGTH = 4000;
const STOP_SEQUENCE = '[[DONE]]';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://api.deepseek.com/v1',
});

const CONTROL_INSTRUCTIONS = [
  'Верни ровно 3 нумерованных пункта, каждый пункт с новой строки, в формате: 1. ... новая строка 2. ... новая строка 3. ...',
  'Каждый пункт должен быть одним предложением, желательно от 12 до 15 слов, но никогда не больше 18 слов.',
  `Не добавляй заголовок, вступление, заключение или другой текст. Проверь все правила перед ответом. Заверши ответ маркером ${STOP_SEQUENCE}.`,
].join(' ');

function getItems(text) {
  return text.replace(/\r/g, '').split(/\n+/).flatMap(line => line.split(/(?=\d+\.\s+)/)).map(item => item.trim()).filter(Boolean);
}

function isControlledResponse(text) {
  const items = getItems(text);
  return items.length === 3 && items.every((item, index) => {
    const body = item.replace(new RegExp(`^${index + 1}\\.\\s+`), '').trim();
    return body.length > 0 && /[.!?]$/.test(body) && body.split(/\s+/).length <= 18;
  });
}

async function requestControlled(prompt) {
  const request = {
    model: MODEL,
    messages: [
      { role: 'system', content: CONTROL_INSTRUCTIONS },
      { role: 'user', content: prompt },
    ],
    max_tokens: 2000,
    stop: [STOP_SEQUENCE],
    temperature: 0.2,
  };

  let completion;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    completion = await openai.chat.completions.create(request);
    if (isControlledResponse(getText(completion))) return completion;
  }
  return completion;
}

function getText(completion) {
  return (completion.choices?.[0]?.message?.content || '').replaceAll(STOP_SEQUENCE, '').trim();
}

function getResult(completion) {
  const finishReason = completion.choices?.[0]?.finish_reason || 'unknown';
  const usage = completion.usage || {};
  return {
    text: getText(completion),
    finishReason,
    stopTriggered: finishReason === 'stop',
    promptTokens: usage.prompt_tokens ?? null,
    completionTokens: usage.completion_tokens ?? null,
    totalTokens: usage.total_tokens ?? null,
    reasoningTokens: usage.completion_tokens_details?.reasoning_tokens ?? null,
  };
}

app.get('/api/config', (req, res) => {
  res.json({
    provider: 'DeepSeek API',
    model: MODEL,
    controlled: {
      instructions: CONTROL_INSTRUCTIONS,
      format: 'Ровно 3 нумерованных пункта, по одному предложению',
      length: 'Максимум 18 слов в каждом пункте',
      stop: STOP_SEQUENCE,
      maxTokens: 2000,
      temperature: 0.2,
    },
  });
});

app.post('/api/compare', async (req, res) => {
  const prompt = typeof req.body?.prompt === 'string' ? req.body.prompt.trim() : '';
  if (!prompt) return res.status(400).json({ error: 'Enter a prompt to compare.' });
  if (prompt.length > MAX_PROMPT_LENGTH) {
    return res.status(413).json({ error: `Prompt must be shorter than ${MAX_PROMPT_LENGTH} characters.` });
  }

  try {
    // Both calls use the identical user prompt and model; only response controls differ.
    const [baseline, controlled] = await Promise.all([
      openai.chat.completions.create({
        model: MODEL,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.2,
      }),
      requestControlled(prompt),
    ]);

    res.json({
      model: MODEL,
      prompt,
      baseline: getResult(baseline),
      controlled: getResult(controlled),
    });
  } catch (error) {
    console.error('Comparison error:', error.message);
    const status = error.status === 401 ? 401 : error.status === 429 ? 429 : 502;
    const message = status === 401
      ? 'API-ключ отклонён. Проверьте локальный файл .env.'
      : status === 429
        ? 'Модель временно перегружена. Попробуйте ещё раз через некоторое время.'
        : 'Сравнение не выполнено. Проверьте API endpoint и повторите попытку.';
    res.status(status).json({ error: message });
  }
});

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => {
  console.log(`Day 2 comparison running at http://localhost:${PORT}`);
});
