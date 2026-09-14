import { MODE_LABELS } from './ModeSelector.jsx';

function survivedCount(survived) {
  return Object.values(survived ?? {}).filter(Boolean).length;
}

function bestMode(rows) {
  const alive = rows.filter(r => !r.error);
  if (!alive.length) return null;
  const maxSurvived = Math.max(...alive.map(r => survivedCount(r.survived)));
  const leaders = alive.filter(r => survivedCount(r.survived) === maxSurvived);
  const minTokens = Math.min(
    ...leaders.map(r => r.prompt_tokens + r.completion_tokens)
  );
  return leaders.find(
    r => r.prompt_tokens + r.completion_tokens === minTokens
  ).mode;
}

export default function ComparePanel({ comparing, error, onOpenChat, onStart, rows }) {
  return (
    <section className="compare">
      <div className="panel-kicker">LAB · ОДИН СЦЕНАРИЙ «СОБИРАЕМ ТЗ» НА 4 РЕЖИМАХ</div>
      <button className="compare-start" disabled={comparing} onClick={onStart} type="button">
        {comparing
          ? '⏳ Прогоняю сценарий во всех режимах (1–3 минуты)…'
          : '⚖ Сравнить стратегии'}
      </button>
      {error && <p className="compare-error">{error}</p>}
      {rows && !comparing && (
        <table className="compare-table">
          <thead>
            <tr>
              <th>Режим</th>
              <th>Контрольные факты в финальном ТЗ</th>
              <th>Токены</th>
              <th>Вызовы</th>
              <th>Сек</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const best = bestMode(rows);
              return rows.map(row => (
              <tr className={[row.error ? 'row-error' : '', row.mode === best ? 'row-best' : ''].join(' ').trim() || undefined} key={row.mode}>
                <td><span className={`mode-chip mode-${row.mode}`}>{MODE_LABELS[row.mode] ?? row.mode}</span>{row.mode === best && ' 🏆'}</td>
                <td>
                  {row.error ? (
                    <span className="chip bad">✘ сбой: {row.error}</span>
                  ) : (
                    <>
                      {Object.entries(row.survived).map(([label, ok]) => (
                        <span className={ok ? 'chip ok' : 'chip bad'} key={label}>
                          {ok ? '✔' : '✘'} {label}
                        </span>
                      ))}
                      <span className="chip score">
                        {survivedCount(row.survived)}/{Object.keys(row.survived).length}
                      </span>
                    </>
                  )}
                </td>
                <td>{row.prompt_tokens + row.completion_tokens}</td>
                <td>{row.calls}</td>
                <td>{(row.duration_ms / 1000).toFixed(1)}</td>
                <td>
                  <button onClick={() => onOpenChat(row.chat_id)} type="button">открыть</button>
                </td>
              </tr>
              ));
            })()}
          </tbody>
        </table>
      )}
    </section>
  );
}
