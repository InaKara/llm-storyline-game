import { describe, it, expect, beforeEach } from 'vitest';
import { renderSceneView } from '../src/components/scene-view.js';

function makeTurnData(overrides = {}) {
  return {
    location: 'study',
    background_url: '/assets/bg.svg',
    portrait_url: '/assets/portrait.svg',
    speaker: 'Mr. Hargrove',
    speaker_type: 'character',
    available_characters: ['steward', 'heir'],
    ...overrides,
  };
}

describe('renderSceneView', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
  });

  it('renders background image from turnData', () => {
    const viewState = { addressedCharacter: 'steward' };
    renderSceneView(container, makeTurnData(), viewState, () => {});
    const scene = container.querySelector('.scene-view');
    expect(scene.style.backgroundImage).toContain('/assets/bg.svg');
  });

  it('renders location label', () => {
    const viewState = { addressedCharacter: 'steward' };
    renderSceneView(container, makeTurnData(), viewState, () => {});
    const label = container.querySelector('.location-label');
    expect(label.textContent).toBe('study');
  });

  it('renders portrait image', () => {
    const viewState = { addressedCharacter: 'steward' };
    renderSceneView(container, makeTurnData(), viewState, () => {});
    const portrait = container.querySelector('.portrait');
    expect(portrait.src).toContain('/assets/portrait.svg');
    expect(portrait.alt).toBe('Mr. Hargrove');
  });

  it('hides portrait when portrait_url is null', () => {
    const viewState = { addressedCharacter: 'steward' };
    renderSceneView(container, makeTurnData({ portrait_url: null }), viewState, () => {});
    expect(container.querySelector('.portrait')).toBeNull();
  });

  it('highlights the addressed character, not the last speaker', () => {
    const viewState = { addressedCharacter: 'heir' };
    renderSceneView(container, makeTurnData(), viewState, () => {});
    const buttons = container.querySelectorAll('.character-btn');
    expect(buttons[0].textContent).toBe('steward');
    expect(buttons[0].classList.contains('active')).toBe(false);
    expect(buttons[1].textContent).toBe('heir');
    expect(buttons[1].classList.contains('active')).toBe(true);
  });

  it('calls onCharacterClick with the character ID', () => {
    const viewState = { addressedCharacter: 'steward' };
    let clicked = null;
    renderSceneView(container, makeTurnData(), viewState, (id) => { clicked = id; });
    const heirBtn = container.querySelectorAll('.character-btn')[1];
    heirBtn.click();
    expect(clicked).toBe('heir');
  });
});
