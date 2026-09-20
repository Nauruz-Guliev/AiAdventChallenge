import { Fragment } from 'react';

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
  if (!state) return null;

  const active = Boolean(state.active);
  const paused = active && Boolean(state.paused);
  const finished = state.stage === 'done';
  const activeIndex = active ? state.stage_index ?? 0 : -1;

  return (
    <section className={`task${paused ? ' task--paused' : ''}`}>
      <div className="task-head">
        <div className="task-heading">
          <span className="task-label mono">задача</span>
          <h2>
            {active ? state.task || 'Без названия' : 'Задача ещё не задана'}
          </h2>
        </div>
        {active && (
          <div className="task-controls">
            {paused ? (
              <>
                <span className="task-paused mono">на паузе</span>
                <button
                  className="btn btn--commit"
                  disabled={disabled}
                  onClick={onResume}
                  type="button"
                >
                  ▶ Продолжить
                </button>
              </>
            ) : (
              <button
                className="btn"
                disabled={disabled || finished}
                onClick={onPause}
                type="button"
              >
                ⏸ Пауза
              </button>
            )}
          </div>
        )}
      </div>

      <ol className="task-steps">
        {STAGES.map((stage, index) => (
          <Fragment key={stage.key}>
            {index > 0 && <li className="task-arrow" aria-hidden="true" />}
            <li className={`task-stage ${stageClass(index, activeIndex)}`}>
              <span className="task-dot" aria-hidden="true">
                {index < activeIndex ? '✓' : ''}
              </span>
              <span className="task-stage-label">{stage.label}</span>
            </li>
          </Fragment>
        ))}
      </ol>

      <div className="task-meta">
        {active && state.total_steps > 0 && (
          <span className="mono task-count">
            шаг {state.step}/{state.total_steps}
          </span>
        )}
        {state.step_label && (
          <span className="task-step-label">{state.step_label}</span>
        )}
        <span className="task-expected">
          <span className="task-expected-arrow" aria-hidden="true">→</span>
          {state.expected_action}
        </span>
      </div>
    </section>
  );
}
