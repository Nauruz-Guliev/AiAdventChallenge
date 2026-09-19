import { useEffect, useRef } from 'react';

export default function ConfirmDialog({
  body,
  cancelLabel = 'Отмена',
  confirmLabel = 'Удалить',
  onCancel,
  onConfirm,
  open,
  title,
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    confirmRef.current?.focus();
    function handleKey(event) {
      if (event.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="overlay"
      onMouseDown={event => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div aria-labelledby="dialog-title" aria-modal="true" className="dialog" role="dialog">
        <h3 id="dialog-title">{title}</h3>
        {body && <p>{body}</p>}
        <div className="dialog-actions">
          <button className="btn" onClick={onCancel} type="button">
            {cancelLabel}
          </button>
          <button className="btn btn--danger" onClick={onConfirm} ref={confirmRef} type="button">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
