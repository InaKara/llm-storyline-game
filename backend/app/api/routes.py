from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dto import (
    CreateSessionResponse,
    FlagsResponse,
    MoveRequest,
    ResetSessionResponse,
    SessionStateResponse,
    SubmitTurnRequest,
    SubmitTurnResponse,
    SwitchCharacterRequest,
)
from backend.app.domain.response_models import TurnResult
from backend.app.services.game_service import GameService

router = APIRouter()

# Populated by main.py at startup via set_game_service()
_game_service: GameService | None = None


def set_game_service(service: GameService) -> None:
    """Called once at startup to inject the game service."""
    global _game_service
    _game_service = service


def _get_service() -> GameService:
    """FastAPI dependency that returns the game service."""
    if _game_service is None:
        raise RuntimeError("GameService not initialised")
    return _game_service


def _turn_result_to_create_response(session_id: str, tr: TurnResult) -> CreateSessionResponse:
    """Map a TurnResult to the create/reset response DTO."""
    return CreateSessionResponse(
        session_id=session_id,
        speaker_type="narrator",
        speaker=tr.speaker,
        dialogue=tr.dialogue,
        location=tr.location,
        background_url=tr.background_url,
        portrait_url=tr.portrait_url,
        available_characters=tr.available_characters,
        available_exits=tr.available_exits,
        suggestions=tr.suggestions,
        game_finished=tr.game_finished,
    )


def _turn_result_to_submit_response(
    session_id: str, turn_index: int, tr: TurnResult,
) -> SubmitTurnResponse:
    """Map a TurnResult to the submit-turn response DTO."""
    return SubmitTurnResponse(
        session_id=session_id,
        turn_index=turn_index,
        speaker_type=tr.speaker_type,
        speaker=tr.speaker,
        dialogue=tr.dialogue,
        location=tr.location,
        background_url=tr.background_url,
        portrait_url=tr.portrait_url,
        available_characters=tr.available_characters,
        available_exits=tr.available_exits,
        suggestions=tr.suggestions,
        game_finished=tr.game_finished,
    )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    svc: GameService = Depends(_get_service),
) -> CreateSessionResponse:
    """Start a new game session and return the opening scene."""
    session_id, turn_result = svc.create_session("manor")
    return _turn_result_to_create_response(session_id, turn_result)


@router.post(
    "/sessions/{session_id}/turns", response_model=SubmitTurnResponse
)
async def submit_turn(
    session_id: str,
    body: SubmitTurnRequest,
    svc: GameService = Depends(_get_service),
) -> SubmitTurnResponse:
    """Accept player input and return the next dialogue turn."""
    try:
        turn_index, turn_result = svc.submit_turn(session_id, body.player_input)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    return _turn_result_to_submit_response(session_id, turn_index, turn_result)


@router.get(
    "/sessions/{session_id}/state", response_model=SessionStateResponse
)
async def get_state(
    session_id: str,
    svc: GameService = Depends(_get_service),
) -> SessionStateResponse:
    """Return the current session state snapshot."""
    try:
        gs = svc.get_state(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStateResponse(
        location=gs.location,
        addressed_character=gs.addressed_character,
        flags=FlagsResponse(
            archive_unlocked=gs.flags.archive_unlocked,
            game_finished=gs.flags.game_finished,
        ),
        steward_pressure=gs.conversation_state.steward_pressure,
        discovered_topics=gs.conversation_state.discovered_topics,
    )


@router.post(
    "/sessions/{session_id}/reset", response_model=ResetSessionResponse
)
async def reset_session(
    session_id: str,
    svc: GameService = Depends(_get_service),
) -> ResetSessionResponse:
    """Reset the session to the opening scene."""
    try:
        svc.get_state(session_id)  # validate exists
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    turn_result = svc.reset_session(session_id)
    resp = _turn_result_to_create_response(session_id, turn_result)
    return ResetSessionResponse(**resp.model_dump())


@router.put(
    "/sessions/{session_id}/addressed-character",
    response_model=SessionStateResponse,
)
async def switch_character(
    session_id: str,
    body: SwitchCharacterRequest,
    svc: GameService = Depends(_get_service),
) -> SessionStateResponse:
    """Change the addressed character. Rejects unknown character IDs with 422."""
    try:
        gs = svc.switch_addressed_character(session_id, body.character_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return SessionStateResponse(
        location=gs.location,
        addressed_character=gs.addressed_character,
        flags=FlagsResponse(
            archive_unlocked=gs.flags.archive_unlocked,
            game_finished=gs.flags.game_finished,
        ),
        steward_pressure=gs.conversation_state.steward_pressure,
        discovered_topics=gs.conversation_state.discovered_topics,
    )


@router.post(
    "/sessions/{session_id}/move", response_model=SubmitTurnResponse
)
async def move_to_location(
    session_id: str,
    body: MoveRequest,
    svc: GameService = Depends(_get_service),
) -> SubmitTurnResponse:
    """Move the player to a new location. Returns a narrator turn."""
    try:
        turn_index, turn_result = svc.handle_movement(session_id, body.target_location)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return _turn_result_to_submit_response(session_id, turn_index, turn_result)


# ---------------------------------------------------------------------------
# Trace endpoints (Phase 5)
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/traces/latest")
async def get_latest_trace(
    session_id: str,
    svc: GameService = Depends(_get_service),
) -> dict:
    """Return the latest trace for a session."""
    try:
        svc.get_state(session_id)  # validate session exists
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    trace = svc.get_latest_trace(session_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="No traces found")
    return trace


# ---------------------------------------------------------------------------
# Debug endpoints (Phase 2)
# ---------------------------------------------------------------------------


@router.get("/debug/scenario/{scenario_id}")
async def debug_scenario(scenario_id: str) -> dict:
    """Load and return a full scenario package as JSON (development only)."""
    from backend.app.core.config import get_settings
    from backend.app.core.validators import validate_scenario_package
    from backend.app.services.scenario_loader import ScenarioLoader

    loader = ScenarioLoader(base_path=get_settings().scenario_root_path)
    try:
        package = loader.load_scenario_package(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    errors = validate_scenario_package(package)
    return {
        "scenario": package.model_dump(),
        "validation_errors": errors,
    }
