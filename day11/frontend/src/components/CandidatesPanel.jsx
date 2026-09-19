const CATEGORY_LABELS = {
  profile: 'Профиль',
  decisions: 'Решения',
  knowledge: 'Знания',
};

export default function CandidatesPanel({ candidates, disabled, onApprove, onReject }) {
  if (!candidates.length) return null;

  return (
    <section className="candidates-panel" aria-label="Кандидаты в память">
      <div className="panel-kicker">REMEMBER?</div>
      <h3>💾 Запомнить навсегда?</h3>
      <ul>
        {candidates.map(candidate => (
          <li key={candidate.id}>
            <span className="candidate-text">{candidate.text}</span>
            <span className="candidate-category">
              {CATEGORY_LABELS[candidate.category] ?? candidate.category}
            </span>
            <button
              disabled={disabled}
              onClick={() => onApprove(candidate.id)}
              type="button"
            >
              ✅
            </button>
            <button
              disabled={disabled}
              onClick={() => onReject(candidate.id)}
              type="button"
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}