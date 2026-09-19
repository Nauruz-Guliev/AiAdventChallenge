import { useEffect, useRef } from 'react';
import FactsPanel from './FactsPanel.jsx';
import MarkdownMessage from './MarkdownMessage.jsx';
import ModeSelector, { MODE_LABELS } from './ModeSelector.jsx';
import UsagePanel from './UsagePanel.jsx';

function ContextChip({ context }) {
  const sent = context.sent_messages;
  const total = context.total_messages;
  let text;
  if (context.mode === 'sliding') text = `окно: ${sent} из ${total}`;
  else if (context.mode === 'facts') {
    const extract = context.fact_update_tokens
      ? ` · экстракция ${context.fact_update_tokens} токенов`
      : '';
    text = `факты: ${context.facts_count} + ${sent} сообщений${extract}`;
  } else if (context.mode === 'branching') text = `ветка: ${total} сообщений`;
  else text = `полный контекст: ${total}`;
  return <div className="context-chip">{text}</div>;
}

function UsageLine({ usage }) {
  if (!usage) return null;
  if (usage.request_tokens != null) {
    return (
      <div className="usage-line">
        запрос {usage.request_tokens} · история ≈{usage.history_tokens} (оценка) · ответ {usage.completion_tokens} · всего {usage.total_tokens} токенов
      </div>
    );
  }
  return (
    <div className="usage-line">
      промпт {usage.prompt_tokens} · ответ {usage.completion_tokens} · всего {usage.total_tokens} токенов (API)
    </div>
  );
}

export default function ChatPanel({
  activeBranchId,
  branches,
  dialogUsage,
  facts,
  mode,
  error,
  loading,
  message,
  messages,
  onChange,
  onNewChat,
  onSimulate,
  onFactsChange,
  onFork,
  onModeChange,
  onSubmit,
  onDeleteBranch,
  onSwitchBranch,
  overflow,
  result,
  simulating,
}) {
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  const blocked = loading || simulating || Boolean(overflow);
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
        <span className={`mode-chip mode-${mode}`}>{MODE_LABELS[mode] ?? mode}</span>
        <span className="model-chip">deepseek-chat</span>
      </div>

      <UsagePanel
        disabled={loading || simulating}
        simulating={simulating}
        usage={dialogUsage}
        onSimulate={onSimulate}
      />

      {mode === 'branching' && branches.length > 0 && (
        <div className="branch-tabs">
          {branches.map(branch => (
            <span className={branch.id === activeBranchId ? 'tab active' : 'tab'} key={branch.id}>
              <button disabled={blocked} onClick={() => onSwitchBranch(branch.id)} type="button">
                {branch.name}
                {branch.fork_at != null ? ` @${branch.fork_at}` : ''}
              </button>
              {branches.length > 1 && (
                <button
                  aria-label={`Удалить ветку ${branch.name}`}
                  className="tab-close"
                  disabled={blocked}
                  onClick={() => onDeleteBranch(branch.id)}
                  type="button"
                >
                  ✕
                </button>
              )}
            </span>
          ))}
        </div>
      )}

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
            {item.role === 'assistant' && <UsageLine usage={item.usage} />}
            {item.role === 'assistant' && item.context && <ContextChip context={item.context} />}
            {item.role === 'assistant' && mode === 'branching' && (
              <button className="fork-button" disabled={blocked} onClick={() => onFork(index)} type="button">
                🌿 Ветвиться отсюда
              </button>
            )}
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
          placeholder={overflow ? 'Лимит — смените режим на «Окно»/«Факты» или начните новый чат' : 'Напиши сообщение...'}
          rows="2"
          value={message}
        />
        <button disabled={blocked || !message.trim()} type="submit">
          {loading ? 'Думает...' : 'Отправить'} <span>↗</span>
        </button>
      </form>
      <ModeSelector disabled={loading || simulating} mode={mode} onChange={onModeChange} />
      {mode === 'facts' && (
        <FactsPanel disabled={loading || simulating} facts={facts ?? {}} onChange={onFactsChange} />
      )}
      <p className="composer-hint">Enter — отправить&nbsp;&nbsp;·&nbsp;&nbsp;Shift + Enter — новая строка</p>
    </section>
  );
}
