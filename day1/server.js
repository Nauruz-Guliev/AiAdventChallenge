require('dotenv').config();
const path = require('path');
const express = require('express');
const OpenAI = require('openai');

const app = express();
app.use(express.json());

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

// In-memory conversation history for this local demo.
const history = [];

const SYSTEM_PROMPT = {
  role: 'system',
  content: 'You are a helpful assistant chatting with Nauruz. Answer in the same language as the user. Do not translate the user\'s message or add translations. Use markdown when appropriate. Be concise, clear, and complete. Never claim to show private hidden chain-of-thought. If asked how you reasoned, provide a short useful summary instead.'
};

app.get('/api/models', (req, res) => {
  res.json({ models: SUPPORTED_MODELS });
});

app.post('/api/chat', async (req, res) => {
  try {
    const { message, model } = req.body;
    if (!message || typeof message !== 'string') {
      return res.status(400).json({ error: 'Message is required' });
    }

    const selectedModel = SUPPORTED_MODELS.some(item => item.id === model)
      ? model
      : SUPPORTED_MODELS[0].id;

    history.push({ role: 'user', content: message });

    const completion = await openai.chat.completions.create({
      model: selectedModel,
      messages: [SYSTEM_PROMPT, ...history],
      temperature: 0.7,
    });

    const assistantMessage = completion.choices[0].message;
    const reply = assistantMessage.content || '';
    // Only expose a provider-generated summary, never hidden chain-of-thought.
    const reasoning = assistantMessage.reasoning_summary || null;
    history.push({ role: 'assistant', content: reply });

    res.json({ response: reply, reasoning });
  } catch (error) {
    console.error('OpenAI error:', error.message);
    history.pop();
    res.status(500).json({ error: error.message || 'LLM request failed' });
  }
});

// Reset conversation
app.post('/api/clear', (req, res) => {
  history.length = 0;
  res.json({ ok: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✨ Advent Challenge Chat running at http://localhost:${PORT}`);
});
