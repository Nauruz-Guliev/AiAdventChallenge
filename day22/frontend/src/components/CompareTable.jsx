export default function CompareTable({ report }) {
  const { items, summary } = report;
  return (
    <div className="compare">
      <div className="summary">
        <div><span>Средний балл без RAG</span><b>{summary.avg_no_rag_score}</b></div>
        <div><span>Средний балл с RAG</span><b>{summary.avg_rag_score}</b></div>
        <div><span>Покрытие источников</span><b>{summary.source_coverage_rate}</b></div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Вопрос</th>
            <th>Без RAG</th>
            <th>С RAG</th>
            <th>Источники</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.question}>
              <td>{item.question}</td>
              <td className={item.no_rag_score >= 0.5 ? 'good' : 'bad'}>{item.no_rag_score}</td>
              <td className={item.rag_score >= 0.5 ? 'good' : 'bad'}>{item.rag_score}</td>
              <td>
                {item.source_coverage ? '✅' : '❌'}{' '}
                <span className="muted">{item.rag_sources.join('; ')}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
