import { useState } from 'react';

const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function CandidateTray({ candidates, disabled, onApprove, onReject }) {
  const [drafts, setDrafts] = useState({});

  function draftFor(candidate) {
    return { text: candidate.text, category: candidate.category, ...(drafts[candidate.id] ?? {}) };
  }

  function update(id, patch) {
    setDrafts(current => ({ ...current, [id]: { ...(current[id] ?? {}), ...patch } }));
  }

  return (
    <section className="threshold" aria-label="Кандидаты в память">
      <div className="threshold-head">
        <h3>На пороге</h3>
        <span className="mono">
          {candidates.length ? `${candidates.length} к решению` : 'пока пусто'}
        </span>
      </div>
      {candidates.length ? (
        <ul className="candidates">
          {candidates.map(candidate => {
            const draft = draftFor(candidate);
            return (
              <li className="candidate" key={candidate.id}>
                <input
                  aria-label="Текст записи"
                  className="candidate-edit"
                  disabled={disabled}
                  onChange={event => update(candidate.id, { text: event.target.value })}
                  value={draft.text}
                />
                <div className="candidate-foot">
                  <select
                    aria-label="Куда сохранить"
                    className="candidate-cat"
                    disabled={disabled}
                    onChange={event =>
                      update(candidate.id, { category: event.target.value })
                    }
                    value={draft.category}
                  >
                    {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn--commit"
                    disabled={disabled || !draft.text.trim()}
                    onClick={() => onApprove(candidate.id, draft)}
                    type="button"
                  >
                    Запомнить
                  </button>
                  <button
                    className="btn btn--ghost"
                    disabled={disabled}
                    onClick={() => onReject(candidate.id)}
                    type="button"
                  >
                    Не надо
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="empty">Ассистент предложит запомнить — решение за вами.</p>
      )}
    </section>
  );
}
