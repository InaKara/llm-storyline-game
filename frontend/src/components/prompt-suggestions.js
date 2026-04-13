/**
 * Prompt suggestions — clickable suggestion buttons below the input.
 */

export function renderSuggestions(container, suggestions, onSelect) {
  container.innerHTML = '';

  if (!suggestions || suggestions.length === 0) return;

  const bar = document.createElement('div');
  bar.className = 'suggestions-bar';

  for (const text of suggestions.slice(0, 3)) {
    const btn = document.createElement('button');
    btn.className = 'suggestion-btn';
    btn.textContent = text;
    btn.addEventListener('click', () => onSelect(text));
    bar.appendChild(btn);
  }

  container.appendChild(bar);
}
