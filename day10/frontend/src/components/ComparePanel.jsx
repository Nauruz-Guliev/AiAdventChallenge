import { MODE_LABELS } from './ModeSelector.jsx';

function survivedCount(survived) {
  return Object.values(survived ?? {}).filter(Boolean).length;
}

function totalFacts(survived) {
  return Object.keys(survived ?? {}).length;
}

function scoreClass(survived) {
  const score = survivedCount(survived);
  const total = totalFacts(survived);
  if (score === total) return 'ok';
  if (score >= total - 1) return 'mid';
  return 'bad';
}

function bestMode(rows) {
  const alive = rows.filter(r => !r.error);
  if (!alive.length) return null;
  const maxSurvived = Math.max(...alive.map(r => survivedCount(r.survived)));
  const leaders = alive.filter(r => survivedCount(r.survived) === maxSurvived);
  const minTokens = Math.min(
    ...leaders.map(r => r.prompt_tokens + r.completion_tokens)
  );
  return leaders.find(r => r.prompt_tokens + r.completion_tokens === minTokens).mode;
}

function wallInfo(error) {
  const match = /(\d+)\/(\d+)/.exec(error ?? '');
  return match ? { used: match[1], limit: match[2] } : null;
}

export default function ComparePanel({ comparing, error, onOpenChat, onStart, rows }) {
  return (
    <section className="compare">
      <div className="panel-kicker">LAB · ОДИН СЦЕНАРИЙ «СОБИРАЕМ ТЗ» НА 4 РЕЖИМАХ</div>
      <button className="compare-start" disabled={comparing} onClick={onStart} type="button">
        {comparing
          ? '⏳ Прогоняю сценарий во всех режимах…'
          : '⚖ Сравнить стратегии'}
      </button>
      {error && <p className="compare-error">{error}</p>}
      {rows && !comparing && (
        <>
          <p className="compare-legend">
            11 обменов, 6 контрольных фактов вшиты в диалог; финальный вопрос —
            «собери ТЗ, назови кодовое имя и бюджет». Счёт = сколько фактов
            модель вернула в финале.
          </p>
          <table className="compare-table">
            <thead>
              <tr>
                <th>Режим</th>
                <th>Факты</th>
                <th>Потеряно</th>
                <th className="num">Вход</th>
                <th className="num">Ответ</th>
                <th className="num">Экстракция</th>
                <th className="num">Всего</th>
                <th className="num">Вызовы</th>
                <th className="num">Сек</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const best = bestMode(rows);
                return rows.map(row => {
                  const lost = Object.entries(row.survived ?? {})
                    .filter(([, ok]) => !ok)
                    .map(([label]) => label);
                  const wall = wallInfo(row.error);
                  return (
                    <tr
                      className={[
                        row.error ? 'row-error' : '',
                        row.mode === best ? 'row-best' : '',
                      ].join(' ').trim() || undefined}
                      key={row.mode}
                    >
                      <td>
                        <span className={`mode-chip mode-${row.mode}`}>
                          {MODE_LABELS[row.mode] ?? row.mode}
                        </span>
                        {row.mode === best && ' 🏆'}
                      </td>
                      {row.error ? (
                        <td colSpan="8">
                          {wall ? (
                            <span className="chip bad">
                              🧱 стена контекста {wall.used} / {wall.limit} —
                              даже полный диалог не влез в бюджет
                            </span>
                          ) : (
                            <span className="chip bad">✘ сбой: {row.error}</span>
                          )}
                        </td>
                      ) : (
                        <>
                          <td>
                            <span className={`chip score ${scoreClass(row.survived)}`}>
                              {survivedCount(row.survived)}/{totalFacts(row.survived)}
                            </span>
                          </td>
                          <td className="lost">
                            {lost.length ? lost.join(', ') : '—'}
                          </td>
                          <td className="num">{row.prompt_tokens}</td>
                          <td className="num">{row.completion_tokens}</td>
                          <td className="num">{row.fact_update_tokens || '—'}</td>
                          <td className="num">
                            <b>{row.prompt_tokens + row.completion_tokens + row.fact_update_tokens}</b>
                          </td>
                          <td className="num">{row.calls}</td>
                          <td className="num">{(row.duration_ms / 1000).toFixed(1)}</td>
                        </>
                      )}
                      <td>
                        <button onClick={() => onOpenChat(row.chat_id)} type="button">
                          открыть
                        </button>
                      </td>
                    </tr>
                  );
                });
              })()}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
