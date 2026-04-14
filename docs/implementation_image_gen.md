# Image Generation — Implementation Plan

## Goal

Replace the placeholder SVG assets (portraits and backgrounds) with AI-generated
PNG images using the OpenAI Image API. The generation runs **offline as a CLI
tool** — images are written to disk once per scenario and served as static files
at runtime.

**What you learn:**
- How the OpenAI Image API works (models, sizes, quality, output formats)
- Prompt engineering for image generation
- Building a CLI tool that integrates with an existing project
- Offline asset pipelines vs runtime generation trade-offs

---

## 1. Model & Quality Selection

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Model** | `gpt-image-1.5` | State-of-the-art quality at a *lower* price than `gpt-image-1` ($0.034 vs $0.042 per square medium image). DALL·E 2/3 are deprecated (sunset 2026-05-12) so we skip them entirely. `gpt-image-1-mini` is cheaper but lower quality — not suitable for atmospheric game art. |
| **Quality** | `medium` | Medium quality keeps cost at ~$0.034/square image and ~$0.05/landscape or portrait. High is 4× more expensive; low lacks the detail we need for atmospheric game art. |
| **Output format** | `png` | Lossless, supports transparency should we need it later. Default format for the API. |
| **Moderation** | `auto` (default) | Standard content filtering is fine for a mystery game. |

### Resolution Per Asset Type

| Asset Type | Size | Rationale |
|------------|------|-----------|
| **Backgrounds** | `1536x1024` (landscape) | Natural fit for wide scene backgrounds that fill the viewport. |
| **Portraits** | `1024x1536` (portrait) | Tall orientation suits character portraits displayed at the side of the dialogue panel. |

### Cost Estimate (Manor Scenario)

| Asset | Count | Size | Est. Cost |
|-------|-------|------|-----------|
| Backgrounds | 2 (study, archive) | 1536×1024 | 2 × $0.05 = $0.10 |
| Portraits | 2 (steward, heir) | 1024×1536 | 2 × $0.05 = $0.10 |
| **Total** | **4** | | **~$0.20** |

Adding scenarios later is cheap — each new asset costs ~5 cents.

---

## 2. API Choice — Image API (not Responses API)

We use the **Image API `images.generate` endpoint** because:

- We only need one-shot generation from a text prompt — no multi-turn editing.
- Simpler call surface: prompt in, base64 image out.
- No need for the Responses API conversation machinery.

```python
response = client.images.generate(
    model="gpt-image-1.5",
    prompt="...",
    size="1536x1024",
    quality="medium",
    n=1,
)
image_b64 = response.data[0].b64_json
```

---

## 3. When It Runs

**Offline CLI tool**, not at runtime.

| Concern | Decision |
|---------|----------|
| **Trigger** | Developer runs `python -m tools.generate_assets <scenario_id>` manually. |
| **Frequency** | Once per scenario, re-run only if prompts change or new locations/characters are added. |
| **Idempotency** | Skips files that already exist on disk. Pass `--force` to regenerate. |
| **Runtime impact** | Zero — the game serves pre-generated PNGs from `assets/`. No API calls during gameplay. |

