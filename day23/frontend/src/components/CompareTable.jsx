import { modeLabel } from '../modeLabels.js';

export default function CompareTable({ report }) {
  const { items, summary } = report;
  const modes = Object.keys(summary.modes || {});
  return (
    <div className="compare">
      <div className="summary">
        {modes.map((mode) => (
          <div key={mode}>
            <span>{modeLabel(mode)}</span>
            <b>{summary.modes[mode].avg_score}</b>
            <small className="muted">покрытие {summary.modes[mode].source_coverage_rate}</small>
          </div>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>Вопрос</th>
            {modes.map((mode) => (
              <th key={mode}>{modeLabel(mode)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.question}>
              <td>{item.question}</td>
              {modes.map((mode) => (
                <td
                  key={mode}
                  className={(item.mode_scores[mode] ?? 0) >= 0.5 ? 'good' : 'bad'}
                >
                  {item.mode_scores[mode]} {item.source_coverage[mode] ? '✅' : '❌'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
