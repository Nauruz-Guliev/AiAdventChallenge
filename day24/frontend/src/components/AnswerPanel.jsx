import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function AnswerPanel({ title, answer }) {
  if (!answer) return null;
  const hasSources = answer.sources && answer.sources.length > 0;
  return (
    <article className="answer-panel">
      <h2>{title}</h2>
      <div className="answer-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.text}</ReactMarkdown>
      </div>
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
