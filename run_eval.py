#!/usr/bin/env python3
"""
Appendix F evaluation runner.

Black-box HTTP client: sends every assessment message in order to a running
RafterFlow service and writes eval.md from the real responses.

This command does not touch the application database. Start the service from a
fresh Appendix-seeded baseline before running (exact reproducible startup flow
is Phase 6):

  python scripts/seed.py --reset
  uvicorn app.main:app --reload
  python run_eval.py

Usage:
  python run_eval.py
  python run_eval.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evaluation.runner import EvalRunError, resolve_base_url, run_evaluation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Appendix F evaluation → eval.md")
    parser.add_argument(
        "--base-url",
        default=None,
        help="RafterFlow base URL (default EVAL_BASE_URL or http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--output",
        default="eval.md",
        help="Output markdown path (default: eval.md)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout seconds per enquiry (default: 120)",
    )
    args = parser.parse_args(argv)

    base_url = resolve_base_url(args.base_url)
    try:
        results = run_evaluation(
            base_url=base_url,
            output_path=args.output,
            timeout=args.timeout,
        )
    except EvalRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    failed = sum(1 for r in results for c in r.checks if not c.passed)
    print(f"Wrote {args.output} ({len(results)} cases, {failed} failed checks).")
    print(f"Target: {base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
