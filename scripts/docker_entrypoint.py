"""Container entrypoint: idempotent seed, then Uvicorn."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.seed import run_seed  # noqa: E402


def main() -> None:
    # Fresh named volumes start empty; idempotent seed loads the Appendix baseline.
    counts = run_seed(reset=False)
    print("RafterFlow container seed complete:", flush=True)
    for name, count in counts.items():
        print(f"  {name}: {count}", flush=True)

    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
    )


if __name__ == "__main__":
    main()
