const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function CandidateTray({ candidates, disabled, onApprove, onReject }) {
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
          {candidates.map(candidate => (
            <li className="candidate" key={candidate.id}>
              <span className="candidate-text">{candidate.text}</span>
              <div className="candidate-foot">
                <span className="candidate-cat">
                  {CATEGORY_LABELS[candidate.category] ?? candidate.category}
                </span>
                <button
                  className="btn btn--commit"
                  disabled={disabled}
                  onClick={() => onApprove(candidate.id)}
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
          ))}
        </ul>
      ) : (
        <p className="empty">Ассистент предложит запомнить — решение за вами.</p>
      )}
    </section>
  );
}
