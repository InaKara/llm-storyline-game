/**
 * Top-level renderer — composes scene view, dialogue panel, and suggestions.
 * Called after every state change.
 */

import { renderSceneView } from './components/scene-view.js';
import { renderDialoguePanel } from './components/dialogue-panel.js';
import { renderSuggestions } from './components/prompt-suggestions.js';

export function renderApp(turnData, viewState, { onSubmit, onCharacterClick, onSuggestion, onReset, onMove }) {
  const app = document.getElementById('app');
  app.innerHTML = '';

  // Scene area
  const sceneContainer = document.createElement('div');
  sceneContainer.id = 'scene-container';
  app.appendChild(sceneContainer);
  renderSceneView(sceneContainer, turnData, viewState, onCharacterClick);

  // Dialogue area
  const dialogueContainer = document.createElement('div');
  dialogueContainer.id = 'dialogue-container';
  app.appendChild(dialogueContainer);
  renderDialoguePanel(dialogueContainer, turnData, viewState, onSubmit);

  // Suggestions
  if (!turnData.game_finished) {
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.id = 'suggestions-container';
    app.appendChild(suggestionsContainer);
    renderSuggestions(suggestionsContainer, turnData.suggestions, onSuggestion);
  }

  // Available exits as movement buttons — call move API directly
  if (turnData.available_exits && turnData.available_exits.length > 0 && !turnData.game_finished) {
    const exitsBar = document.createElement('div');
    exitsBar.className = 'exits-bar';
    const label = document.createElement('span');
    label.className = 'exits-label';
    label.textContent = 'Go to:';
    exitsBar.appendChild(label);
    for (const exit of turnData.available_exits) {
      const btn = document.createElement('button');
      btn.className = 'exit-btn';
      btn.textContent = exit;
      btn.addEventListener('click', () => onMove(exit));
      exitsBar.appendChild(btn);
    }
    app.appendChild(exitsBar);
  }

  // Reset button
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  const resetBtn = document.createElement('button');
  resetBtn.className = 'reset-btn';
  resetBtn.textContent = 'Restart';
  resetBtn.addEventListener('click', onReset);
  toolbar.appendChild(resetBtn);
  app.appendChild(toolbar);
}
