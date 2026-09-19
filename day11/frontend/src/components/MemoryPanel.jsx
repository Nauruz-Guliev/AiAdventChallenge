import { useEffect, useState } from 'react';

const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function MemoryPanel({
  disabled,
  longTerm,
  messageCount,
  onAddEntry,
  onClearHistory,
  onCompleteWorking,
  onDeleteEntry,
  onResetWorking,
  onSaveWorking,
  working,
}) {
  const [goal, setGoal] = useState(working?.goal ?? '');
  const [constraints, setConstraints] = useState(
    (working?.constraints ?? []).join('\n')
  );
  const [decisions, setDecisions] = useState(
    (working?.decisions ?? []).join('\n')
  );
  const [newEntry, setNewEntry] = useState({ category: 'knowledge', text: '' });

  useEffect(() => {
    setGoal(working?.goal ?? '');
    setConstraints((working?.constraints ?? []).join('\n'));
    setDecisions((working?.decisions ?? []).join('\n'));
  }, [working]);

  function submitWorking(event) {
    event.preventDefault();
    onSaveWorking({
      goal,
      constraints: constraints.split('\n').map(item => item.trim()).filter(Boolean),
      decisions: decisions.split('\n').map(item => item.trim()).filter(Boolean),
      status: working?.status ?? 'active',
    });
  }

  return (
    <aside className="memory-panel" aria-label="Память ассистента">
      <div className="panel-kicker">MEMORY</div>
      <h2>Память ассистента</h2>

      <section className="memory-layer">
        <h3>Краткосрочная <span>{messageCount} сообщ.</span></h3>
        <button disabled={disabled} onClick={onClearHistory} type="button">
          Очистить историю
        </button>
      </section>

      <section className="memory-layer">
        <h3>Рабочая <span>{working?.status === 'done' ? 'завершена' : 'активна'}</span></h3>
        <form className="working-form" onSubmit={submitWorking}>
          <input
            disabled={disabled}
            onChange={event => setGoal(event.target.value)}
            placeholder="Цель задачи"
            value={goal}
          />
          <textarea
            disabled={disabled}
            onChange={event => setConstraints(event.target.value)}
            placeholder="Ограничения (по строке)"
            rows="2"
            value={constraints}
          />
          <textarea
            disabled={disabled}
            onChange={event => setDecisions(event.target.value)}
            placeholder="Решения (по строке)"
            rows="2"
            value={decisions}
          />
          <div className="working-actions">
            <button disabled={disabled} type="submit">Сохранить</button>
            <button disabled={disabled} onClick={onCompleteWorking} type="button">
              Завершить задачу
            </button>
            <button disabled={disabled} onClick={onResetWorking} type="button">
              Новая задача
            </button>
          </div>
        </form>
      </section>

      <section className="memory-layer">
        <h3>Долговременная <span>{longTerm ? longTerm.profile.length + longTerm.decisions.length + longTerm.knowledge.length : 0}</span></h3>
        {['profile', 'decisions', 'knowledge'].map(category => (
          <div className="longterm-category" key={category}>
            <strong>{CATEGORY_LABELS[category]}</strong>
            <ul>
              {(longTerm?.[category] ?? []).map(entry => (
                <li key={entry.id}>
                  <span>{entry.text}</span>
                  <button
                    aria-label={`Удалить ${entry.text}`}
                    disabled={disabled}
                    onClick={() => onDeleteEntry(category, entry.id)}
                    type="button"
                  >
                    🗑
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="longterm-add">
          <select
            disabled={disabled}
            onChange={event =>
              setNewEntry(current => ({ ...current, category: event.target.value }))
            }
            value={newEntry.category}
          >
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
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
            disabled={disabled || !newEntry.text.trim()}
            onClick={() => {
              onAddEntry(newEntry);
              setNewEntry(current => ({ ...current, text: '' }));
            }}
            type="button"
          >
            +
          </button>
        </div>
      </section>
    </aside>
  );
}