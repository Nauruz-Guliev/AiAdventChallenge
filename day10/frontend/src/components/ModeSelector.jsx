export const MODES = [
  ['full', 'Полный'],
  ['sliding', 'Окно'],
  ['facts', 'Факты'],
  ['branching', 'Ветки'],
];

export const MODE_LABELS = Object.fromEntries(MODES);

export default function ModeSelector({ mode, onChange, disabled }) {
  return (
    <div className="mode-selector" role="radiogroup" aria-label="Режим контекста">
      {MODES.map(([value, label]) => (
        <button
          aria-checked={mode === value}
          className={mode === value ? 'mode active' : 'mode'}
          disabled={disabled}
          key={value}
          onClick={() => onChange(value)}
          role="radio"
          type="button"
        >
          {label}
        </button>
      ))}
    </div>
  );
}
