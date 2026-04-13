/**
 * Dialogue panel — shows speaker, dialogue text, and the player input area.
 */

export function renderDialoguePanel(container, turnData, viewState, onSubmit) {
  container.innerHTML = '';

  const panel = document.createElement('div');
  panel.className = 'dialogue-panel';

  // Speaker and dialogue
  const speechBubble = document.createElement('div');
  speechBubble.className = 'speech-bubble';

  const speakerEl = document.createElement('div');
  speakerEl.className = `speaker ${turnData.speaker_type}`;
  speakerEl.textContent = turnData.speaker;
  speechBubble.appendChild(speakerEl);

  const dialogueEl = document.createElement('div');
  dialogueEl.className = `dialogue ${turnData.speaker_type}`;
  dialogueEl.textContent = turnData.dialogue;
  speechBubble.appendChild(dialogueEl);

  panel.appendChild(speechBubble);

  // Error message
  if (viewState.errorMessage) {
    const errEl = document.createElement('div');
    errEl.className = 'error-message';
    errEl.textContent = viewState.errorMessage;
    panel.appendChild(errEl);
  }

  // Input area (hidden if game finished)
  if (!turnData.game_finished) {
    const inputArea = document.createElement('form');
    inputArea.className = 'input-area';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'player-input';
    input.placeholder = 'Ask, inspect, accuse, or tell\u2026';
    input.value = viewState.inputText;
    input.disabled = viewState.isSubmitting;
    input.addEventListener('input', (e) => {
      viewState.inputText = e.target.value;
    });

    const submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.className = 'submit-btn';
    submitBtn.textContent = viewState.isSubmitting ? 'Thinking\u2026' : 'Send';
    submitBtn.disabled = viewState.isSubmitting;

    inputArea.appendChild(input);
    inputArea.appendChild(submitBtn);

    inputArea.addEventListener('submit', (e) => {
      e.preventDefault();
      if (!viewState.isSubmitting && viewState.inputText.trim()) {
        onSubmit(viewState.inputText.trim());
      }
    });

    panel.appendChild(inputArea);

    // Auto-focus the input
    requestAnimationFrame(() => input.focus());
  } else {
    const endMsg = document.createElement('div');
    endMsg.className = 'game-finished';
    endMsg.textContent = 'The story has reached its conclusion.';
    panel.appendChild(endMsg);
  }

  container.appendChild(panel);
}
