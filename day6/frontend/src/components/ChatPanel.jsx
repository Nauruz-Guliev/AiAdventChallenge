export default function ChatPanel({
  answer,
  error,
  loading,
  message,
  result,
  onChange,
  onSubmit,
}) {
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  return (
    <section className="chat-panel">
      <div className="panel-kicker">CONVERSATION</div>
      <div className="chat-heading-row">
        <h2>Спроси агента</h2>
        <span className="model-chip">deepseek-chat</span>
      </div>

      <div className={`conversation ${answer || error ? 'has-response' : ''}`}>
        {!message && !answer && !error && (
          <div className="empty-state">
            <span className="empty-icon">✦</span>
            <p>Агент готов. Начни с вопроса,<br />который хочется разобрать.</p>
          </div>
        )}
        {message && <div className="message user-message">{message}</div>}
        {loading && (
          <div className="message agent-message loading-message">
            <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
          </div>
        )}
        {answer && <div className="message agent-message">{answer}</div>}
        {error && <div className="error-card"><strong>Запрос не завершён</strong><span>{error}</span></div>}
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
          disabled={loading}
          onChange={event => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Напиши сообщение..."
          rows="2"
          value={message}
        />
        <button disabled={loading || !message.trim()} type="submit">
          {loading ? 'Думает...' : 'Отправить'} <span>↗</span>
        </button>
      </form>
      <p className="composer-hint">Enter — отправить&nbsp;&nbsp;·&nbsp;&nbsp;Shift + Enter — новая строка</p>
    </section>
  );
}
