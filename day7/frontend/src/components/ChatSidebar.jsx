export default function ChatSidebar({
  chats,
  selectedChatId,
  onSelect,
  onCreate,
  onDelete,
  disabled,
}) {
  return (
    <aside className="chat-sidebar" aria-label="Сохранённые чаты">
      <div className="sidebar-heading">
        <div>
          <div className="panel-kicker">ARCHIVE</div>
          <h2>Мои чаты</h2>
        </div>
        <button className="new-chat-button" disabled={disabled} onClick={onCreate} type="button">
          +
        </button>
      </div>

      <div className="chat-list">
        {chats.map(chat => (
          <div
            className={`chat-list-item ${chat.id === selectedChatId ? 'selected' : ''}`}
            key={chat.id}
          >
            <button
              aria-current={chat.id === selectedChatId ? 'true' : undefined}
              className="chat-list-select"
              disabled={disabled}
              onClick={() => onSelect(chat.id)}
              title={chat.title}
              type="button"
            >
              <span className="chat-list-dot" />
              <span className="chat-list-copy">
                <strong>{chat.title}</strong>
                <small>{new Date(chat.updated_at).toLocaleDateString('ru-RU')}</small>
              </span>
            </button>
            <button
              aria-label={`Удалить чат: ${chat.title}`}
              className="delete-chat-button"
              disabled={disabled}
              onClick={() => onDelete(chat.id)}
              title="Удалить чат"
              type="button"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
