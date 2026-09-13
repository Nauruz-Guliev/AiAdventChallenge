export default function ChatSidebar({
  chats,
  selectedChatId,
  onSelect,
  onCreate,
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
          <button
            aria-current={chat.id === selectedChatId ? 'true' : undefined}
            className={`chat-list-item ${chat.id === selectedChatId ? 'selected' : ''}`}
            disabled={disabled}
            key={chat.id}
            onClick={() => onSelect(chat.id)}
            type="button"
          >
            <span className="chat-list-dot" />
            <span className="chat-list-copy">
              <strong>{chat.title}</strong>
              <small>{new Date(chat.updated_at).toLocaleDateString('ru-RU')}</small>
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
