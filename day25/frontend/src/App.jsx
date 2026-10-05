import { useEffect, useState } from 'react';
import {
  listSessions,
  getSession,
  createSession,
  sendMessage,
  runScenarios,
} from './api.js';
import Chat from './components/Chat.jsx';
import MemoryPanel from './components/MemoryPanel.jsx';

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState(null);
  const [goal, setGoal] = useState('');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [reports, setReports] = useState(null);
  const [tab, setTab] = useState('chat');

  async function refreshSessions() {
    setSessions(await listSessions());
  }

  useEffect(() => {
    refreshSessions().catch(() => {});
  }, []);

  async function handleCreate() {
    if (!goal.trim()) return;
    setError('');
    try {
      const created = await createSession(goal);
      setSession(created);
      setGoal('');
      await refreshSessions();
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleOpen(id) {
    setError('');
    try {
      setSession(await getSession(id));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function handleSend() {
    if (!session || !text.trim()) return;
    setLoading(true);
    setError('');
    const pending = text.trim();
    setText('');
    try {
      const turn = await sendMessage(session.id, pending);
      const assistant = {
        role: 'assistant',
        text: turn.reply,
        sources: turn.sources,
        citations: turn.citations,
        at: new Date().toISOString(),
      };
      setSession((prev) => ({
        ...prev,
        memory: turn.memory,
        messages: [
          ...prev.messages,
          { role: 'user', text: pending, sources: [], citations: [], at: new Date().toISOString() },
          assistant,
        ],
      }));
      await refreshSessions();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunScenarios() {
    setLoading(true);
    setError('');
    try {
      setReports(await runScenarios());
      setTab('scenarios');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header className="masthead">
        <h1>Мини-чат с RAG и памятью задачи</h1>
        <p>Диалог с источниками из базы KMP и живой памятью задачи.</p>
      </header>

      <nav className="tabs">
        <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>Чат</button>
        <button className={tab === 'scenarios' ? 'active' : ''} onClick={() => setTab('scenarios')}>Сценарии</button>
      </nav>

      {error && <div className="error">{error}</div>}

      {tab === 'chat' && (
        <div className="layout">
          <aside className="sidebar">
            <div className="new-session">
              <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Цель новой сессии…" />
              <button onClick={handleCreate} disabled={!goal.trim()}>Новая сессия</button>
            </div>
            <ul className="session-list">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className={session && session.id === s.id ? 'active' : ''}
                  onClick={() => handleOpen(s.id)}
                >
                  <div className="s-goal">{s.goal || '(без цели)'}</div>
                  <div className="s-meta">{s.n_messages} сообщ.</div>
                </li>
              ))}
            </ul>
          </aside>

          <section className="chat-area">
            {session ? (
              <>
                <MemoryPanel memory={session.memory} />
                <Chat messages={session.messages} />
                <div className="composer">
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Вопрос…"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
                  />
                  <button onClick={handleSend} disabled={loading || !text.trim()}>
                    {loading ? '…' : 'Отправить'}
                  </button>
                </div>
              </>
            ) : (
              <p className="muted">Создайте или выберите сессию слева.</p>
            )}
          </section>
        </div>
      )}

      {tab === 'scenarios' && (
        <section>
          <div className="eval-actions">
            <button onClick={handleRunScenarios} disabled={loading}>
              {loading ? 'Считаем…' : 'Запустить сценарии'}
            </button>
          </div>
          {reports && (
            <div className="reports">
              {reports.map((r) => (
                <div key={r.name} className={`report ${r.passed ? 'passed' : 'failed'}`}>
                  <h3>{r.name}</h3>
                  <p>
                    Ходов: {r.turns} · Источники всегда: {r.all_with_sources ? 'да' : 'нет'} ·
                    Цель не потеряна: {r.goal_kept ? 'да' : 'нет'} ·
                    Память накоплена: {r.memory_grown ? 'да' : 'нет'}
                  </p>
                  <div className="report-status">{r.passed ? 'PASSED' : 'FAILED'}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
