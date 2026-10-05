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

export function listSessions() {
  return request('/api/sessions');
}

export function getSession(id) {
  return request(`/api/sessions/${id}`);
}

export function createSession(goal) {
  return request('/api/sessions', { method: 'POST', body: JSON.stringify({ goal }) });
}

export function sendMessage(id, text) {
  return request(`/api/sessions/${id}/messages`, { method: 'POST', body: JSON.stringify({ text }) });
}

export function runScenarios() {
  return request('/api/scenarios/run', { method: 'POST' });
}
