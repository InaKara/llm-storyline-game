/**
 * API client — all HTTP communication with the backend goes through here.
 */

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export function createSession() {
  return request('/api/sessions', { method: 'POST' });
}

export function submitTurn(sessionId, playerInput) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/turns`, {
    method: 'POST',
    body: JSON.stringify({ player_input: playerInput }),
  });
}

export function getState(sessionId) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/state`);
}

export function resetSession(sessionId) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/reset`, {
    method: 'POST',
  });
}

export function switchCharacter(sessionId, characterId) {
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/addressed-character`,
    {
      method: 'PUT',
      body: JSON.stringify({ character_id: characterId }),
    }
  );
}

export function move(sessionId, targetLocation) {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/move`, {
    method: 'POST',
    body: JSON.stringify({ target_location: targetLocation }),
  });
}
