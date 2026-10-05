export default function Chat({ messages }) {
  return (
    <div className="chat">
      {messages.map((m, i) => (
        <div key={i} className={`msg ${m.role}`}>
          <div className="msg-text">{m.text}</div>
          {m.sources && m.sources.length > 0 && (
            <div className="msg-sources">
              <span className="src-label">Источники:</span>
              {m.sources.map((s) => (
                <span key={s.chunk_id} className="src-tag">
                  {s.source} :: {s.section} · {s.score.toFixed(2)}
                </span>
              ))}
            </div>
          )}
          {m.citations && m.citations.length > 0 && (
            <div className="msg-citations">
              {m.citations.map((c) => (
                <blockquote key={c.ref} className={c.grounded ? '' : 'ungrounded'}>
                  «{c.quote}» <span className="cite-meta">[{c.ref}] {c.source} :: {c.section}</span>
                </blockquote>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
