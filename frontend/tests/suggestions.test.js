import { describe, it, expect, beforeEach } from 'vitest';
import { renderSuggestions } from '../src/components/prompt-suggestions.js';

describe('renderSuggestions', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
  });

  it('renders up to 3 suggestion buttons', () => {
    renderSuggestions(container, ['a', 'b', 'c', 'd'], () => {});
    const buttons = container.querySelectorAll('.suggestion-btn');
    expect(buttons.length).toBe(3);
    expect(buttons[0].textContent).toBe('a');
    expect(buttons[2].textContent).toBe('c');
  });

  it('calls onSelect with the suggestion text', () => {
    let selected = null;
    renderSuggestions(container, ['ask about the key'], (t) => { selected = t; });
    container.querySelector('.suggestion-btn').click();
    expect(selected).toBe('ask about the key');
  });

  it('renders nothing when suggestions are empty', () => {
    renderSuggestions(container, [], () => {});
    expect(container.innerHTML).toBe('');
  });
});
