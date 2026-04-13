/**
 * Main entrypoint — bootstrap, session creation, event wiring.
 */

import { createSession, submitTurn, resetSession, switchCharacter, move } from './api.js';
import { state } from './state.js';
import { renderApp } from './render.js';

function render() {
  if (!state.currentTurn) return;
  renderApp(state.currentTurn, state, {
    onSubmit: handleSubmit,
    onCharacterClick: handleCharacterClick,
    onSuggestion: handleSuggestion,
    onReset: handleReset,
    onMove: handleMove,
  });
}

async function handleSubmit(text) {
  if (state.isSubmitting || !text) return;

  state.isSubmitting = true;
  state.inputText = '';
  state.errorMessage = null;
  render();

  try {
    const data = await submitTurn(state.sessionId, text);
    state.currentTurn = data;
  } catch (err) {
    state.errorMessage = err.message;
  } finally {
    state.isSubmitting = false;
    render();
  }
}

async function handleCharacterClick(characterId) {
  if (state.isSubmitting) return;

  state.isSubmitting = true;
  state.errorMessage = null;
  render();

  try {
    const stateResp = await switchCharacter(state.sessionId, characterId);
    state.addressedCharacter = stateResp.addressed_character;
  } catch (err) {
    state.errorMessage = err.message;
  } finally {
    state.isSubmitting = false;
    render();
  }
}

function handleSuggestion(text) {
  state.inputText = text;
  handleSubmit(text);
}

async function handleMove(locationId) {
  if (state.isSubmitting) return;

  state.isSubmitting = true;
  state.errorMessage = null;
  render();

  try {
    const data = await move(state.sessionId, locationId);
    state.currentTurn = data;
  } catch (err) {
    state.errorMessage = err.message;
  } finally {
    state.isSubmitting = false;
    render();
  }
}

async function handleReset() {
  if (state.isSubmitting) return;

  state.isSubmitting = true;
  state.errorMessage = null;
  render();

  try {
    const data = await resetSession(state.sessionId);
    state.currentTurn = data;
    state.addressedCharacter = data.available_characters[0] || null;
  } catch (err) {
    state.errorMessage = err.message;
  } finally {
    state.isSubmitting = false;
    render();
  }
}

// Bootstrap
async function init() {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading">Starting adventure&hellip;</div>';

  try {
    const data = await createSession();
    state.sessionId = data.session_id;
    state.currentTurn = data;
    state.addressedCharacter = data.available_characters[0] || null;
    render();
  } catch (err) {
    app.innerHTML = `<div class="error-message">Failed to start: ${err.message}</div>`;
  }
}

init();
