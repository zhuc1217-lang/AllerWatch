"""Delete only explicitly synthetic observations; never reset the database."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError
from scripts.demo_data import DEFAULT_DATABASE_PATH, DemoDataError, delete_demo_data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete ONLY records where is_synthetic=true; preserve all real observations.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH, help="Existing initialised SQLite file (default: application database).")
    parser.add_argument("--daily-health", action="store_true", help="Delete ONLY synthetic daily-health records; leave all symptoms unchanged.")
    args = parser.parse_args(argv)
    print(f"Database: {args.database.resolve()}", flush=True)
    try:
        if args.daily_health:
            from scripts.daily_demo_data import delete_daily_demo
            deleted, real = delete_daily_demo(args.database, report=lambda message: print(message, flush=True))
        else:
            deleted, real = delete_demo_data(args.database, report=lambda message: print(message, flush=True))
    except (DemoDataError, SQLAlchemyError, OSError) as exc:
        print(f"No deletion was committed: {exc}", file=sys.stderr)
        return 1
    print(f"Deleted {deleted} synthetic {'daily-health' if args.daily_health else 'symptom'} records")
    print(f"Real records preserved: {real}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
