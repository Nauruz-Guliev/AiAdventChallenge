import { Fragment } from 'react';

const STAGES = [
  { key: 'planning', label: 'планирование' },
  { key: 'approval', label: 'утверждение' },
  { key: 'execution', label: 'выполнение' },
  { key: 'validation', label: 'проверка' },
  { key: 'done', label: 'готово' },
];

const STAGE_LABELS = Object.fromEntries(
  STAGES.map(stage => [stage.key, stage.label]),
);

const COUNTED_STAGES = ['execution', 'validation', 'done'];

function stageClass(index, activeIndex) {
  if (index < activeIndex) return 'task-stage--done';
  if (index === activeIndex) return 'task-stage--active';
  return 'task-stage--todo';
}

export default function TaskStatePanel({
  state,
  disabled,
  onPause,
  onResume,
  onApprove,
}) {
  if (!state) return null;

  const active = Boolean(state.active);
  const paused = active && Boolean(state.paused);
  const finished = state.stage === 'done';
  const awaiting = active && state.stage === 'approval' && !paused;
  const activeIndex = active ? state.stage_index ?? 0 : -1;
  const allowed = (state.allowed_stages ?? []).map(
    key => STAGE_LABELS[key] ?? key,
  );
  const rejections = state.rejections ?? [];

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
              <>
                {awaiting && (
                  <button
                    className="btn btn--commit"
                    disabled={disabled}
                    onClick={onApprove}
                    type="button"
                  >
                    ✓ Утвердить план
                  </button>
                )}
                <button
                  className="btn"
                  disabled={disabled || finished}
                  onClick={onPause}
                  type="button"
                >
                  ⏸ Пауза
                </button>
              </>
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
        {active && state.total_steps > 0 && COUNTED_STAGES.includes(state.stage) && (
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
        {allowed.length > 0 && (
          <span className="task-allowed mono">
            доступно: {allowed.join(', ')}
          </span>
        )}
      </div>

      {rejections.length > 0 && (
        <ul className="task-rejections">
          {rejections.map((rejection, index) => (
            <li
              className="task-rejection"
              key={`${rejection.event}-${index}`}
            >
              <span className="task-rejection-badge mono">
                переход отклонён
              </span>
              <span>{rejection.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
