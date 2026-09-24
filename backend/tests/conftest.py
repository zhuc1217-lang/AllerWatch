from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    """Mock the real transport, leaving explicit MockTransport fixtures unaffected."""
    async def unavailable(self, request):
        raise httpx.ConnectError("Offline test: no external connections", request=request)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", unavailable)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "isolated" / "test.sqlite3"


@pytest.fixture
def client(database_path: Path):
    with TestClient(create_app(database_path)) as test_client:
        yield test_client


@pytest.fixture
def valid_record() -> dict:
    return {
        "timestamp": "2026-09-17T08:30:00+08:00",
        "nasal_congestion": 3,
        "sneezing": 2,
        "runny_nose": 1,
        "nasal_itching": 0,
        "eye_symptoms": 2,
        "overall_severity": 7,
        "medication_taken": True,
        "notes": "Synthetic test observation.",
        "is_synthetic": True,
    }
