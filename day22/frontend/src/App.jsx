import { useState } from 'react';
import { askQuestion, runEval } from './api.js';
import AnswerPanel from './components/AnswerPanel.jsx';
import CompareTable from './components/CompareTable.jsx';
import QuestionInput from './components/QuestionInput.jsx';

export default function App() {
  const [result, setResult] = useState(null);
  const [report, setReport] = useState(null);
  const [tab, setTab] = useState('ask');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleAsk(question) {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      setResult(await askQuestion(question));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleEval() {
    setLoading(true);
    setError('');
    try {
      setReport(await runEval());
      setTab('compare');
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header className="masthead">
        <h1>Первый RAG-запрос</h1>
        <p>Один вопрос — два ответа: модель без документов и модель с поиском по базе KMP.</p>
      </header>

      <nav className="tabs">
        <button className={tab === 'ask' ? 'active' : ''} onClick={() => setTab('ask')}>Вопрос</button>
        <button className={tab === 'compare' ? 'active' : ''} onClick={() => setTab('compare')}>Сравнение по 10 вопросам</button>
      </nav>

      {error && <div className="error">{error}</div>}

      {tab === 'ask' && (
        <section>
          <QuestionInput onSubmit={handleAsk} disabled={loading} />
          {result && (
            <div className="answers">
              <AnswerPanel title="Без RAG" answer={result.no_rag} />
              <AnswerPanel title="С RAG" answer={result.rag} />
            </div>
          )}
        </section>
      )}

      {tab === 'compare' && (
        <section>
          <div className="eval-actions">
            <button onClick={handleEval} disabled={loading}>
              {loading ? 'Считаем…' : 'Запустить сравнение'}
            </button>
          </div>
          {report && <CompareTable report={report} />}
        </section>
      )}
    </main>
  );
}
