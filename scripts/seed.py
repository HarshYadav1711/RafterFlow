"""CLI: initialise schema and seed appendix reference data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.seed import run_seed  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed RafterFlow reference data from business_rules.json")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables, then seed the Appendix baseline (destructive).",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional SQLAlchemy URL override (defaults to DATABASE_URL from settings).",
    )
    args = parser.parse_args(argv)

    counts = run_seed(database_url=args.database_url, reset=args.reset)
    mode = "reset+seed" if args.reset else "idempotent seed"
    print(f"RafterFlow {mode} complete:")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
