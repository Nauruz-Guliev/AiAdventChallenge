import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function AnswerPanel({ title, answer }) {
  return (
    <article className="answer-panel">
      <h2>{title}</h2>
      <div className="answer-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.text}</ReactMarkdown>
      </div>
      {answer.mode === 'rag' && (
        <div className="sources">
          <h3>Источники</h3>
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