This avoids:
- Latency (complex prompts can take up to 2 minutes).
- Runtime cost (players don't burn tokens).
- API key requirement for players who just want to play locally.

---

## 4. Where It Fits in the App Structure

### 4.1 New Files

```
tools/
  __init__.py
  generate_assets.py          # CLI entry point
  prompts/
    backgrounds.py             # Prompt templates per background
    portraits.py               # Prompt templates per portrait
```

### 4.2 Existing Files Changed

| File | Change |
|------|--------|
| `scenarios/manor/assets.json` | Update paths from `.svg` → `.png` |
| `scenarios/manor/characters.json` | `portrait_asset`: `steward.svg` → `steward.png` |
| `scenarios/manor/locations.json` | `background_asset`: `study.svg` → `study.png` |
| `backend/app/core/config.py` | Add optional `image_gen_model: str` setting (suggested to user, not auto-changed) |
| `pyproject.toml` | (no change — `openai` is already a dependency) |

### 4.3 Asset Output Layout

Generated images land in the existing asset directories:

```
assets/scenarios/manor/
  portraits/
    steward.png       ← replaces steward.svg
    heir.png          ← replaces heir.svg
  backgrounds/
    study.png         ← replaces study.svg
    archive.png       ← replaces archive.svg
```

The SVG placeholders can be kept alongside or deleted — the JSON references will
point to `.png`.

### 4.4 Data Flow

```
┌─────────────────────────────────────┐
│  tools/generate_assets.py (CLI)     │
│                                     │
│  1. Load scenario JSON files        │
│  2. For each character → build      │
│     portrait prompt from template   │
│  3. For each location → build       │
│     background prompt from template │
│  4. Call OpenAI Image API           │
│  5. Decode base64 → write .png      │
└────────────────┬────────────────────┘
                 │ writes to disk
                 ▼
         assets/scenarios/manor/
         ├── portraits/*.png
         └── backgrounds/*.png
                 │ served at runtime
                 ▼
         FastAPI StaticFiles mount
         (/assets/scenarios/manor/...)
                 │
                 ▼
         Vite frontend fetches <img src="...">
```

---

## 5. Prompt Design

Well-crafted prompts are essential for consistent, atmospheric images.

### 5.1 Background Prompts

Each background prompt should include:

- **Art style**: "photorealistic", "realism"
- **Setting description**: pulled from `locations.json` → `description`
- **Mood**: "warm wood tones", "natural light through large windows", "mountain atmosphere"
- **Composition**: "wide establishing shot, no characters, landscape orientation"
- **Negative guidance**: "no text, no UI elements, no anachronistic objects"

Example for **The Study**:
```
Photorealistic wide establishing shot of a modern western chalet study.
Wood-paneled walls with floor-to-ceiling bookshelves, a broad oak desk with
neatly stacked papers. Warm natural light streams through tall alpine windows
with mountain views. Cozy yet sophisticated atmosphere. No characters, no text.
Landscape orientation.
```

### 5.2 Portrait Prompts

Each portrait prompt should include:

- **Art style**: consistent with backgrounds ("photorealistic portrait")
- **Character description**: pulled from `characters.json` → `visual_description` + `personality` + `role`
- **Framing**: "upper body portrait, centered"
- **Mood**: matching the character's disposition
- **Negative guidance**: "no text, no background clutter"

Example for **Mr. Hargrove (steward)**:
```
Photorealistic upper body portrait of a sly-looking English estate manager in
his late 50s. Thin face, sharp narrow eyes, receding grey hair slicked back.
Wearing a fitted dark charcoal vest over a crisp white shirt. Faint smirk
suggesting hidden motives. Warm natural light from a window to one side.
Blurred chalet interior background. No text.
```

Example for **Lady Ashworth (heir)**:
```
Photorealistic upper body portrait of an elegant woman in her early 30s.
Striking, attractive features — high cheekbones, bright intelligent eyes,
rich auburn hair loosely pinned up. Wearing a refined cream blouse with a
delicate gold pendant. Confident, slightly impatient expression. Warm natural
light. Blurred chalet interior background. No text.
```

---

## 6. Implementation Steps

### Step 6.1 — Create prompt template modules

**Create:**
- `tools/__init__.py`
- `tools/prompts/__init__.py`
- `tools/prompts/backgrounds.py`
- `tools/prompts/portraits.py`

**Concept:** Prompt templates are pure functions that take scenario data and return a prompt string. Separating them from the CLI tool keeps prompt iteration independent of tool mechanics.

**Contents:**
- `build_background_prompt(location)` — interpolates `location.name`, `location.description` into the photorealistic chalet style template.
- `build_portrait_prompt(character)` — interpolates `character.visual_description`, `character.name`, `character.role` into the photorealistic upper body portrait template.

**Why separate modules:** Prompts are the part most likely to change. Keeping them in their own files means you can iterate on image quality without touching CLI or API code.

**Verify:** Import the functions, pass a mock location/character dict, and inspect the returned prompt string.

---

### Step 6.2 — Create `tools/generate_assets.py`

**Create:** `tools/generate_assets.py`

**Concept:** A CLI entry point that loads scenario JSON, builds prompts, calls the OpenAI Image API, and writes PNG files to disk. Uses `argparse` for CLI args.

**Contents:**
- Parse CLI args: `scenario_id`, `--force`, `--model` (default `gpt-image-1.5`), `--quality` (default `medium`).
- Load `scenarios/{id}/characters.json`, `locations.json`.
- For each location → build background prompt → call `client.images.generate(size="1536x1024")` → decode base64 → write PNG.
- For each character → build portrait prompt → call `client.images.generate(size="1024x1536")` → decode base64 → write PNG.
- Skip files that already exist on disk (unless `--force`).
- Print progress to stdout.

**Why offline CLI:** Avoids runtime latency (up to 2 minutes per image), runtime cost, and API key requirement for players. Images are generated once per scenario.

**Verify:** `python -m tools.generate_assets manor` generates 4 PNGs in `assets/scenarios/manor/`. Run with `--force` to confirm overwrite.

---

### Step 6.3 — Update scenario JSON references

**Modify:**
- `scenarios/manor/assets.json` — change paths from `.svg` → `.png`
- `scenarios/manor/characters.json` — `portrait_asset`: `.svg` → `.png`
- `scenarios/manor/locations.json` — `background_asset`: `.svg` → `.png`

**Concept:** The scenario JSON files are the single source of truth for asset paths. Updating them here means the running game automatically picks up the new PNGs.

**Why not both formats:** Keeping two sets of references (SVG fallback + PNG) adds complexity. The SVG placeholders can stay on disk but the JSON should point to one canonical path.

**Verify:** Start the backend, create a session, and confirm the `background_url` and `portrait_url` in the API response end in `.png`.

---

### Step 6.4 — Add unit tests

**Create:** `tests/test_generate_assets.py`

**Concept:** Mock `client.images.generate` to return a known base64 PNG. Test that files are written to the expected paths, that `--force` overwrites existing files, and that prompts are built correctly from scenario data.

**Contents:**
- Test: prompt builders return non-empty strings containing character/location names.
- Test: CLI writes PNGs to correct asset paths.
- Test: existing files are skipped without `--force`.
- Test: `--force` overwrites existing files.

**Why mock the API:** Real API calls cost money and are slow. Mocking lets tests run in CI for free.

**Verify:** `uv run pytest tests/test_generate_assets.py` — all tests pass.

---

### Step 6.5 — End-to-end verification

**Run:** `python -m tools.generate_assets manor`

- Confirm 4 PNGs appear in `assets/scenarios/manor/`.
- Start backend + frontend.
- Verify images display correctly in the browser.

---

## 7. Configuration

| Setting | Default | Env var | Purpose |
|---------|---------|---------|---------|
| `image_gen_model` | `gpt-image-1.5` | `IMAGE_GEN_MODEL` | Model override |
| `image_gen_quality` | `medium` | `IMAGE_GEN_QUALITY` | Quality override |

> **Note**: Per project rules, config defaults are not changed directly in code.
> These will be suggested to the user for approval before adding.

---

## 8. Error Handling

| Scenario | Handling |
|----------|----------|
| Missing API key | Exit with clear message: "Set OPENAI_API_KEY to generate images." |
| Content moderation refusal | Log warning, skip that asset, continue with others. |
| Rate limit / timeout | Retry once with exponential backoff, then skip with warning. |
| Network error | Same as rate limit. |
| Scenario not found | Exit with error listing available scenarios. |

---

## 9. Future Enhancements (Out of Scope)

- **`gpt-image-1-mini` downgrade** — swap model string for cheaper generation when quality is less important.
- **Transparent portraits** — set `background: "transparent"` + `png` format for compositing over scene backgrounds.
- **Style consistency pass** — generate all assets in one session using the Responses API multi-turn editing for visual coherence.
- **Prompt iteration UI** — a simple web form to preview/regenerate individual assets.
