import { modeLabel } from '../modeLabels.js';

export default function CompareTable({ report }) {
  const { items, summary } = report;
  const modes = Object.keys(summary.modes || {});
  return (
    <div className="compare">
      <div className="summary">
        {modes.map((mode) => {
          const m = summary.modes[mode];
          return (
            <div key={mode}>
              <span>{modeLabel(mode)}</span>
              <b>{m.avg_score}</b>
              <small className="muted">покрытие {m.source_coverage_rate}</small>
              <small className="muted">цитаты {m.citation_rate}</small>
              <small className="muted">grounding {m.avg_grounding}</small>
              <small className="muted">support {m.avg_support}</small>
              <small className="muted">не знаю {m.no_answer_rate}</small>
            </div>
          );
        })}
      </div>
      <table>
        <thead>
          <tr>
            <th>Вопрос</th>
            {modes.map((mode) => <th key={mode}>{modeLabel(mode)}</th>)}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.question}>
              <td>{item.question}</td>
              {modes.map((mode) => {
                const score = item.mode_scores[mode] ?? 0;
                const cited = item.has_citations[mode] ? '✓' : '';
                const cover = item.source_coverage[mode] ? '✅' : '❌';
                return (
                  <td key={mode} className={score >= 0.5 ? 'good' : 'bad'}>
                    {score} {cover} {cited}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
