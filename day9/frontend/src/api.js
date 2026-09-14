async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || 'Ошибка запроса.');
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function listChats() {
  return request('/api/chats');
}

export function createChat() {
  return request('/api/chats', { method: 'POST' });
}

export function getChat(chatId) {
  return request(`/api/chats/${chatId}`);
}

export function deleteChat(chatId) {
  return request(`/api/chats/${chatId}`, { method: 'DELETE' });
}

export function sendMessage(chatId, message, compress = true) {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message, compress }),
  });
}
