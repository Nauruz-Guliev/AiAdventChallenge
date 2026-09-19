import { useEffect, useRef } from 'react';
import MarkdownMessage from './MarkdownMessage.jsx';

function MemoryChip({ memory }) {
  if (!memory) return null;
  return (
    <div className="context-chip">
      память: долг. {memory.long_term_tokens} · рабоч. {memory.working_tokens} · истор. {memory.history_tokens}
      {memory.candidate_tokens ? ` · кандидаты ${memory.candidate_tokens}` : ''}
    </div>
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
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  const blocked = loading || Boolean(overflow);
  const conversationRef = useRef(null);

  useEffect(() => {
    const element = conversationRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, loading]);

  return (
    <section className="chat-panel">
      <div className="panel-kicker">CONVERSATION</div>
      <div className="chat-heading-row">
        <h2>Спроси агента</h2>
        <span className="model-chip">deepseek-chat</span>
      </div>

      <div
        className={`conversation ${messages.length || error || overflow ? 'has-response' : ''}`}
        ref={conversationRef}
      >
        {!messages.length && !error && !overflow && !loading && (
          <div className="empty-state">
            <span className="empty-icon">✦</span>
            <p>Агент готов. История этого чата<br />сохранится после перезапуска.</p>
          </div>
        )}
        {messages.map((item, index) => (
          <div
            className={`message-group ${item.role === 'user' ? 'user-group' : 'agent-group'}`}
            key={`${item.role}-${index}`}
          >
            <div className={`message ${item.role === 'user' ? 'user-message' : 'agent-message markdown'}`}>
              {item.role === 'user'
                ? item.content
                : <MarkdownMessage content={item.content} />}
            </div>
            {item.role === 'assistant' && <MemoryChip memory={item.memory} />}
          </div>
        ))}
        {loading && (
          <div className="message agent-message loading-message">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </div>
        )}
        {error && <div className="error-card"><strong>Запрос не завершён</strong><span>{error}</span></div>}
        {overflow && (
          <div className="error-card overflow-card">
            <strong>Лимит контекста превышен</strong>
            <span>{overflow}</span>
            <button className="overflow-new-chat" onClick={onNewChat} type="button">
              Начать новый чат
            </button>
          </div>
        )}
      </div>

      {result && !loading && (
        <div className="result-meta">
          <span><b>MODEL</b> {result.model}</span>
          <span><b>TIME</b> {result.duration_ms} ms</span>
        </div>
      )}

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          aria-label="Сообщение для агента"
          disabled={blocked}
          onChange={event => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Напиши сообщение... (или «запомни: ...»)"
          rows="2"
          value={message}
        />
        <button disabled={blocked || !message.trim()} type="submit">
          {loading ? 'Думает...' : 'Отправить'} <span>↗</span>
        </button>
      </form>
      <p className="composer-hint">Enter — отправить&nbsp;&nbsp;·&nbsp;&nbsp;Shift + Enter — новая строка</p>
    </section>
  );
}