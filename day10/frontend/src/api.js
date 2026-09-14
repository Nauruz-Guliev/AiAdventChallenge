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

export function sendMessage(chatId, message, mode = 'sliding') {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message, mode }),
  });
}

export function createBranch(chatId, afterMessageIndex, name) {
  return request(`/api/chats/${chatId}/branches`, {
    body: JSON.stringify({ after_message_index: afterMessageIndex, name }),
    method: 'POST',
  });
}

export function setActiveBranch(chatId, branchId) {
  return request(`/api/chats/${chatId}/active-branch`, {
    body: JSON.stringify({ branch_id: branchId }),
    method: 'PATCH',
  });
}

export function deleteBranch(chatId, branchId) {
  return request(`/api/chats/${chatId}/branches/${branchId}`, { method: 'DELETE' });
}

export function updateFacts(chatId, facts) {
  return request(`/api/chats/${chatId}/facts`, {
    body: JSON.stringify({ facts }),
    method: 'PATCH',
  });
}

export function runCompare() {
  return request('/api/compare', { method: 'POST' });
}
