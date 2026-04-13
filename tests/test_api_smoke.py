"""Phase 1 smoke tests — verify every endpoint returns the correct status and shape."""

# Every DTO field the frontend depends on is asserted here.
# If a field is renamed, removed, or re-typed, these tests break immediately.

CREATE_SESSION_FIELDS = {
    "session_id",
    "speaker_type",
    "speaker",
    "dialogue",
    "location",
    "background_url",
    "portrait_url",
    "available_characters",
    "available_exits",
    "suggestions",
    "game_finished",
}

SUBMIT_TURN_FIELDS = CREATE_SESSION_FIELDS | {"turn_index"}

STATE_FIELDS = {
    "location",
    "addressed_character",
    "flags",
    "steward_pressure",
    "discovered_topics",
}

FLAGS_FIELDS = {"archive_unlocked", "game_finished"}


def _create_session(client):
    """Helper: create a session and return the response JSON."""
    resp = client.post("/api/sessions")
    assert resp.status_code == 200
    return resp.json()


# ---------- POST /api/sessions ----------


def test_create_session(client):
    data = _create_session(client)
    assert CREATE_SESSION_FIELDS <= set(data.keys()), (
        f"Missing fields: {CREATE_SESSION_FIELDS - set(data.keys())}"
    )
    assert data["speaker_type"] == "narrator"
    assert isinstance(data["dialogue"], str) and len(data["dialogue"]) > 0
    assert isinstance(data["available_characters"], list)
    assert isinstance(data["suggestions"], list)
    assert data["game_finished"] is False


# ---------- POST /api/sessions/{id}/turns ----------


def test_submit_turn(client):
    session = _create_session(client)
    player_text = "Ask about the testament"
    resp = client.post(
        f"/api/sessions/{session['session_id']}/turns",
        json={"player_input": player_text},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert SUBMIT_TURN_FIELDS <= set(data.keys()), (
        f"Missing fields: {SUBMIT_TURN_FIELDS - set(data.keys())}"
    )
    assert data["session_id"] == session["session_id"]
    assert isinstance(data["turn_index"], int)
    assert data["speaker_type"] in ("character", "narrator")
    assert isinstance(data["speaker"], str)
    assert isinstance(data["dialogue"], str)
    assert player_text in data["dialogue"], "Mock should echo the player input"
    assert isinstance(data["available_characters"], list)
    assert isinstance(data["available_exits"], list)
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["game_finished"], bool)


# ---------- GET /api/sessions/{id}/state ----------


def test_get_state(client):
    session = _create_session(client)
    resp = client.get(f"/api/sessions/{session['session_id']}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert STATE_FIELDS <= set(data.keys()), (
        f"Missing fields: {STATE_FIELDS - set(data.keys())}"
    )
    assert FLAGS_FIELDS <= set(data["flags"].keys()), (
        f"Missing flags: {FLAGS_FIELDS - set(data['flags'].keys())}"
    )
    assert isinstance(data["flags"]["archive_unlocked"], bool)
    assert isinstance(data["flags"]["game_finished"], bool)
    assert isinstance(data["steward_pressure"], int)
    assert isinstance(data["discovered_topics"], list)


# ---------- POST /api/sessions/{id}/reset ----------


def test_reset_session(client):
    session = _create_session(client)
    resp = client.post(f"/api/sessions/{session['session_id']}/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert CREATE_SESSION_FIELDS <= set(data.keys()), (
        f"Missing fields: {CREATE_SESSION_FIELDS - set(data.keys())}"
    )
    # Reset preserves the same session ID
    assert data["session_id"] == session["session_id"]
    assert data["speaker_type"] == "narrator"
    assert isinstance(data["dialogue"], str)
    assert isinstance(data["suggestions"], list)


# ---------- PUT /api/sessions/{id}/addressed-character ----------


def test_switch_character(client):
    session = _create_session(client)
    resp = client.put(
        f"/api/sessions/{session['session_id']}/addressed-character",
        json={"character_id": "heir"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["addressed_character"] == "heir"


def test_switch_to_invalid_character_rejected(client):
    session = _create_session(client)
    resp = client.put(
        f"/api/sessions/{session['session_id']}/addressed-character",
        json={"character_id": "stranger"},
    )
    assert resp.status_code == 422


# ---------- POST /api/sessions/{id}/move ----------


def test_move_blocked_when_locked(client):
    session = _create_session(client)
    resp = client.post(
        f"/api/sessions/{session['session_id']}/move",
        json={"target_location": "archive"},
    )
    assert resp.status_code == 422


# ---------- 404 for unknown session ----------


def test_invalid_session_returns_404(client):
    resp = client.get("/api/sessions/nonexistent-id/state")
    assert resp.status_code == 404
