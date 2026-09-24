"""Generate clearly flagged fictional observations in an existing local database."""
import argparse
from datetime import date
from pathlib import Path
import sys

# Direct execution from any PowerShell working directory; no PYTHONPATH setup.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError
from scripts.demo_data import DEFAULT_DATABASE_PATH, DEFAULT_SEED, DemoDataError, generate_demo_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Development only: generate 90 days of SYNTHETIC observations, never patient data.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed (default: 42).")
    parser.add_argument("--end-date", type=date.fromisoformat, help="Last UTC date, YYYY-MM-DD (default: yesterday UTC).")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH, help="Existing initialised SQLite file (default: application database).")
    args = parser.parse_args(argv)
    print(f"Development data only - all generated records are synthetic.\nDatabase: {args.database.resolve()}", flush=True)
    try:
        result = generate_demo_data(args.database, seed=args.seed, end_date=args.end_date)
    except (DemoDataError, SQLAlchemyError, OSError) as exc:
        print(f"No demo dataset was committed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated {result.generated} synthetic symptom records")
    print(f"Date range (UTC): {result.start_date} to {result.end_date}")
    print(f"Seed: {args.seed}")
    print(f"Real records preserved: {result.real_preserved}")
    print(f"Records with missing environmental values: {result.missing_environment}")
    print("These are fictional development records, not real health observations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
