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

export function askQuestion(question) {
  return request('/api/answer', { method: 'POST', body: JSON.stringify({ question }) });
}

export function runEval() {
  return request('/api/eval', { method: 'POST' });
}

export function getQuestions() {
  return request('/api/questions');
}
