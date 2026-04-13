/**
 * Scene view — renders background image, character portrait, location name,
 * and character-switching buttons.
 */

export function renderSceneView(container, turnData, viewState, onCharacterClick) {
  container.innerHTML = '';

  // Background
  const scene = document.createElement('div');
  scene.className = 'scene-view';
  if (turnData.background_url) {
    scene.style.backgroundImage = `url(${turnData.background_url})`;
  }

  // Location label
  const locationLabel = document.createElement('div');
  locationLabel.className = 'location-label';
  locationLabel.textContent = turnData.location;
  scene.appendChild(locationLabel);

  // Portrait
  if (turnData.portrait_url) {
    const portrait = document.createElement('img');
    portrait.className = 'portrait';
    portrait.src = turnData.portrait_url;
    portrait.alt = turnData.speaker || 'Character';
    portrait.onerror = () => { portrait.style.display = 'none'; };
    scene.appendChild(portrait);
  }

  // Character buttons
  if (turnData.available_characters && turnData.available_characters.length > 0) {
    const charBar = document.createElement('div');
    charBar.className = 'character-bar';
    for (const charId of turnData.available_characters) {
      const btn = document.createElement('button');
      btn.className = 'character-btn';
      btn.textContent = charId;
      if (viewState.addressedCharacter === charId) {
        btn.classList.add('active');
      }
      btn.addEventListener('click', () => onCharacterClick(charId));
      charBar.appendChild(btn);
    }
    scene.appendChild(charBar);
  }

  container.appendChild(scene);
}
