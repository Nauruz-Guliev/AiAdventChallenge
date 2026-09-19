const CATEGORIES = [
  { value: 'profile', label: 'Профиль' },
  { value: 'decisions', label: 'Решения' },
  { value: 'knowledge', label: 'Знания' },
];

export default function CategoryPicker({ disabled, label = 'Категория', onChange, value }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {CATEGORIES.map(item => (
        <button
          aria-checked={value === item.value}
          className="seg-item"
          disabled={disabled}
          key={item.value}
          onClick={() => onChange(item.value)}
          role="radio"
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
