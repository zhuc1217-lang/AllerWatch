from contextlib import closing
from datetime import date
import hashlib
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from app.config import DEFAULT_DATABASE_PATH, DEFAULT_DEMO_DATABASE_PATH, REPOSITORY_ROOT, Settings, get_settings
from app.daily_health import DailyHealthRecord
from app.main import create_app
from app.models import SymptomRecord
from app import public_demo
from scripts import demo_data


@pytest.fixture
def demo_settings():
    return Settings(public_demo_mode=True, frontend_origin="https://portfolio.example")


@pytest.fixture(autouse=True)
def fixed_demo_end(monkeypatch):
    monkeypatch.setattr(demo_data, "default_end_date", lambda: date(2025, 3, 31))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_default_paths_are_separate_and_relative_paths_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Settings().resolved_database_path() == DEFAULT_DATABASE_PATH
    assert Settings(public_demo_mode=True).resolved_database_path() == DEFAULT_DEMO_DATABASE_PATH
    assert Settings(database_path=Path("data/test.sqlite3")).resolved_database_path() == REPOSITORY_ROOT / "data/test.sqlite3"


def test_environment_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "public.sqlite3"))
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://demo.example/")
    settings = get_settings()
    assert settings.public_demo_mode is True
    assert settings.frontend_origin == "https://demo.example"
    assert settings.resolved_database_path() == tmp_path / "public.sqlite3"
    with TestClient(create_app()) as client:
        assert client.get("/config").json() == {"public_demo_mode": True}
        assert client.get("/symptoms").json()


