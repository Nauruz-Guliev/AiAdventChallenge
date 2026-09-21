async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.reason || 'Ошибка запроса.';
    const error = new Error(message);
    error.status = response.status;
    error.detail = detail;
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

export function clearHistory(chatId) {
  return request(`/api/chats/${chatId}/messages`, { method: 'DELETE' });
}

export function sendMessage(chatId, message) {
  return request(`/api/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export function saveWorkingMemory(chatId, working) {
  return request(`/api/chats/${chatId}/working-memory`, {
    method: 'PUT',
    body: JSON.stringify(working),
  });
}

export function completeWorkingMemory(chatId) {
  return request(`/api/chats/${chatId}/working-memory/complete`, {
    method: 'POST',
  });
}

export function resetWorkingMemory(chatId) {
  return request(`/api/chats/${chatId}/working-memory/reset`, {
    method: 'POST',
  });
}

export function getLongTerm() {
  return request('/api/long-term');
}

export function replaceLongTerm(longTerm) {
  return request('/api/long-term', {
    method: 'PUT',
    body: JSON.stringify(longTerm),
  });
}

export function deleteLongTermEntry(category, entryId) {
  return request(`/api/long-term/${category}/${entryId}`, { method: 'DELETE' });
}

export function listCandidates(status = 'pending') {
  return request(`/api/candidates?status=${status}`);
}

export function approveCandidate(candidateId, payload = {}) {
  return request(`/api/candidates/${candidateId}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function rejectCandidate(candidateId) {
  return request(`/api/candidates/${candidateId}/reject`, { method: 'POST' });
}

export function getProfiles() {
  return request('/api/profiles');
}

export function getProfilePresets() {
  return request('/api/profiles/presets');
}

export function createProfile(payload) {
  return request('/api/profiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createProfileFromPreset(key) {
  return request('/api/profiles/from-preset', {
    method: 'POST',
    body: JSON.stringify({ key }),
  });
}

export function updateProfile(profileId, payload) {
  return request(`/api/profiles/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProfile(profileId) {
  return request(`/api/profiles/${profileId}`, { method: 'DELETE' });
}

export function activateProfile(profileId) {
  return request(`/api/profiles/${profileId}/activate`, { method: 'POST' });
}

export function getTaskState() {
  return request('/api/task/state');
}

export function pauseTask() {
  return request('/api/task/pause', { method: 'POST' });
}

export function resumeTask() {
  return request('/api/task/resume', { method: 'POST' });
}

export function getTaskTransitions() {
  return request('/api/task/transitions');
}

export function applyTaskTransition(event) {
  return request('/api/task/transition', {
    method: 'POST',
    body: JSON.stringify({ event }),
  });
}

export function getInvariants() {
  return request('/api/invariants');
}

export function createInvariant(payload) {
  return request('/api/invariants', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deleteInvariant(invariantId) {
  return request(`/api/invariants/${invariantId}`, { method: 'DELETE' });
}