import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.app.api.dto import (
    CreateSessionResponse,
    FlagsResponse,
    ResetSessionResponse,
    SessionStateResponse,
    SubmitTurnRequest,
    SubmitTurnResponse,
    SwitchCharacterRequest,
)

# Characters valid at the mock stage — replaced by scenario data in Phase 3
_VALID_CHARACTERS = {"steward", "heir"}

router = APIRouter()

# In-memory set of valid mock session IDs (replaced by real session store in Phase 3)
_mock_sessions: set[str] = set()

MOCK_SESSION_DATA = {
    "speaker": "Narrator",
    "dialogue": (
        "You step into the study. The air smells of old paper and polished wood. "
        "Mr. Hargrove, the steward, stands behind the desk. "
        "Lady Ashworth, the heir, watches from a chair by the window."
    ),
    "location": "study",
    "background_url": "",
    "available_characters": ["steward", "heir"],
    "available_exits": [],
    "suggestions": [
        "Ask the steward about the testament",
        "Ask the heir what she thinks happened",
        "Look around the study",
    ],
}


def _validate_session(session_id: str) -> None:
    """Raise 404 if *session_id* is not in the mock session store."""
    if session_id not in _mock_sessions:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    """Start a new game session and return the opening scene."""
    session_id = str(uuid.uuid4())
    _mock_sessions.add(session_id)
    return CreateSessionResponse(
        session_id=session_id,
        **MOCK_SESSION_DATA,
    )


@router.post(
    "/sessions/{session_id}/turns", response_model=SubmitTurnResponse
)
async def submit_turn(
    session_id: str, body: SubmitTurnRequest
) -> SubmitTurnResponse:
    """Accept player input and return the next dialogue turn (mock)."""
    _validate_session(session_id)
    return SubmitTurnResponse(
        session_id=session_id,
        turn_index=1,
        speaker_type="character",
        speaker="Mr. Hargrove",
        dialogue=f"[Mock — received: '{body.player_input}'] The steward regards you coolly. 'The testament will surface in due course.'",
        location="study",
        background_url="",
        portrait_url="",
        available_characters=["steward", "heir"],
        available_exits=[],
        suggestions=[
            "Press the steward further",
            "Ask the heir if she trusts the steward",
            "Accuse the steward of hiding the testament",
        ],
    )


@router.get(
    "/sessions/{session_id}/state", response_model=SessionStateResponse
)
async def get_state(session_id: str) -> SessionStateResponse:
    """Return the current session state snapshot."""
    _validate_session(session_id)
    return SessionStateResponse(
        location="study",
        addressed_character="steward",
        flags=FlagsResponse(),
        steward_pressure=0,
        discovered_topics=[],
    )


@router.post(
    "/sessions/{session_id}/reset", response_model=ResetSessionResponse
)
async def reset_session(session_id: str) -> ResetSessionResponse:
    """Reset the session to the opening scene."""
    _validate_session(session_id)
    return ResetSessionResponse(
        session_id=session_id,
        **MOCK_SESSION_DATA,
    )


@router.put(
    "/sessions/{session_id}/addressed-character",
    response_model=SessionStateResponse,
)
async def switch_character(
    session_id: str, body: SwitchCharacterRequest
) -> SessionStateResponse:
    """Change the addressed character. Rejects unknown character IDs with 422."""
    _validate_session(session_id)
    if body.character_id not in _VALID_CHARACTERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown character '{body.character_id}'. Valid: {sorted(_VALID_CHARACTERS)}",
        )
    return SessionStateResponse(
        location="study",
        addressed_character=body.character_id,
        flags=FlagsResponse(),
        steward_pressure=0,
        discovered_topics=[],
    )


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
