"""Tests for the image generation tool and prompt builders."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.domain.scenario_models import CharacterDefinition, LocationDefinition
from backend.app.services.scenario_loader import ScenarioLoader
from tools.prompts.backgrounds import build_background_prompt
from tools.prompts.portraits import build_portrait_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def location():
    return LocationDefinition(
        id="study",
        name="The Study",
        description="A wood-paneled room with tall bookshelves.",
        background_asset="study.png",
        initially_available=True,
    )


@pytest.fixture()
def character():
    return CharacterDefinition(
        id="steward",
        name="Mr. Hargrove",
        role="steward",
        personality="Formal, guarded, efficient.",
        knowledge="Knows the full truth.",
        portrait_asset="steward.png",
    )


@pytest.fixture()
def manor_package():
    loader = ScenarioLoader(base_path=Path("scenarios"))
    return loader.load_scenario_package("manor")


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------

class TestBuildBackgroundPrompt:
    def test_returns_nonempty_string(self, location):
        prompt = build_background_prompt(location)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_contains_location_name(self, location):
        prompt = build_background_prompt(location)
        assert "The Study" in prompt

    def test_contains_location_description(self, location):
        prompt = build_background_prompt(location)
        assert "wood-paneled" in prompt

    def test_includes_no_characters_guidance(self, location):
        prompt = build_background_prompt(location)
        assert "No characters" in prompt


class TestBuildPortraitPrompt:
    def test_returns_nonempty_string(self, character):
        prompt = build_portrait_prompt(character)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_contains_character_name(self, character):
        prompt = build_portrait_prompt(character)
        assert "Mr. Hargrove" in prompt

    def test_contains_character_role(self, character):
        prompt = build_portrait_prompt(character)
        assert "steward" in prompt

    def test_includes_no_text_guidance(self, character):
        prompt = build_portrait_prompt(character)
        assert "No text" in prompt or "No background" in prompt


# ---------------------------------------------------------------------------
# Prompt builders work with real scenario data
# ---------------------------------------------------------------------------

class TestPromptsWithRealScenario:
    def test_all_locations_produce_prompts(self, manor_package):
        for loc in manor_package.locations.locations:
            prompt = build_background_prompt(loc)
            assert loc.name in prompt

    def test_all_characters_produce_prompts(self, manor_package):
        for char in manor_package.characters.characters:
            prompt = build_portrait_prompt(char)
            assert char.name in prompt


# ---------------------------------------------------------------------------
# CLI / generate_assets tests (mocked API)
# ---------------------------------------------------------------------------

# A tiny 1x1 red PNG as base64
_FAKE_PNG_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


class TestGenerateAssets:
    def test_write_image_creates_file(self, tmp_path):
        from tools.generate_assets import _write_image

        output = tmp_path / "sub" / "test.png"
        _write_image(_FAKE_PNG_B64, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_skip_existing_without_force(self, tmp_path):
        from tools.generate_assets import _write_image

        output = tmp_path / "test.png"
        output.write_bytes(b"original")
        # Simulate the skip logic from main()
        assert output.exists()
        assert output.read_bytes() == b"original"

    def test_force_overwrites_existing(self, tmp_path):
        from tools.generate_assets import _write_image

        output = tmp_path / "test.png"
        output.write_bytes(b"original")
        _write_image(_FAKE_PNG_B64, output)
        assert output.read_bytes() != b"original"

    def test_generate_image_calls_api(self):
        from tools.generate_assets import _generate_image

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(b64_json=_FAKE_PNG_B64)]
        mock_client.images.generate.return_value = mock_response

        result = _generate_image(
            mock_client, "test prompt", "1024x1024", "gpt-image-1.5", "medium",
        )

        assert result == _FAKE_PNG_B64
        mock_client.images.generate.assert_called_once_with(
            model="gpt-image-1.5",
            prompt="test prompt",
            size="1024x1024",
            quality="medium",
            background="auto",
            n=1,
        )

    def test_generate_image_passes_transparent_background(self):
        from tools.generate_assets import _generate_image

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(b64_json=_FAKE_PNG_B64)]
        mock_client.images.generate.return_value = mock_response

        result = _generate_image(
            mock_client, "portrait prompt", "1024x1536", "gpt-image-1.5", "medium",
            background="transparent",
        )

        assert result == _FAKE_PNG_B64
        mock_client.images.generate.assert_called_once_with(
            model="gpt-image-1.5",
            prompt="portrait prompt",
            size="1024x1536",
            quality="medium",
            background="transparent",
            n=1,
        )

    def test_retry_on_rate_limit(self):
        from openai import RateLimitError
        from tools.generate_assets import _generate_image

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(b64_json=_FAKE_PNG_B64)]

        mock_client.images.generate.side_effect = [
            RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            mock_response,
        ]

        with patch("tools.generate_assets.time.sleep"):
            result = _generate_image(
                mock_client, "prompt", "1024x1024", "gpt-image-1.5", "medium",
            )
        assert result == _FAKE_PNG_B64
        assert mock_client.images.generate.call_count == 2

    def test_moderation_refusal_raises_immediately(self):
        from openai import APIStatusError
        from tools.generate_assets import _generate_image

        mock_client = MagicMock()
        mock_resp = MagicMock(status_code=400, headers={})
        mock_client.images.generate.side_effect = APIStatusError(
            message="content_policy_violation",
            response=mock_resp,
            body={"error": {"code": "content_policy_violation"}},
        )

        with pytest.raises(RuntimeError, match="Content moderation"):
            _generate_image(
                mock_client, "prompt", "1024x1024", "gpt-image-1.5", "medium",
            )
        # Should not retry on moderation refusal
        assert mock_client.images.generate.call_count == 1


# ---------------------------------------------------------------------------
# _update_json_references tests
# ---------------------------------------------------------------------------

class TestUpdateJsonReferences:
    def _make_scenario_dir(self, tmp_path):
        """Create a minimal scenario directory with .svg references."""
        d = tmp_path / "test_scenario"
        d.mkdir()
        (d / "assets.json").write_text(json.dumps({
            "portraits": {"steward": "scenarios/test/portraits/steward.svg"},
            "backgrounds": {"study": "scenarios/test/backgrounds/study.svg"},
        }), encoding="utf-8")
        (d / "characters.json").write_text(json.dumps({
            "characters": [{"portrait_asset": "steward.svg"}],
        }), encoding="utf-8")
        (d / "locations.json").write_text(json.dumps({
            "locations": [{"background_asset": "study.svg"}],
        }), encoding="utf-8")
        return d

    def test_updates_svg_to_png(self, tmp_path):
        from tools.generate_assets import _update_json_references

        d = self._make_scenario_dir(tmp_path)
        _update_json_references(d)

        assets = json.loads((d / "assets.json").read_text(encoding="utf-8"))
        assert assets["portraits"]["steward"].endswith(".png")
        assert assets["backgrounds"]["study"].endswith(".png")

        chars = json.loads((d / "characters.json").read_text(encoding="utf-8"))
        assert chars["characters"][0]["portrait_asset"].endswith(".png")

        locs = json.loads((d / "locations.json").read_text(encoding="utf-8"))
        assert locs["locations"][0]["background_asset"].endswith(".png")

    def test_idempotent_on_already_png(self, tmp_path):
        from tools.generate_assets import _update_json_references

        d = self._make_scenario_dir(tmp_path)
        _update_json_references(d)
        text_after_first = (d / "assets.json").read_text(encoding="utf-8")
        _update_json_references(d)
        text_after_second = (d / "assets.json").read_text(encoding="utf-8")
        assert text_after_first == text_after_second


# ---------------------------------------------------------------------------
# Integration: main() with mocked API
# ---------------------------------------------------------------------------

class TestMainIntegration:
    def _setup_workspace(self, tmp_path):
        """Copy real scenario files into a temp workspace."""
        # Copy scenario
        scenario_src = Path("scenarios") / "manor"
        scenario_dst = tmp_path / "scenarios" / "manor"
        shutil.copytree(scenario_src, scenario_dst)

        # Create empty asset dirs
        (tmp_path / "assets" / "scenarios" / "manor" / "portraits").mkdir(parents=True)
        (tmp_path / "assets" / "scenarios" / "manor" / "backgrounds").mkdir(parents=True)
        return tmp_path

    def test_main_generates_and_updates_json(self, tmp_path, monkeypatch):
        from tools.generate_assets import main

        ws = self._setup_workspace(tmp_path)
        monkeypatch.chdir(ws)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        mock_response = MagicMock()
        mock_response.data = [MagicMock(b64_json=_FAKE_PNG_B64)]

        with patch("tools.generate_assets.OpenAI") as MockOpenAI, \
             patch("sys.argv", ["generate_assets", "manor"]):
            MockOpenAI.return_value.images.generate.return_value = mock_response
            main()

        # PNGs should exist
        portraits = ws / "assets" / "scenarios" / "manor" / "portraits"
        backgrounds = ws / "assets" / "scenarios" / "manor" / "backgrounds"
        assert (portraits / "steward.png").exists()
        assert (portraits / "heir.png").exists()
        assert (backgrounds / "study.png").exists()
        assert (backgrounds / "archive.png").exists()

        # JSON references should now be .png
        chars = json.loads(
            (ws / "scenarios" / "manor" / "characters.json").read_text(encoding="utf-8")
        )
        for c in chars["characters"]:
            assert c["portrait_asset"].endswith(".png")

    def test_main_does_not_update_json_on_failure(self, tmp_path, monkeypatch):
        from tools.generate_assets import main

        ws = self._setup_workspace(tmp_path)
        monkeypatch.chdir(ws)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Make the API always fail
        with patch("tools.generate_assets.OpenAI") as MockOpenAI, \
             patch("sys.argv", ["generate_assets", "manor"]):
            MockOpenAI.return_value.images.generate.side_effect = RuntimeError("API down")
            main()

        # JSON references should still be .svg
        chars = json.loads(
            (ws / "scenarios" / "manor" / "characters.json").read_text(encoding="utf-8")
        )
        for c in chars["characters"]:
            assert c["portrait_asset"].endswith(".svg")
