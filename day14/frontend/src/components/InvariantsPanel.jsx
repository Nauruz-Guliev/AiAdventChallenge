import { useState } from 'react';

const CATEGORIES = [
  { key: 'architecture', label: 'архитектура' },
  { key: 'decision', label: 'технические решения' },
  { key: 'stack', label: 'ограничения стека' },
  { key: 'business', label: 'бизнес-правила' },
];

export default function InvariantsPanel({
  invariants,
  disabled,
  onAdd,
  onDelete,
}) {
  const [text, setText] = useState('');
  const [category, setCategory] = useState('stack');

  async function handleSubmit(event) {
    event.preventDefault();
    if (!text.trim()) return;
    const saved = await onAdd({ text: text.trim(), category });
    if (saved) setText('');
  }

  return (
    <section className="inv">
      <div className="inv-head">
        <div className="inv-heading">
          <span className="inv-label mono">инварианты</span>
          <h2>Ограничения, которые ассистент не нарушает</h2>
        </div>
        <span className="inv-count mono">{invariants.length}</span>
      </div>

      <ul className="inv-list">
        {invariants.map(item => (
          <li className="inv-item" key={item.id}>
            <span className="inv-cat mono">{item.category_label}</span>
            <span className="inv-text">{item.text}</span>
            <button
              aria-label="Удалить инвариант"
              className="inv-del"
              disabled={disabled}
              onClick={() => onDelete(item.id)}
              type="button"
            >
              ×
            </button>
          </li>
        ))}
        {!invariants.length && (
          <li className="inv-empty">
            Инвариантов нет — ассистент ничем не ограничен.
          </li>
        )}
      </ul>

      <form className="inv-add" onSubmit={handleSubmit}>
        <input
          aria-label="Новый инвариант"
          disabled={disabled}
          onChange={event => setText(event.target.value)}
          placeholder="Например: только Python, без новых зависимостей"
          value={text}
        />
        <select
          aria-label="Категория инварианта"
          disabled={disabled}
          onChange={event => setCategory(event.target.value)}
          value={category}
        >
          {CATEGORIES.map(item => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
        <button
          className="btn"
          disabled={disabled || !text.trim()}
          type="submit"
        >
          Добавить
        </button>
      </form>
    </section>
  );
}
