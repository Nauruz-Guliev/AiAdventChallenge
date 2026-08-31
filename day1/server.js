require('dotenv').config();
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json({ limit: '32kb' }));

// Serve static frontend
app.use(express.static(path.join(__dirname, 'public')));

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || undefined,
});

const SUPPORTED_MODELS = [
  { id: 'kimi-k3', name: 'Kimi K3', description: 'Balanced everyday chat' },
  { id: 'qwen3.6-plus', name: 'Qwen 3.6 Plus', description: 'Strong reasoning and coding' },
  { id: 'minimax-m3', name: 'MiniMax M3', description: 'Fast general assistant' },
];

// Keep conversations isolated by browser session in this local demo.
const sessions = new Map();
const activeSessions = new Set();
const MAX_MESSAGE_LENGTH = 4000;
const MAX_HISTORY_MESSAGES = 20;

const SYSTEM_PROMPT = {
  role: 'system',
  content: 'You are a helpful assistant chatting with Nauruz. Answer in the same language as the user. Do not translate the user\'s message or add translations. Use markdown when appropriate. Be concise, clear, and complete. Never claim to show private hidden chain-of-thought. If asked how you reasoned, provide a short useful summary instead.'
};

app.get('/api/models', (req, res) => {
  res.json({ models: SUPPORTED_MODELS });
});

app.post('/api/chat', async (req, res) => {
  try {
    const { message, model, sessionId } = req.body;
    if (!message || typeof message !== 'string' || !message.trim()) {
      return res.status(400).json({ error: 'Message is required' });
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      return res.status(413).json({ error: `Message must be shorter than ${MAX_MESSAGE_LENGTH} characters` });
    }
    if (!sessionId || !/^[a-zA-Z0-9_-]{8,80}$/.test(sessionId)) {
      return res.status(400).json({ error: 'A valid session is required' });
    }
    if (activeSessions.has(sessionId)) {
      return res.status(409).json({ error: 'Another message is already being processed' });
    }

    const selectedModel = SUPPORTED_MODELS.some(item => item.id === model)
      ? model
      : SUPPORTED_MODELS[0].id;

    const history = sessions.get(sessionId) || [];
    activeSessions.add(sessionId);

    const completion = await openai.chat.completions.create({
      model: selectedModel,
      messages: [SYSTEM_PROMPT, ...history, { role: 'user', content: message.trim() }],
      temperature: 0.7,
    });

    const assistantMessage = completion.choices[0].message;
    const reply = assistantMessage.content || '';
    // Only expose a provider-generated summary, never hidden chain-of-thought.
    const reasoning = assistantMessage.reasoning_summary || null;
    sessions.set(sessionId, [
      ...history,
      { role: 'user', content: message.trim() },
      { role: 'assistant', content: reply },
    ].slice(-MAX_HISTORY_MESSAGES));
    activeSessions.delete(sessionId);

    res.json({ response: reply, reasoning });
  } catch (error) {
    console.error('OpenAI error:', error.message);
    if (req.body?.sessionId) activeSessions.delete(req.body.sessionId);
    const status = error.status === 401 ? 401 : error.status === 429 ? 429 : 502;
    const errorMessage = status === 401
      ? 'The API key was rejected. Check your local .env file.'
      : status === 429
        ? 'The model is temporarily busy. Try again in a moment.'
        : 'The LLM request failed. Check the API endpoint and try again.';
    res.status(status).json({ error: errorMessage });
  }
});

// Reset conversation
app.post('/api/clear', (req, res) => {
  const { sessionId } = req.body;
  if (sessionId) {
    sessions.delete(sessionId);
    activeSessions.delete(sessionId);
  }
  res.json({ ok: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✨ Advent Challenge Chat running at http://localhost:${PORT}`);
});
