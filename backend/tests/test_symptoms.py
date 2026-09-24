from contextlib import closing
from datetime import UTC, datetime
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.main import create_app

SYMPTOM_FIELDS = (
    "nasal_congestion",
    "sneezing",
    "runny_nose",
    "nasal_itching",
    "eye_symptoms",
)


def test_health_endpoint_still_works(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_valid_symptom_record(client, valid_record):
    response = client.post("/symptoms", json=valid_record)

    assert response.status_code == 201
    record = response.json()
    assert record == {
        **valid_record,
        "id": record["id"],
        "received_at": record["received_at"],
        "timestamp": "2026-09-17T00:30:00Z",
        "tnss": 6,
        "temperature_c": None,
        "relative_humidity": None,
        "pm2_5": None,
        "pm10": None,
        "us_aqi": None,
        "environment_timestamp": None,
        "weather_timestamp": None,
        "air_quality_timestamp": None,
        "environment_latitude": None,
        "environment_longitude": None,
        "environment_time_eligible": {field: False for field in
            ("pm2_5", "pm10", "us_aqi", "relative_humidity", "temperature_c")},
    }
    assert isinstance(record["id"], int)
    assert record["id"] > 0


def test_optional_fields_and_current_utc_timestamp(client, valid_record):
    for field in ("timestamp", "notes", "is_synthetic"):
        valid_record.pop(field)
    before = datetime.now(UTC)
    response = client.post("/symptoms", json=valid_record)
    after = datetime.now(UTC)

    assert response.status_code == 201
    record = response.json()
    timestamp = datetime.fromisoformat(record["timestamp"])
    assert before <= timestamp <= after
    assert timestamp.utcoffset().total_seconds() == 0
    assert record["notes"] is None
    assert record["is_synthetic"] is False


@pytest.mark.parametrize("field", SYMPTOM_FIELDS)
@pytest.mark.parametrize("value", [-1, 4, 1.5, "2", True, None])
def test_invalid_symptom_score_returns_422(client, valid_record, field, value):
    valid_record[field] = value
    response = client.post("/symptoms", json=valid_record)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert client.get("/symptoms").json() == []


@pytest.mark.parametrize("value", [-1, 11, 1.5, "7", True, None])
def test_invalid_overall_severity_returns_422(client, valid_record, value):
    valid_record["overall_severity"] = value
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 422
    assert client.get("/symptoms").json() == []


@pytest.mark.parametrize("value", [0, 10])
def test_overall_severity_boundaries_are_valid(client, valid_record, value):
    valid_record["overall_severity"] = value
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 201
    assert response.json()["overall_severity"] == value


@pytest.mark.parametrize("field", [*SYMPTOM_FIELDS, "overall_severity", "medication_taken"])
def test_required_fields_cannot_be_omitted(client, valid_record, field):
    valid_record.pop(field)
    assert client.post("/symptoms", json=valid_record).status_code == 422


@pytest.mark.parametrize("field", ["medication_taken", "is_synthetic"])
@pytest.mark.parametrize("value", ["false", 0, None])
def test_boolean_fields_reject_coercion(client, valid_record, field, value):
    valid_record[field] = value
    assert client.post("/symptoms", json=valid_record).status_code == 422


@pytest.mark.parametrize("value", [True, False])
def test_boolean_fields_round_trip(client, valid_record, value):
    valid_record.update(medication_taken=value, is_synthetic=value)
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 201
    stored = client.get(f"/symptoms/{response.json()['id']}").json()
    assert stored["medication_taken"] is value
    assert stored["is_synthetic"] is value


@pytest.mark.parametrize("scores,expected", [((0, 0, 0, 0), 0), ((3, 3, 3, 3), 12), ((1, 2, 3, 1), 7)])
def test_tnss_calculation(client, valid_record, scores, expected):
    valid_record.update(zip(SYMPTOM_FIELDS[:4], scores))
    valid_record.update(eye_symptoms=3, overall_severity=10)
    response = client.post("/symptoms", json=valid_record)
    assert response.status_code == 201
    record = response.json()
    assert record["tnss"] == expected
    assert client.get(f"/symptoms/{record['id']}").json()["tnss"] == expected


@pytest.mark.parametrize("extra", [{"tnss": 12}, {"TNSS": 12}, {"id": 100}])
def test_server_managed_fields_cannot_be_supplied(client, valid_record, extra):
    response = client.post("/symptoms", json={**valid_record, **extra})
    assert response.status_code == 422
    assert any(error["type"] == "extra_forbidden" for error in response.json()["detail"])
    assert client.get("/symptoms").json() == []


@pytest.mark.parametrize("value", ["2026-09-17T08:30:00", "not-a-date", None])
def test_timestamp_must_be_valid_and_timezone_aware(client, valid_record, value):
    valid_record["timestamp"] = value
    assert client.post("/symptoms", json=valid_record).status_code == 422


def test_empty_record_list(client):
    response = client.get("/symptoms")
    assert response.status_code == 200
    assert response.json() == []


def test_retrieve_records_newest_first_with_stable_ties(client, valid_record):
    first = client.post("/symptoms", json=valid_record).json()
    second = client.post("/symptoms", json=valid_record).json()
    older = client.post(
        "/symptoms", json={**valid_record, "timestamp": "2026-09-16T00:00:00Z"}
    ).json()

    response = client.get("/symptoms")
    assert response.status_code == 200
    assert response.json() == [second, first, older]
    for record in (first, second, older):
        fetched = client.get(f"/symptoms/{record['id']}")
        assert fetched.status_code == 200
        assert fetched.json() == record


def test_missing_records_return_404(client):
    for method in (client.get, client.delete):
        response = method("/symptoms/999")
        assert response.status_code == 404
        assert response.json() == {"detail": "Symptom record not found"}


@pytest.mark.parametrize("record_id", ["abc", "0", "-1", str(2**63)])
def test_invalid_ids_return_422(client, record_id):
    assert client.get(f"/symptoms/{record_id}").status_code == 422
    assert client.delete(f"/symptoms/{record_id}").status_code == 422


def test_delete_record_returns_empty_204_and_preserves_other_records(client, valid_record):
    first = client.post("/symptoms", json=valid_record).json()
    second = client.post("/symptoms", json=valid_record).json()

    response = client.delete(f"/symptoms/{first['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/symptoms/{first['id']}").status_code == 404
    assert client.delete(f"/symptoms/{first['id']}").status_code == 404
    assert client.get("/symptoms").json() == [second]


def test_database_initialization_and_persistence_across_restarts(database_path, valid_record):
    application = create_app(database_path)
    assert not database_path.exists()

    with TestClient(application) as client:
        assert database_path.is_file()
        created = client.post("/symptoms", json=valid_record).json()

    with TestClient(create_app(database_path)) as restarted:
        response = restarted.get(f"/symptoms/{created['id']}")
        assert response.status_code == 200
        assert response.json() == created
        assert restarted.delete(f"/symptoms/{created['id']}").status_code == 204

    with TestClient(create_app(database_path)) as restarted_again:
        assert restarted_again.get("/symptoms").json() == []


def test_notes_allow_null_and_unicode(client, valid_record):
    for notes in (None, "Rhinitis diary — 鼻炎"):
        response = client.post("/symptoms", json={**valid_record, "notes": notes})
        assert response.status_code == 201
        assert response.json()["notes"] == notes


@pytest.mark.parametrize(
    "field,value",
    [("nasal_congestion", -1), ("eye_symptoms", 4), ("sneezing", 1.5),
     ("overall_severity", 11), ("medication_taken", 2), ("is_synthetic", 2)],
)
def test_sqlite_constraints_protect_data_without_api_validation(
    client, database_path, valid_record, field, value
):
    created = client.post("/symptoms", json=valid_record).json()
    with closing(sqlite3.connect(database_path)) as connection, connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE symptom_records SET {field} = ? WHERE id = ?", (value, created["id"])
            )
    assert client.get(f"/symptoms/{created['id']}").json() == created


def test_tnss_has_no_storage_column_and_is_recomputed(client, database_path, valid_record):
    created = client.post("/symptoms", json=valid_record).json()
    with closing(sqlite3.connect(database_path)) as connection, connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(symptom_records)")}
        assert "tnss" not in columns
        connection.execute(
            "UPDATE symptom_records SET nasal_itching = 3 WHERE id = ?", (created["id"],)
        )
    assert client.get(f"/symptoms/{created['id']}").json()["tnss"] == 9
