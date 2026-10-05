import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function AnswerPanel({ title, answer }) {
  if (!answer) return null;
  const hasSources = answer.sources && answer.sources.length > 0;
  const hasCitations = answer.citations && answer.citations.length > 0;
  return (
    <article className="answer-panel">
      <h2>{title}</h2>
      {answer.answerable === false && <div className="no-answer">Не знаю</div>}
      {typeof answer.relevance === 'number' && (
        <div className="relevance">релевантность: {answer.relevance.toFixed(3)}</div>
      )}
      <div className="answer-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.text}</ReactMarkdown>
      </div>
      {hasCitations && (
        <div className="citations">
          <h3>Цитаты ({answer.citations.length})</h3>
          <ul>
            {answer.citations.map((c) => (
              <li key={`${c.ref}-${c.chunk_id}`} className={c.grounded ? '' : 'ungrounded'}>
                <blockquote>{c.quote}</blockquote>
                <span className="cite-meta">
                  [{c.ref}] {c.source} :: {c.section} · {c.chunk_id}
                  {c.grounded ? '' : ' · не дословно'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasSources && (
        <div className="sources">
          <h3>Источники ({answer.sources.length})</h3>
          <ul>
            {answer.sources.map((source) => (
              <li key={source.chunk_id}>
                <span className="source-path">{source.source} :: {source.section}</span>
                <span className="source-score">{source.score.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
