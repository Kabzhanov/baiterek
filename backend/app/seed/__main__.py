"""Entry point for `python -m app.seed` / `python -m app.seed --demo` (Makefile `seed`
and `demo-data` targets). `--demo` is accepted for Makefile compatibility; the MVP has
no separate demo-only dataset yet (map/analytics demo content is a later stage), so
both invocations currently run the same idempotent core seed.
"""
from __future__ import annotations

import argparse
import asyncio

from app.seed import run_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed organizations, dictionaries and demo services.")
    parser.add_argument("--demo", action="store_true", help="also seed demo-only content (currently a no-op extra)")
    parser.parse_args()

    summary = asyncio.run(run_seed())
    print(f"seed complete: {summary.describe()}")


if __name__ == "__main__":
    main()
