function List({ title, items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mem-group">
      <h4>{title}</h4>
      <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

export default function MemoryPanel({ memory }) {
  return (
    <div className="memory-panel">
      <div className="mem-goal">Цель: {memory.goal || '(не задана)'}</div>
      <List title="Уточнения" items={memory.clarifications} />
      <List title="Ограничения" items={memory.constraints} />
      <List title="Термины" items={memory.terms} />
    </div>
  );
}
