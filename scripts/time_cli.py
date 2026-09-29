"""Time Littera CLI commands against an existing work (scale spike, littera-496).

    python scripts/time_cli.py WORK_DIR [--runs 3]

Postgres is started first so each figure is the command itself, not the
embedded server boot; the boot is reported on its own line.
"""

from __future__ import annotations

import argparse
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

LITTERA = str(Path(sys.executable).with_name("littera"))

COMMANDS = [
    "--help",  # baseline: interpreter + imports, no database
    "status",
    "wc",
    "doc list",
    "section list 36",  # a chapter mid-book
    "block list 150",  # a section mid-book (global index)
    "export json",
    "export markdown",
    "export markdown --compile",
]


def timed(cmd: str, cwd: Path) -> tuple[float, int]:
    start = time.perf_counter()
    res = subprocess.run(
        [LITTERA, *shlex.split(cmd)], cwd=cwd, capture_output=True, text=True, check=False
    )
    elapsed = time.perf_counter() - start
    if res.returncode != 0:
        raise SystemExit(f"`littera {cmd}` failed:\n{res.stdout}\n{res.stderr}")
    return elapsed, len(res.stdout.encode())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    subprocess.run(
        [LITTERA, "mntn-db-stop"], cwd=args.work_dir, capture_output=True, check=False
    )
    boot, _ = timed("mntn-db-start", args.work_dir)
    print(f"{'mntn-db-start (cold boot)':32} {boot:7.2f}s")

    for cmd in COMMANDS:
        samples, size = [], 0
        for _ in range(args.runs):
            t, size = timed(cmd, args.work_dir)
            samples.append(t)
        print(
            f"{'littera ' + cmd:32} {statistics.median(samples):7.2f}s"
            f"  (min {min(samples):.2f}, max {max(samples):.2f}, {size / 1024:,.0f} KiB out)"
        )


if __name__ == "__main__":
    main()
