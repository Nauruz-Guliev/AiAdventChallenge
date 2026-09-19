export default function SessionStrip({
  chats,
  disabled,
  onCreate,
  onDelete,
  onSelect,
  selectedChatId,
}) {
  return (
    <div className="sessions">
      <div className="chats">
        {chats.map(chat => (
          <span
            className={`chat-tab ${chat.id === selectedChatId ? 'selected' : ''}`}
            key={chat.id}
          >
            <button
              disabled={disabled}
              onClick={() => onSelect(chat.id)}
              title={chat.title}
              type="button"
            >
              {chat.title || 'Новый чат'}
            </button>
            <button
              aria-label={`Удалить чат «${chat.title}»`}
              className="tab-del"
              disabled={disabled}
              onClick={() => onDelete(chat.id)}
              type="button"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <button className="btn" disabled={disabled} onClick={onCreate} type="button">
        Новый чат
      </button>
    </div>
  );
}
