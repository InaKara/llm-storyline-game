import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture()
def client():
    # Reset mock sessions between tests
    from backend.app.api.routes import _mock_sessions

    _mock_sessions.clear()
    with TestClient(app) as c:
        yield c
