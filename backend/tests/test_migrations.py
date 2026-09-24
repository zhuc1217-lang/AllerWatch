from contextlib import closing
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.database import create_database_engine, initialize_database
from app.main import create_app
from app import migrations

# Exact pre-snapshot table structure, independent of the new SQLAlchemy model.
LEGACY_TABLE_SQL = "CREATE TABLE symptom_records (\n\tid INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, \n\ttimestamp DATETIME NOT NULL, \n\tnasal_congestion INTEGER NOT NULL, \n\tsneezing INTEGER NOT NULL, \n\trunny_nose INTEGER NOT NULL, \n\tnasal_itching INTEGER NOT NULL, \n\teye_symptoms INTEGER NOT NULL, \n\toverall_severity INTEGER NOT NULL, \n\tmedication_taken BOOLEAN NOT NULL, \n\tnotes TEXT, \n\tis_synthetic BOOLEAN DEFAULT 0 NOT NULL, \n\tCONSTRAINT ck_symptom_records_nasal_congestion CHECK (typeof(nasal_congestion) = 'integer' AND nasal_congestion BETWEEN 0 AND 3), \n\tCONSTRAINT ck_symptom_records_sneezing CHECK (typeof(sneezing) = 'integer' AND sneezing BETWEEN 0 AND 3), \n\tCONSTRAINT ck_symptom_records_runny_nose CHECK (typeof(runny_nose) = 'integer' AND runny_nose BETWEEN 0 AND 3), \n\tCONSTRAINT ck_symptom_records_nasal_itching CHECK (typeof(nasal_itching) = 'integer' AND nasal_itching BETWEEN 0 AND 3), \n\tCONSTRAINT ck_symptom_records_eye_symptoms CHECK (typeof(eye_symptoms) = 'integer' AND eye_symptoms BETWEEN 0 AND 3), \n\tCONSTRAINT ck_symptom_records_overall_severity CHECK (typeof(overall_severity) = 'integer' AND overall_severity BETWEEN 0 AND 10), \n\tCONSTRAINT ck_medication_taken CHECK (medication_taken IN (0, 1)), \n\tCONSTRAINT ck_is_synthetic CHECK (is_synthetic IN (0, 1))\n)"
LEGACY_ROWS = [
    (7, "2026-09-17 00:30:00.000000", 3, 2, 1, 0, 2, 7, 1, "Legacy observation — 鼻炎", 0),
    (11, "2026-09-18 03:30:00.000000", 0, 0, 0, 0, 3, 4, 0, None, 1),
]
LEGACY_COLUMNS = "id, timestamp, nasal_congestion, sneezing, runny_nose, nasal_itching, eye_symptoms, overall_severity, medication_taken, notes, is_synthetic"


@pytest.fixture
def legacy_database(database_path):
    database_path.parent.mkdir(parents=True)
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(LEGACY_TABLE_SQL)
        connection.execute("CREATE INDEX ix_symptom_records_timestamp ON symptom_records (timestamp)")
        connection.executemany("INSERT INTO symptom_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", LEGACY_ROWS)
    return database_path


def rows_at(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(f"SELECT {LEGACY_COLUMNS} FROM symptom_records ORDER BY id").fetchall()


@pytest.mark.parametrize("journal_mode", ["delete", "wal"])
def test_migration_preserves_records_constraints_index_and_backup(legacy_database, valid_record, journal_mode):
    with closing(sqlite3.connect(legacy_database)) as connection:
        connection.execute(f"PRAGMA journal_mode={journal_mode}")
        with TestClient(create_app(legacy_database)) as client:
            records = client.get("/symptoms").json()
            assert [r["id"] for r in records] == [11, 7]
            assert [r["tnss"] for r in records] == [0, 6]
            assert records[1]["notes"] == LEGACY_ROWS[0][9]
            for record in records:
                assert all(record[field] is None for field in migrations.ENVIRONMENT_COLUMNS)
                assert client.get(f"/symptoms/{record['id']}").json() == record
            assert rows_at(legacy_database) == LEGACY_ROWS
            columns = {row[1]: row for row in connection.execute("PRAGMA table_info(symptom_records)")}
            assert all(columns[field][3] == 0 and columns[field][4] is None for field in migrations.ENVIRONMENT_COLUMNS)
            assert connection.execute("SELECT name FROM sqlite_master WHERE name='ix_symptom_records_timestamp'").fetchone()
            with pytest.raises(sqlite3.IntegrityError):
                with connection:
                    connection.execute("UPDATE symptom_records SET sneezing=4 WHERE id=7")
            created = client.post("/symptoms", json=valid_record).json()
            assert created["id"] == 12
    backups = list((legacy_database.parent / "backups").glob("*.sqlite3"))
    assert len(backups) == 1 and rows_at(backups[0]) == LEGACY_ROWS
    with closing(sqlite3.connect(backups[0])) as backup:
        assert len(backup.execute("PRAGMA table_info(symptom_records)").fetchall()) == 11
    with TestClient(create_app(legacy_database)) as restarted:
        assert len(restarted.get("/symptoms").json()) == 3
    assert list((legacy_database.parent / "backups").glob("*.sqlite3")) == backups


def test_new_database_needs_no_migration_backup(database_path):
    engine = create_database_engine(database_path)
    try:
        initialize_database(engine)
        initialize_database(engine)
        assert not (database_path.parent / "backups").exists()
    finally:
        engine.dispose()


def test_partially_extended_database_preserves_existing_snapshot_values(legacy_database):
    with closing(sqlite3.connect(legacy_database)) as connection, connection:
        connection.execute("ALTER TABLE symptom_records ADD COLUMN temperature_c FLOAT")
        connection.execute("UPDATE symptom_records SET temperature_c=0 WHERE id=7")
    with TestClient(create_app(legacy_database)) as client:
        assert client.get("/symptoms/7").json()["temperature_c"] == 0
        assert client.get("/symptoms/11").json()["temperature_c"] is None
    assert rows_at(legacy_database) == LEGACY_ROWS


def test_failed_backup_prevents_any_schema_change(legacy_database, monkeypatch):
    def fail_backup(path):
        raise OSError("Simulated unwritable backup directory")
    monkeypatch.setattr(migrations, "_backup_database", fail_backup)
    engine = create_database_engine(legacy_database)
    try:
        with pytest.raises(OSError):
            initialize_database(engine)
    finally:
        engine.dispose()
    assert rows_at(legacy_database) == LEGACY_ROWS
    with closing(sqlite3.connect(legacy_database)) as connection:
        assert len(connection.execute("PRAGMA table_info(symptom_records)").fetchall()) == 11


def test_failed_ddl_rolls_back_all_column_additions(legacy_database, monkeypatch):
    monkeypatch.setattr(migrations, "ENVIRONMENT_COLUMNS", {
        "temperature_c": "FLOAT", "invalid_test_column": "FLOAT NOT NULL",
    })
    engine = create_database_engine(legacy_database)
    try:
        with pytest.raises(Exception, match="NOT NULL"):
            initialize_database(engine)
    finally:
        engine.dispose()
    with closing(sqlite3.connect(legacy_database)) as connection:
        assert len(connection.execute("PRAGMA table_info(symptom_records)").fetchall()) == 11
    assert rows_at(legacy_database) == LEGACY_ROWS
    backups = list((legacy_database.parent / "backups").glob("*.sqlite3"))
    assert len(backups) == 1 and rows_at(backups[0]) == LEGACY_ROWS
