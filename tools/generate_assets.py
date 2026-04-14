"""CLI tool to generate scenario image assets using the OpenAI Image API.

Usage:
    python -m tools.generate_assets <scenario_id> [--force] [--model MODEL] [--quality QUALITY]

Example:
    python -m tools.generate_assets manor
    python -m tools.generate_assets manor --force --quality high
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

from backend.app.services.scenario_loader import ScenarioLoader
from tools.prompts.backgrounds import build_background_prompt
from tools.prompts.portraits import build_portrait_prompt

BACKGROUND_SIZE = "1536x1024"
PORTRAIT_SIZE = "1024x1536"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate scenario image assets via OpenAI Image API.",
    )
    parser.add_argument("scenario_id", help="Scenario folder name (e.g. 'manor')")
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing PNG files",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("IMAGE_GEN_MODEL", "gpt-image-1.5"),
        help="OpenAI image model (default: gpt-image-1.5 or IMAGE_GEN_MODEL env var)",
    )
    parser.add_argument(
        "--quality",
        default=os.environ.get("IMAGE_GEN_QUALITY", "medium"),
        choices=["low", "medium", "high"],
        help="Image quality (default: medium or IMAGE_GEN_QUALITY env var)",
    )
    return parser.parse_args()


def _write_image(image_b64: str, output_path: Path) -> None:
    """Decode base64 image data and write to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(image_b64))


MAX_RETRIES = 2
RETRY_BASE_DELAY = 2.0  # seconds


def _generate_image(
    client: OpenAI,
    prompt: str,
    size: str,
    model: str,
    quality: str,
    background: str = "auto",
) -> str:
    """Call the OpenAI Image API with retry and return base64-encoded image data.

    Retries on transient errors (rate limits, timeouts, server errors).
    Raises immediately on permanent errors (auth, moderation refusal).
    """
    from openai import APIStatusError, APITimeoutError, RateLimitError

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                background=background,
                n=1,
            )
            return response.data[0].b64_json
        except RateLimitError as exc:
            last_exc = exc
            _retry_wait(attempt, "Rate limited")
        except APITimeoutError as exc:
            last_exc = exc
            _retry_wait(attempt, "Timeout")
        except APIStatusError as exc:
            if exc.status_code >= 500:
                last_exc = exc
                _retry_wait(attempt, f"Server error {exc.status_code}")
            elif exc.status_code == 400 and "content_policy" in str(exc.body).lower():
                raise RuntimeError(
                    f"Content moderation refusal: {exc.message}"
                ) from exc
            else:
                raise
        except Exception:
            raise
    raise RuntimeError(f"Failed after {MAX_RETRIES + 1} attempts: {last_exc}") from last_exc


def _retry_wait(attempt: int, reason: str) -> None:
    """Exponential backoff wait between retries."""
    if attempt < MAX_RETRIES:
        delay = RETRY_BASE_DELAY * (2 ** attempt)
        print(f"  RETRY {reason}, waiting {delay:.0f}s (attempt {attempt + 1}/{MAX_RETRIES + 1})...")
        time.sleep(delay)


def main() -> None:
    args = _parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Try loading from .env file
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        print("Error: Set OPENAI_API_KEY environment variable or add it to .env")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Load scenario using the existing typed loader
    scenario_root = Path("scenarios")
    loader = ScenarioLoader(base_path=scenario_root)
    try:
        package = loader.load_scenario_package(args.scenario_id)
    except FileNotFoundError:
        available = [p.name for p in scenario_root.iterdir() if p.is_dir()]
        print(f"Error: Scenario '{args.scenario_id}' not found.")
        print(f"Available scenarios: {', '.join(available) or '(none)'}")
        sys.exit(1)

    assets_base = Path("assets") / "scenarios" / args.scenario_id
    generated: list[str] = []
    failed: list[str] = []

    # Generate backgrounds
    for location in package.locations.locations:
        asset_name = Path(location.background_asset).stem + ".png"
        output_path = assets_base / "backgrounds" / asset_name

        if output_path.exists() and not args.force:
            print(f"  SKIP  {output_path} (already exists, use --force to overwrite)")
            continue

        prompt = build_background_prompt(location)
        print(f"  GEN   {output_path} ...")
        try:
            image_b64 = _generate_image(
                client, prompt, BACKGROUND_SIZE, args.model, args.quality,
            )
            _write_image(image_b64, output_path)
            generated.append(str(output_path))
            print(f"  OK    {output_path}")
        except Exception as exc:
            failed.append(str(output_path))
            print(f"  FAIL  {output_path}: {exc}")

    # Generate portraits
    for character in package.characters.characters:
        asset_name = Path(character.portrait_asset).stem + ".png"
        output_path = assets_base / "portraits" / asset_name

        if output_path.exists() and not args.force:
            print(f"  SKIP  {output_path} (already exists, use --force to overwrite)")
            continue

        prompt = build_portrait_prompt(character)
        print(f"  GEN   {output_path} ...")
        try:
            image_b64 = _generate_image(
                client, prompt, PORTRAIT_SIZE, args.model, args.quality,
                background="transparent",
            )
            _write_image(image_b64, output_path)
            generated.append(str(output_path))
            print(f"  OK    {output_path}")
        except Exception as exc:
            failed.append(str(output_path))
            print(f"  FAIL  {output_path}: {exc}")

    # Update JSON references only if all succeeded
    print()
    if failed:
        print(f"WARNING: {len(failed)} asset(s) failed to generate:")
        for f in failed:
            print(f"  - {f}")
        print("JSON references NOT updated. Fix errors and re-run.")
    else:
        _update_json_references(scenario_root / args.scenario_id)
        print(f"Done. {len(generated)} asset(s) generated.")
        if not generated:
            print("(All assets already existed. Use --force to regenerate.)")


def _update_json_references(scenario_dir: Path) -> None:
    """Replace .svg extensions with .png in scenario JSON files."""
    for filename in ("assets.json", "characters.json", "locations.json"):
        filepath = scenario_dir / filename
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        updated = text.replace(".svg", ".png")
        if updated != text:
            filepath.write_text(updated, encoding="utf-8")
            print(f"  Updated {filepath}")


if __name__ == "__main__":
    main()
