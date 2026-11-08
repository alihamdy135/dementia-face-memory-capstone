from __future__ import annotations

import argparse
from pathlib import Path

from .poster_artifacts import write_poster_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Create clearly marked pending poster files")
    parser.add_argument("output_dir", nargs="?", type=Path, default=Path("reports/public"))
    args = parser.parse_args()
    write_poster_artifacts(args.output_dir)
    print(f"Pending, non-measured poster templates written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
