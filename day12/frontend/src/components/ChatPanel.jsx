import { useEffect, useRef } from 'react';
import MarkdownMessage from './MarkdownMessage.jsx';

const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};
const TONE_LABELS = {
  formal: 'деловой',
  friendly: 'дружелюбный',
  neutral: 'нейтральный',
};
const LENGTH_LABELS = {
  short: 'коротко',
  medium: 'средне',
  detailed: 'подробно',
};
const STRUCTURE_LABELS = {
  prose: 'текст',
  bullets: 'списки',
  markdown: 'markdown',
};

function UsedMemory({ used }) {
  const longTermParts = used.long_term
    ? Object.entries(used.long_term)
        .filter(([, list]) => list.length)
        .map(([category, list]) => `${CATEGORY_LABELS[category]}: ${list.join('; ')}`)
    : [];
  const working = used.working;
  const workingParts = working
    ? [working.goal && `цель: ${working.goal}`, ...working.constraints, ...working.decisions].filter(Boolean)
    : [];
  const profile = used.profile;
  const profileParts = profile
    ? [
        profile.tone && `тон: ${TONE_LABELS[profile.tone] ?? profile.tone}`,
        profile.length && `объём: ${LENGTH_LABELS[profile.length] ?? profile.length}`,
        profile.structure && `формат: ${STRUCTURE_LABELS[profile.structure] ?? profile.structure}`,
        ...(profile.constraints ?? []),
      ].filter(Boolean)
    : [];

  return (
    <details className="trace">
      <summary>Что учтено в ответе</summary>
      <div className="trace-body">
        {profileParts.length > 0 && (
          <div>
            <span className="trace-label trace-label--profile mono">профиль</span>
            {profileParts.join('; ')}
          </div>
        )}
        <div>
          <span className="trace-label trace-label--short mono">краткосрочная</span>
          диалог в контексте: {used.history_count} сообщ.
        </div>
        {workingParts.length > 0 && (
          <div>
            <span className="trace-label trace-label--work mono">рабочая</span>
            {workingParts.join('; ')}
          </div>
        )}
        {longTermParts.length > 0 && (
          <div>
            <span className="trace-label trace-label--long mono">долговременная</span>
            {longTermParts.join('; ')}
          </div>
        )}
      </div>
    </details>
  );
}

export default function ChatPanel({
  error,
  loading,
  message,
  messages,
  onChange,
  onNewChat,
  onSubmit,
  overflow,
  result,
}) {
  const conversationRef = useRef(null);

  useEffect(() => {
    const element = conversationRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, loading]);

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  const blocked = loading || Boolean(overflow);
  const memory = result?.usage?.memory ?? null;

  return (
    <section className="chat">
      <div className="chat-head">
        <h2>Диалог</h2>
        <span className="model mono">{result?.model ?? 'deepseek-chat'}</span>
      </div>

      <div className="conversation" ref={conversationRef}>
        {!messages.length && !error && !overflow && !loading && (
          <div className="empty-state">
            <span className="empty-signature mono">
              профиль подключается к каждому ответу
            </span>
            <strong>Отвечу в вашем стиле</strong>
            Задайте вопрос: активный профиль задаст тон и формат, а память дня 11
            сохранит факты.
          </div>
        )}
        {messages.map((item, index) => (
          <div
            className={`turn ${item.role === 'user' ? 'turn--user' : 'turn--agent'}`}
            key={`${item.role}-${index}`}
          >
            <div className={`bubble ${item.role === 'user' ? '' : 'markdown'}`}>
              {item.role === 'user'
                ? item.content
                : <MarkdownMessage content={item.content} />}
            </div>
            {item.role === 'assistant' && item.used && <UsedMemory used={item.used} />}
          </div>
        ))}
        {loading && (
          <div className="turn turn--agent">
            <div className="bubble bubble--skeleton" role="status" aria-label="Ассистент готовит ответ">
              <span className="skeleton-line" style={{ width: '72%' }} />
              <span className="skeleton-line" style={{ width: '94%' }} />
              <span className="skeleton-line" style={{ width: '58%' }} />
            </div>
          </div>
        )}
        {error && (
          <div className="note note--error">
            <strong>Запрос не завершён</strong>
            {error}
          </div>
        )}
        {overflow && (
          <div className="note note--error">
            <strong>Контекст переполнен</strong>
            {overflow}
            <button className="btn" onClick={onNewChat} type="button">
              Начать новый чат
            </button>
          </div>
        )}
      </div>

      {result && !loading && (
        <div className="result-meta">
          <span className="mono"><b>модель</b> {result.model}</span>
          <span className="mono"><b>время</b> {(result.duration_ms / 1000).toFixed(1)} с</span>
          {memory && (
            <span className="mono">
              <b>профиль</b> {memory.profile_tokens ?? 0} · <b>память</b> долг.{' '}
              {memory.long_term_tokens} / рабоч. {memory.working_tokens} / истор.{' '}
              {memory.history_tokens}
            </span>
          )}
        </div>
      )}

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          aria-label="Сообщение для агента"
          disabled={blocked}
          onChange={event => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Сообщение. Команда «запомни: ...» сохраняет сразу."
          rows="2"
          value={message}
        />
        <button className="btn" disabled={blocked || !message.trim()} type="submit">
          {loading ? 'Думает…' : 'Отправить'}
        </button>
      </form>
      <p className="hint mono">Enter — отправить, Shift + Enter — новая строка</p>
    </section>
  );
}
