const statusLabels = {
  pending: 'Ожидание',
  active: 'Выполняется',
  completed: 'Готово',
  error: 'Ошибка',
};

export default function AgentFlow({ loading, stages }) {
  return (
    <aside className="flow-panel">
      <div className="panel-kicker">REQUEST FLOW</div>
      <div className="flow-heading-row">
        <h2>Как работает Agent</h2>
        <span className={loading ? 'live-tag live' : 'live-tag'}>
          {loading ? 'LIVE' : 'READY'}
        </span>
      </div>
      <p className="flow-description">
        Один запрос проходит через отдельные слои. Каждый слой знает только свою задачу.
      </p>

      <div className="flow-list">
        {stages.map((stage, index) => (
          <div className="flow-item" key={stage.name}>
            <div className={`flow-marker ${stage.status}`}>
              {stage.status === 'completed' ? '✓' : index + 1}
            </div>
            <div className="flow-item-copy">
              <strong>{stage.name}</strong>
              <span>{statusLabels[stage.status]}</span>
            </div>
            {index < stages.length - 1 && <div className={`flow-connector ${stage.status}`} />}
          </div>
        ))}
      </div>

      <div className="flow-note">
        <span className="note-mark">i</span>
        <p>Agent скрывает детали провайдера от интерфейса и возвращает только безопасный результат.</p>
      </div>
    </aside>
  );
}
