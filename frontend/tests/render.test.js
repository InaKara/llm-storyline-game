import { describe, it, expect, beforeEach } from 'vitest';
import { renderApp } from '../src/render.js';

function makeTurnData(overrides = {}) {
  return {
    location: 'study',
    background_url: '/assets/bg.svg',
    portrait_url: '/assets/portrait.svg',
    speaker: 'Mr. Hargrove',
    speaker_type: 'character',
    dialogue: 'Good evening.',
    available_characters: ['steward', 'heir'],
    available_exits: [],
    suggestions: ['Ask about the testament'],
    game_finished: false,
    ...overrides,
  };
}

function makeViewState(overrides = {}) {
  return {
    isSubmitting: false,
    inputText: '',
    errorMessage: null,
    addressedCharacter: 'steward',
    ...overrides,
  };
}

function noop() {}

const callbacks = {
  onSubmit: noop,
  onCharacterClick: noop,
  onSuggestion: noop,
  onReset: noop,
  onMove: noop,
};

describe('renderApp', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>';
  });

  it('renders all major sections', () => {
    renderApp(makeTurnData(), makeViewState(), callbacks);
    expect(document.getElementById('scene-container')).not.toBeNull();
    expect(document.getElementById('dialogue-container')).not.toBeNull();
    expect(document.getElementById('suggestions-container')).not.toBeNull();
    expect(document.querySelector('.toolbar')).not.toBeNull();
  });

  it('renders exit buttons that call onMove directly', () => {
    let movedTo = null;
    renderApp(
      makeTurnData({ available_exits: ['archive'] }),
      makeViewState(),
      { ...callbacks, onMove: (loc) => { movedTo = loc; } }
    );
    const exitBtn = document.querySelector('.exit-btn');
    expect(exitBtn.textContent).toBe('archive');
    exitBtn.click();
    expect(movedTo).toBe('archive');
  });

  it('hides suggestions and exits when game is finished', () => {
    renderApp(makeTurnData({ game_finished: true }), makeViewState(), callbacks);
    expect(document.getElementById('suggestions-container')).toBeNull();
    expect(document.querySelector('.exits-bar')).toBeNull();
  });
});