@pytest.mark.parametrize("origin", ["*", "https://*.example", "https://demo.example/path", "https://u:p@demo.example", "javascript:alert(1)", "https://demo.example?a=1"])
def test_origin_is_one_exact_http_origin(origin):
    with pytest.raises(ValidationError):
        Settings(frontend_origin=origin)


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "https://portfolio.example"])
def test_cors_preflight_and_response(database_path, demo_settings, origin):
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        preflight = client.options("/symptoms", headers={"Origin": origin,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert client.get("/health", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in preflight.headers
        denied = client.options("/symptoms", headers={"Origin": "https://unlisted.example", "Access-Control-Request-Method": "POST"})
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


def test_fresh_demo_is_seeded_once_and_only_synthetic(database_path, demo_settings):
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        symptoms = client.get("/symptoms").json()
        daily = client.get("/daily-health?dataset=all").json()["records"]
        assert 90 <= len(symptoms) <= 180
        assert 90 <= len(daily) <= 91
        assert all(r["is_synthetic"] for r in symptoms + daily)
        assert len({r["timestamp"][:10] for r in symptoms}) == 90
        assert all(r["tnss"] == sum(r[k] for k in demo_data.NASAL_FIELDS) for r in symptoms)
        assert client.get("/analysis/descriptive?dataset=real_only").json()["record_count"] == 0
        assert client.get("/analysis/risk-model?dataset=all").status_code == 422
        assert client.get("/health").json() == {"status": "ok"}
    before = digest(database_path)
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        assert client.get("/symptoms").json() == symptoms
        assert client.get("/daily-health?dataset=all").json()["records"] == daily
    assert digest(database_path) == before


@pytest.mark.parametrize("remove_model", [SymptomRecord, DailyHealthRecord])
def test_partially_populated_demo_is_not_reseeded(database_path, demo_settings, remove_model):
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        with client.app.state.session_factory() as session:
            session.execute(delete(remove_model))
            session.commit()
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        endpoint = "/symptoms" if remove_model is SymptomRecord else "/daily-health?dataset=all"
        data = client.get(endpoint).json()
        assert (data if isinstance(data, list) else data["records"]) == []


def test_fully_empty_existing_demo_is_seeded_again(database_path, demo_settings):
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        with client.app.state.session_factory() as session:
            session.execute(delete(SymptomRecord))
            session.execute(delete(DailyHealthRecord))
            session.commit()
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        assert len(client.get("/symptoms").json()) >= 90


def test_local_mode_does_not_seed_and_keeps_real_submission(database_path, valid_record):
    with TestClient(create_app(database_path, settings=Settings())) as client:
        assert client.get("/config").json() == {"public_demo_mode": False}
        assert client.get("/symptoms").json() == []
        response = client.post("/symptoms", json=valid_record | {"is_synthetic": False})
        assert response.status_code == 201
        assert response.json()["is_synthetic"] is False


@pytest.mark.parametrize("supplied", [None, False, True])
def test_demo_forces_synthetic_symptoms_despite_client_flag(database_path, demo_settings, valid_record, supplied):
    payload = dict(valid_record)
    payload.pop("is_synthetic")
    if supplied is not None:
        payload["is_synthetic"] = supplied
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        response = client.post("/symptoms", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["is_synthetic"] is True
        assert data["tnss"] == 6
        assert data["pm2_5"] is None  # Offline fixture; never fabricate exposure.
        assert client.get(f'/symptoms/{data["id"]}').json() == data


def test_demo_daily_create_read_update_cannot_write_real(database_path, demo_settings):
    values = {"sleep_duration_hours": 7.5, "sleep_quality": 4, "stress_level": 2, "exercise_minutes": 0, "notes": None}
    with TestClient(create_app(database_path, settings=demo_settings)) as client:
        payload = values | {"date": "2020-01-01", "is_synthetic": False}
        created = client.post("/daily-health", json=payload)
        assert created.status_code == 201
        assert created.json()["is_synthetic"] is True
        assert client.post("/daily-health", json=payload).status_code == 409
        assert client.get("/daily-health/2020-01-01").json() == created.json()
        updated = client.put("/daily-health/2020-01-01?is_synthetic=false", json=values | {"sleep_duration_hours": 6.5})
        assert updated.status_code == 200
        assert updated.json()["id"] == created.json()["id"]
        assert updated.json()["is_synthetic"] is True
        assert updated.json()["sleep_duration_hours"] == 6.5
        assert client.get("/daily-health?dataset=real_only").json()["records"] == []


def test_private_default_and_private_directory_rejected_before_connect(demo_settings):
    for path in [DEFAULT_DATABASE_PATH, DEFAULT_DATABASE_PATH.parent / "another.sqlite3"]:
        with pytest.raises(RuntimeError, match="private"):
            create_app(path, settings=demo_settings)


def test_unknown_existing_database_is_never_migrated_seeded_or_read(database_path, demo_settings, valid_record):
    with TestClient(create_app(database_path, settings=Settings())) as client:
        client.post("/symptoms", json=valid_record | {"is_synthetic": False})
    before = digest(database_path)
    with pytest.raises(RuntimeError, match="not an AllerWatch public demo"):
        create_app(database_path, settings=demo_settings)
    assert digest(database_path) == before


def test_private_hard_link_is_rejected(tmp_path, demo_settings, monkeypatch):
    private = tmp_path / "private" / "original.sqlite3"
    private.parent.mkdir()
    private.write_bytes(b"private fixture")
    alias = tmp_path / "alias.sqlite3"
    alias.hardlink_to(private)
    monkeypatch.setattr(public_demo, "DEFAULT_DATABASE_PATH", private)
    with pytest.raises(RuntimeError, match="private"):
        create_app(alias, settings=demo_settings)
    assert private.read_bytes() == b"private fixture"


def test_real_row_in_marked_demo_refuses_service_without_deleting(database_path, demo_settings):
    with TestClient(create_app(database_path, settings=demo_settings)):
        pass
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("UPDATE symptom_records SET is_synthetic=0 WHERE id=1")
        connection.commit()
    before = digest(database_path)
    with pytest.raises(RuntimeError, match="contains real records"):
        with TestClient(create_app(database_path, settings=demo_settings)):
            pass
    assert digest(database_path) == before


def test_seed_failure_does_not_commit_partial_health_records(database_path, demo_settings, monkeypatch):
    from scripts import daily_demo_data
    def fail(*args, **kwargs):
        raise RuntimeError("simulated generator failure")
    monkeypatch.setattr(daily_demo_data, "build_daily_demo", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        with TestClient(create_app(database_path, settings=demo_settings)):
            pass
    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("SELECT count(*) FROM symptom_records").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM daily_health_records").fetchone() == (0,)
