import { useState } from 'react';
import { askAgent } from './api.js';
import AgentFlow from './components/AgentFlow.jsx';
import ChatPanel from './components/ChatPanel.jsx';

const initialStages = [
  { name: 'UI', status: 'completed' },
  { name: 'Agent', status: 'pending' },
  { name: 'DeepSeek API', status: 'pending' },
];

export default function App() {
  const [message, setMessage] = useState('');
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [stages, setStages] = useState(initialStages);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedMessage = message.trim();
    if (!trimmedMessage || loading) return;

    setLoading(true);
    setAnswer('');
    setResult(null);
    setError('');
    setStages([
      { name: 'UI', status: 'completed' },
      { name: 'Agent', status: 'active' },
      { name: 'DeepSeek API', status: 'pending' },
    ]);

    try {
      const response = await askAgent(trimmedMessage);
      setAnswer(response.answer);
      setResult(response);
      setStages(response.stages);
    } catch (requestError) {
      setError(requestError.message);
      setStages(currentStages => currentStages.map(stage => ({
        ...stage,
        status: stage.name === 'DeepSeek API' ? 'error' : stage.status,
      })));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <div className="eyebrow"><span className="pulse-dot" /> DAY 06 / FIRST AGENT</div>
        <h1>Не просто вызов API.<br /><em>Отдельный агент.</em></h1>
        <p className="hero-copy">
          Введи вопрос и проследи, как он проходит через интерфейс,
          Python-агента и DeepSeek.
        </p>
      </header>

      <section className="workspace" aria-label="Agent workspace">
        <ChatPanel
          answer={answer}
          error={error}
          loading={loading}
          message={message}
          result={result}
          onChange={setMessage}
          onSubmit={handleSubmit}
        />
        <AgentFlow loading={loading} stages={stages} />
      </section>

      <footer className="page-footer">
        <span>FASTAPI + REACT</span>
        <span>ONE REQUEST / NO MEMORY</span>
      </footer>
    </main>
  );
}
