const STAGES = [
  { key: 'planning', label: 'планирование' },
  { key: 'execution', label: 'выполнение' },
  { key: 'validation', label: 'проверка' },
  { key: 'done', label: 'готово' },
];

function stageClass(index, activeIndex) {
  if (index < activeIndex) return 'task-stage--done';
  if (index === activeIndex) return 'task-stage--active';
  return 'task-stage--todo';
}

export default function TaskStatePanel({ state, disabled, onPause, onResume }) {
  if (!state?.active) return null;
  const activeIndex = state.stage_index ?? 0;

  return (
    <section className={`task${state.paused ? ' task--paused' : ''}`}>
      <div className="task-head">
        <div className="task-heading">
          <span className="task-label mono">состояние задачи</span>
          <h2>{state.task || 'Без названия'}</h2>
        </div>
        <div className="task-controls">
          {state.paused ? (
            <>
              <span className="task-paused mono">на паузе</span>
              <button className="btn" disabled={disabled} onClick={onResume} type="button">
                ▶ Продолжить
              </button>
            </>
          ) : (
            <button
              className="btn"
              disabled={disabled || state.stage === 'done'}
              onClick={onPause}
              type="button"
            >
              ⏸ Пауза
            </button>
          )}
        </div>
      </div>

      <ol className="task-steps">
        {STAGES.map((stage, index) => (
          <li className={`task-stage ${stageClass(index, activeIndex)}`} key={stage.key}>
            <span className="task-dot" aria-hidden="true" />
            <span className="task-stage-label">{stage.label}</span>
          </li>
        ))}
      </ol>

      <div className="task-meta">
        <span className="mono">
          шаг {state.step}/{state.total_steps}
        </span>
        {state.step_label && <span className="task-step-label">{state.step_label}</span>}
        <span className="task-expected">{state.expected_action}</span>
      </div>
    </section>
  );
}
