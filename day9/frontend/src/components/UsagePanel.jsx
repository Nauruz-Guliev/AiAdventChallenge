export default function UsagePanel({ disabled, simulating, usage, onSimulate }) {
  if (!usage) return null;

  const used = usage.context_limit - usage.context_remaining;
  const percent = usage.context_limit
    ? Math.min(100, Math.round((used / usage.context_limit) * 100))
    : 0;
  const level = percent >= 100 ? 'danger' : usage.warning ? 'warning' : 'ok';

  return (
    <div className="usage-panel">
      <div className="usage-top">
        <div>
          <div className="panel-kicker">TOKEN BUDGET</div>
          <div className={`context-bar ${level}`} aria-label="Заполнение бюджета контекста" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
            <div className="context-bar-fill" style={{ width: `${percent}%` }} />
          </div>
          <small className="usage-caption">
            контекст ≈ {used} / {usage.context_limit} токенов ({percent}%) — локальная оценка
          </small>
        </div>
        <button
          className="simulate-button"
          disabled={disabled || simulating}
          onClick={onSimulate}
          type="button"
        >
          {simulating ? 'Симуляция…' : 'Симулировать длинный диалог'}
        </button>
      </div>
      <div className="usage-stats">
        <span><b>Σ ТОКЕНОВ</b> {usage.dialog_total_tokens}</span>
        <span><b>СТОИМОСТЬ</b> ≈ ${usage.dialog_cost_usd.toFixed(5)}</span>
        <span><b>ОСТАЛОСЬ</b> {usage.context_remaining}</span>
      </div>
      {usage.warning && (
        <p className="usage-warning">
          Бюджет контекста заполнен больше чем на 80% — следующее сообщение может не пройти.
        </p>
      )}
    </div>
  );
}
