import { describe, it, expect, beforeEach } from 'vitest';
import { renderDialoguePanel } from '../src/components/dialogue-panel.js';

function makeTurnData(overrides = {}) {
  return {
    speaker: 'Mr. Hargrove',
    speaker_type: 'character',
    dialogue: 'Good evening.',
    game_finished: false,
    ...overrides,
  };
}

function makeViewState(overrides = {}) {
  return {
    isSubmitting: false,
    inputText: '',
    errorMessage: null,
    ...overrides,
  };
}

describe('renderDialoguePanel', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
  });

  it('renders speaker name and dialogue', () => {
    renderDialoguePanel(container, makeTurnData(), makeViewState(), () => {});
    expect(container.querySelector('.speaker').textContent).toBe('Mr. Hargrove');
    expect(container.querySelector('.dialogue').textContent).toBe('Good evening.');
  });

  it('applies narrator styling for narrator turns', () => {
    renderDialoguePanel(
      container,
      makeTurnData({ speaker_type: 'narrator', speaker: 'Narrator' }),
      makeViewState(),
      () => {}
    );
    expect(container.querySelector('.speaker.narrator')).not.toBeNull();
    expect(container.querySelector('.dialogue.narrator')).not.toBeNull();
  });

  it('disables input when isSubmitting is true', () => {
    renderDialoguePanel(container, makeTurnData(), makeViewState({ isSubmitting: true }), () => {});
    const input = container.querySelector('.player-input');
    expect(input.disabled).toBe(true);
    const btn = container.querySelector('.submit-btn');
    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toBe('Thinking\u2026');
  });

  it('shows error message when present', () => {
    renderDialoguePanel(container, makeTurnData(), makeViewState({ errorMessage: 'fail' }), () => {});
    expect(container.querySelector('.error-message').textContent).toBe('fail');
  });

  it('hides input and shows game-finished text when game is over', () => {
    renderDialoguePanel(container, makeTurnData({ game_finished: true }), makeViewState(), () => {});
    expect(container.querySelector('.player-input')).toBeNull();
    expect(container.querySelector('.game-finished')).not.toBeNull();
  });

  it('calls onSubmit with trimmed text on form submit', () => {
    let submitted = null;
    renderDialoguePanel(container, makeTurnData(), makeViewState({ inputText: '  hello  ' }), (t) => { submitted = t; });
    const form = container.querySelector('.input-area');
    form.dispatchEvent(new Event('submit'));
    expect(submitted).toBe('hello');
  });
});
