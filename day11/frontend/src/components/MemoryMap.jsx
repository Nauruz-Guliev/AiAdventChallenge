import { useEffect, useState } from 'react';
import CandidateTray from './CandidateTray.jsx';

const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

function sourceLabel(chats, sourceChatId) {
  if (!sourceChatId) return 'добавлено вручную';
  const chat = chats.find(item => item.id === sourceChatId);
  return chat ? `из чата «${chat.title}»` : 'из чата';
}

function shortDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('ru-RU');
}

export default function MemoryMap({
  candidates,
  chats,
  disabled,
  longTerm,
  messageCount,
  onAddEntry,
  onApprove,
  onClearHistory,
  onCompleteWorking,
  onDeleteEntry,
  onReject,
  onResetWorking,
  onSaveWorking,
  recent,
  working,
}) {
  const [goal, setGoal] = useState(working?.goal ?? '');
  const [constraints, setConstraints] = useState((working?.constraints ?? []).join('\n'));
  const [decisions, setDecisions] = useState((working?.decisions ?? []).join('\n'));
  const [newEntry, setNewEntry] = useState({ category: 'knowledge', text: '' });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setGoal(working?.goal ?? '');
    setConstraints((working?.constraints ?? []).join('\n'));
    setDecisions((working?.decisions ?? []).join('\n'));
  }, [working]);

  const dirty =
    goal !== (working?.goal ?? '') ||
    constraints !== (working?.constraints ?? []).join('\n') ||
    decisions !== (working?.decisions ?? []).join('\n');

  async function submitWorking(event) {
    event.preventDefault();
    const ok = await onSaveWorking({
      goal,
      constraints: constraints.split('\n').map(item => item.trim()).filter(Boolean),
      decisions: decisions.split('\n').map(item => item.trim()).filter(Boolean),
      status: working?.status ?? 'active',
    });
    if (ok) {
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    }
  }

  const total = longTerm
    ? longTerm.profile.length + longTerm.decisions.length + longTerm.knowledge.length
    : 0;

  return (
    <aside className="map" aria-label="Память ассистента">
      <div className="map-head">
        <h2>Разрез памяти</h2>
        <span>Сверху — то, что живёт один чат. Снизу — то, что остаётся навсегда.</span>
      </div>

      <section className="layer layer--short">
        <div className="layer-head">
          <h3>Краткосрочная</h3>
          <span className="meta mono">{messageCount} сообщ.</span>
        </div>
        <div className="layer-body">
          {recent.length ? (
            <ul className="tape">
              {recent.map((item, index) => (
                <li key={`${item.role}-${index}`}>
                  <span className="who mono">{item.role === 'user' ? 'вы' : 'агент'}</span>
                  <span className="line">{item.content}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty">Диалог начнётся с первого сообщения.</p>
          )}
          <button
            className="btn btn--ghost"
            disabled={disabled}
            onClick={onClearHistory}
            type="button"
          >
            Очистить историю
          </button>
        </div>
      </section>

      <section className="layer layer--work">
        <div className="layer-head">
          <h3>Рабочая</h3>
          <span className="meta mono">
            {working?.status === 'done' ? 'завершена' : 'активна'}
          </span>
        </div>
        <div className="layer-body">
          <form className="working-form" onSubmit={submitWorking}>
            <label>
              Цель задачи
              <input
                disabled={disabled}
                onChange={event => setGoal(event.target.value)}
                placeholder="Например: уложиться в бюджет"
                value={goal}
              />
            </label>
            <label>
              Ограничения — по строке
              <textarea
                disabled={disabled}
                onChange={event => setConstraints(event.target.value)}
                placeholder="не дороже 500"
                rows="2"
                value={constraints}
              />
            </label>
            <label>
              Решения — по строке
              <textarea
                disabled={disabled}
                onChange={event => setDecisions(event.target.value)}
                placeholder="выбрали поставщика А"
                rows="2"
                value={decisions}
              />
            </label>
            <div className="row-actions">
              <button className="btn" disabled={disabled} type="submit">
                Сохранить
              </button>
              {dirty && <span className="save-state mono">есть изменения</span>}
              {!dirty && saved && <span className="save-state saved mono">сохранено</span>}
              <button
                className="btn"
                disabled={disabled}
                onClick={onCompleteWorking}
                type="button"
              >
                Завершить
              </button>
              <button
                className="btn btn--ghost"
                disabled={disabled}
                onClick={onResetWorking}
                type="button"
              >
                Новая задача
              </button>
            </div>
            <p className="layer-hint">
              Ассистент видит карточку в каждом ответе, пока задача активна.
              «Завершить» отключает влияние.
            </p>
          </form>
        </div>
      </section>

      <CandidateTray
        candidates={candidates}
        disabled={disabled}
        onApprove={onApprove}
        onReject={onReject}
      />

      <section className="layer layer--long">
        <div className="layer-head">
          <h3>Долговременная</h3>
          <span className="meta mono">{total} записей</span>
        </div>
        <div className="layer-body">
          <div className="drawers">
            {['profile', 'decisions', 'knowledge'].map(category => (
              <div className="drawer" key={category}>
                <div className="drawer-title mono">{CATEGORY_LABELS[category]}</div>
                <ul>
                  {(longTerm?.[category] ?? []).map(entry => (
                    <li className="entry" key={entry.id}>
                      <span className="entry-text">
                        {entry.text}
                        <span className="entry-prov mono">
                          {[
                            sourceLabel(chats, entry.source_chat_id),
                            shortDate(entry.created_at),
                          ]
                            .filter(Boolean)
                            .join(', ')}
                        </span>
                      </span>
                      <button
                        aria-label={`Удалить «${entry.text}»`}
                        className="entry-del"
                        disabled={disabled}
                        onClick={() => onDeleteEntry(category, entry.id)}
                        type="button"
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="add-row">
            <select
              aria-label="Категория новой записи"
              disabled={disabled}
              onChange={event =>
                setNewEntry(current => ({ ...current, category: event.target.value }))
              }
              value={newEntry.category}
            >
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <input
              disabled={disabled}
              onChange={event =>
                setNewEntry(current => ({ ...current, text: event.target.value }))
              }
              placeholder="Добавить в память"
              value={newEntry.text}
            />
            <button
              className="btn"
              disabled={disabled || !newEntry.text.trim()}
              onClick={async () => {
                const saved = await onAddEntry(newEntry);
                if (saved) setNewEntry(current => ({ ...current, text: '' }));
              }}
              type="button"
            >
              Добавить
            </button>
          </div>
        </div>
      </section>
    </aside>
  );
}
