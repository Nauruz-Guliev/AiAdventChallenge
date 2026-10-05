import { useState } from 'react';

export default function QuestionInput({ onSubmit, disabled }) {
  const [value, setValue] = useState('');

  function handleSubmit(event) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue('');
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Например: как работают expect и actual declarations?"
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()}>Спросить</button>
    </form>
  );
}
