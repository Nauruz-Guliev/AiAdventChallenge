require('dotenv').config();
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '16kb' }));
app.use(express.static(path.join(__dirname, 'public')));

const MODEL = 'qwen3.6-plus';
const MAX_PROMPT_LENGTH = 4000;
const STOP_SEQUENCE = '<END>';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || 'https://opencode.ai/zen/go/v1',
});

const CONTROL_INSTRUCTIONS = [
  'Return exactly 3 numbered items using this format: 1. ..., 2. ..., 3. ...',
  'Each item must be exactly one sentence and no longer than 18 words.',
  `Do not add a title, introduction, conclusion, or extra text. End with ${STOP_SEQUENCE}.`,
].join(' ');

function getText(completion) {
  return completion.choices?.[0]?.message?.content?.trim() || '';
}

function getResult(completion) {
  return {
    text: getText(completion),
    finishReason: completion.choices?.[0]?.finish_reason || 'unknown',
    promptTokens: completion.usage?.prompt_tokens ?? null,
    completionTokens: completion.usage?.completion_tokens ?? null,
  };
}

app.get('/api/config', (req, res) => {
  res.json({
    model: MODEL,
    controlled: {
      instructions: CONTROL_INSTRUCTIONS,
      format: 'Exactly 3 numbered items, one sentence per item',
      length: '18 words maximum per item',
      stop: STOP_SEQUENCE,
      maxTokens: 600,
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
      }),
      openai.chat.completions.create({
        model: MODEL,
        messages: [
          { role: 'system', content: CONTROL_INSTRUCTIONS },
          { role: 'user', content: prompt },
        ],
        // OpenCode reasoning can consume part of the technical token budget.
        // The visible answer is still limited by the explicit 18-word/item rule.
        max_tokens: 600,
        stop: [STOP_SEQUENCE],
      }),
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
      ? 'The API key was rejected. Check your local .env file.'
      : status === 429
        ? 'The model is temporarily busy. Try again in a moment.'
        : 'The comparison failed. Check the API endpoint and try again.';
    res.status(status).json({ error: message });
  }
});

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => {
  console.log(`Day 2 comparison running at http://localhost:${PORT}`);
});
