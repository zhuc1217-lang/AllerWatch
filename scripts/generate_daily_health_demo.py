"""Generate only synthetic daily-health summaries alongside existing synthetic symptoms."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError
from scripts.daily_demo_data import DEFAULT_DATABASE_PATH, DEFAULT_SEED, DemoDataError, generate_daily_demo


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate fictional daily-health data without changing symptom observations.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    try:
        summary = generate_daily_demo(args.database, seed=args.seed)
    except (DemoDataError, SQLAlchemyError, OSError) as exc:
        print(f"No daily demo data committed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated {summary.generated} synthetic daily-health records")
    print(f"Study-date range: {summary.start_date} to {summary.end_date}")
    print(f"Real daily-health records preserved: {summary.real_preserved}")
    print("Synthetic development data only; existing symptom records unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
