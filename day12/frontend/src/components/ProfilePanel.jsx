import { useEffect, useState } from 'react';

const TONE_OPTIONS = [
  { value: 'formal', label: 'Деловой' },
  { value: 'friendly', label: 'Дружелюбный' },
  { value: 'neutral', label: 'Нейтральный' },
];
const LENGTH_OPTIONS = [
  { value: 'short', label: 'Коротко' },
  { value: 'medium', label: 'Средне' },
  { value: 'detailed', label: 'Подробно' },
];
const STRUCTURE_OPTIONS = [
  { value: 'prose', label: 'Текст' },
  { value: 'bullets', label: 'Списки' },
  { value: 'markdown', label: 'Markdown' },
];
const EMPTY_FORM = {
  title: '',
  name: '',
  role: '',
  language: 'ru',
  tone: 'neutral',
  length: 'medium',
  structure: 'prose',
  constraints: [],
};

function Segments({ label, options, value, disabled, onChange }) {
  return (
    <div className="seg-field">
      <span className="seg-label mono">{label}</span>
      <div className="seg" role="group" aria-label={label}>
        {options.map(option => (
          <button
            aria-checked={option.value === value}
            className="seg-item"
            disabled={disabled}
            key={option.value}
            onClick={() => onChange(option.value)}
            role="radio"
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ProfilePanel({
  activeProfile,
  disabled,
  onActivate,
  onCreateFromPreset,
  onDuplicate,
  onRequestDelete,
  onUpdate,
  presets,
  profiles,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [newConstraint, setNewConstraint] = useState('');

  useEffect(() => {
    setForm(activeProfile ? { ...EMPTY_FORM, ...activeProfile } : EMPTY_FORM);
    setNewConstraint('');
  }, [activeProfile?.id]);

  function patch(key, value) {
    setForm(current => ({ ...current, [key]: value }));
  }

  function addConstraint() {
    const text = newConstraint.trim();
    if (!text) return;
    patch('constraints', [...form.constraints, text]);
    setNewConstraint('');
  }

  const empty = !activeProfile;

  return (
    <section className="layer layer--profile">
      <div className="layer-head">
        <div className="layer-title">
          <h3>
            Профиль
            <span className="badge badge--profile mono">как отвечать</span>
          </h3>
          <span className="layer-sub">
            Персонализация подключается к каждому запросу автоматически
          </span>
        </div>
        <span className="meta mono">{profiles.length} профил.</span>
      </div>

      <div className="layer-body">
        <div className="profile-chips" role="group" aria-label="Выбор профиля">
          {profiles.map(profile => (
            <button
              className={`chip ${
                profile.id === activeProfile?.id ? 'chip--profile is-active' : ''
              }`}
              disabled={disabled}
              key={profile.id}
              onClick={() => onActivate(profile.id)}
              type="button"
            >
              {profile.title || 'Без названия'}
            </button>
          ))}
          {presets.map(preset => (
            <button
              className="chip chip--ghost"
              disabled={disabled}
              key={preset.key}
              onClick={() => onCreateFromPreset(preset.key)}
              type="button"
            >
              + {preset.label}
            </button>
          ))}
        </div>

        {!empty && (
          <>
            <label>
              Название профиля
              <input
                disabled={disabled}
                onChange={event => patch('title', event.target.value)}
                placeholder="Например: Для работы"
                value={form.title}
              />
            </label>
            <div className="profile-pair">
              <label>
                Имя
                <input
                  disabled={disabled}
                  onChange={event => patch('name', event.target.value)}
                  placeholder="Как к вам обращаться"
                  value={form.name}
                />
              </label>
              <label>
                Роль
                <input
                  disabled={disabled}
                  onChange={event => patch('role', event.target.value)}
                  placeholder="Например: разработчик"
                  value={form.role}
                />
              </label>
            </div>

            <Segments
              disabled={disabled}
              label="Стиль"
              onChange={value => patch('tone', value)}
              options={TONE_OPTIONS}
              value={form.tone}
            />
            <Segments
              disabled={disabled}
              label="Объём"
              onChange={value => patch('length', value)}
              options={LENGTH_OPTIONS}
              value={form.length}
            />
            <Segments
              disabled={disabled}
              label="Формат"
              onChange={value => patch('structure', value)}
              options={STRUCTURE_OPTIONS}
              value={form.structure}
            />

            <div className="seg-field">
              <span className="seg-label mono">Ограничения</span>
              <ul className="constraint-list">
                {form.constraints.map((item, index) => (
                  <li key={`${item}-${index}`}>
                    <span>{item}</span>
                    <button
                      aria-label={`Убрать «${item}»`}
                      className="entry-del"
                      disabled={disabled}
                      onClick={() =>
                        patch(
                          'constraints',
                          form.constraints.filter((_, i) => i !== index),
                        )
                      }
                      type="button"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
              <div className="add-row">
                <input
                  disabled={disabled}
                  onChange={event => setNewConstraint(event.target.value)}
                  onKeyDown={event => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addConstraint();
                    }
                  }}
                  placeholder="Например: без эмодзи"
                  value={newConstraint}
                />
                <button
                  className="btn btn--ghost"
                  disabled={disabled || !newConstraint.trim()}
                  onClick={addConstraint}
                  type="button"
                >
                  Добавить
                </button>
              </div>
            </div>

            <div className="row-actions">
              <button
                className="btn"
                disabled={disabled}
                onClick={() => onUpdate(activeProfile.id, form)}
                type="button"
              >
                Сохранить профиль
              </button>
              <button
                className="btn btn--ghost"
                disabled={disabled}
                onClick={() => onDuplicate(activeProfile)}
                type="button"
              >
                Дублировать
              </button>
              <button
                className="btn btn--ghost"
                disabled={disabled || profiles.length <= 1}
                onClick={() => onRequestDelete(activeProfile.id)}
                type="button"
              >
                Удалить
              </button>
            </div>
            <p className="layer-hint">
              Профиль меняет тон и формат каждого ответа. «Нейтральный» отключает
              персонализацию.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
