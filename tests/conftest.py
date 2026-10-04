from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_file = tmp_path / "projectbridge-tests.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_file.as_posix()}")
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:5173")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_client(client):
    response = client.post("/api/v1/demo/session")
    assert response.status_code == 200
    return client


@pytest.fixture
def canonical_project(session_client):
    from app.drafts import CS_CLUB_EXAMPLE_IDEA, CS_CLUB_EXAMPLE_TITLE

    response = session_client.post("/api/v1/projects", json={
        "client_request_id": "canonical-test-project",
        "title": CS_CLUB_EXAMPLE_TITLE,
        "idea": CS_CLUB_EXAMPLE_IDEA,
        "desired_team_size": 4,
    })
    assert response.status_code == 201
    return response.json()["project"]
