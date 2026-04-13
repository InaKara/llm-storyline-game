import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, store


@pytest.fixture()
def client():
    # Clear all sessions between tests for isolation
    store._sessions.clear()
    with TestClient(app) as c:
        yield c
