import { useState } from 'react';

function FactRow({ entryKey, value, onCommit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draftKey, setDraftKey] = useState(entryKey);
  const [draftValue, setDraftValue] = useState(value);

  if (!editing) {
    return (
      <li className="fact-row">
        <span className="fact-key">{entryKey}</span>
        <span className="fact-value">{value}</span>
        <button aria-label={`Изменить факт ${entryKey}`} className="fact-btn" onClick={() => setEditing(true)} type="button">✏</button>
        <button aria-label={`Удалить факт ${entryKey}`} className="fact-btn" onClick={() => onDelete(entryKey)} type="button">🗑</button>
      </li>
    );
  }
  return (
    <li className="fact-row editing">
      <input aria-label="ключ факта" onChange={event => setDraftKey(event.target.value)} value={draftKey} />
      <input aria-label="значение факта" onChange={event => setDraftValue(event.target.value)} value={draftValue} />
      <button
        className="fact-btn"
        onClick={() => {
          setEditing(false);
          onCommit(entryKey, draftKey.trim(), draftValue.trim());
        }}
        type="button"
      >
        ✓
      </button>
    </li>
  );
}

export default function FactsPanel({ facts, onChange, disabled }) {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const entries = Object.entries(facts ?? {});

  function commit(oldKey, key, value) {
    const next = { ...facts };
    delete next[oldKey];
    if (key) next[key] = value;
    onChange(next);
  }

  function add() {
    const key = newKey.trim();
    if (!key) return;
    onChange({ ...facts, [key]: newValue.trim() || '—' });
    setNewKey('');
    setNewValue('');
  }

  return (
    <div className="facts-panel">
      <div className="panel-kicker">FACTS · KV-память</div>
      <ul>
        {entries.map(([key, value]) => (
          <FactRow
            disabled={disabled}
            entryKey={key}
            key={key}
            onCommit={commit}
            onDelete={keyToDelete => commit(keyToDelete, '', '')}
            value={value}
          />
        ))}
        {!entries.length && <li className="fact-empty">Пока пусто — факты появятся из сообщений.</li>}
      </ul>
      <div className="fact-add">
        <input aria-label="новый ключ" onChange={event => setNewKey(event.target.value)} placeholder="ключ" value={newKey} />
        <input aria-label="новое значение" onChange={event => setNewValue(event.target.value)} placeholder="значение" value={newValue} />
        <button disabled={disabled || !newKey.trim()} onClick={add} type="button">+ добавить</button>
      </div>
    </div>
  );
}
