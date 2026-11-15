#!/usr/bin/env python3
"""
Pick random gameplay testers from a curated list of users.

Used by the "Create Gameplay Test Report" workflow and by administrators who
need to reroll a tester assignment. Prints one login per line.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

DEFAULT_COUNT = 2
DEFAULT_USERS_FILE = Path(__file__).resolve().parent / "gameplay-testers.txt"


def positive_int(value: str) -> int:
    """Return value as a positive integer or raise an argparse error."""
    try:
        count = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error

    if count < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")

    return count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Pick random gameplay testers from a curated list of users.",
        epilog=(
            'Empty lines and lines starting with "#" are ignored. Bots are '
            "always excluded. The TESTERS_FILE environment variable is used "
            "when --file is omitted."
        ),
    )
    parser.add_argument(
        "--count",
        type=positive_int,
        default=DEFAULT_COUNT,
        help="Number of testers to pick. Defaults to 2.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="LOGINS",
        help="Comma-separated logins to exclude. May be repeated.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help=(
            "File with one GitHub login per line. Defaults to "
            "scripts/gameplay-testers.txt next to this script."
        ),
    )
    return parser.parse_args(argv)


def parse_excludes(values: list[str]) -> set[str]:
    """Return the normalized set of excluded logins."""
    excluded = set()
    for value in values:
        for login in value.split(","):
            login = login.strip()
            if login:
                excluded.add(login.casefold())
    return excluded


def read_candidates(users_file: Path, excluded: set[str]) -> list[str]:
    """Read, filter, and deduplicate tester logins from users_file."""
    candidates = []
    seen = set()

    for line in users_file.read_text(encoding="utf-8").splitlines():
        login = line.strip()

        if not login or login.startswith("#"):
            continue
        if login.endswith("[bot]"):
            continue

        key = login.casefold()
        if key in excluded or key in seen:
            continue

        seen.add(key)
        candidates.append(login)

    return candidates


def main(argv: list[str] | None = None) -> int:
    """Run the tester selection."""
    args = parse_args(argv)
    users_file = args.file or Path(
        os.environ.get("TESTERS_FILE") or DEFAULT_USERS_FILE
    )

    try:
        candidates = read_candidates(users_file, parse_excludes(args.exclude))
    except OSError:
        print(
            f"Error: tester list is missing or unreadable: {users_file}",
            file=sys.stderr,
        )
        return 1

    if len(candidates) < args.count:
        print(
            f"Error: need {args.count} candidates but only "
            f"{len(candidates)} are available in {users_file}",
            file=sys.stderr,
        )
        return 1

    for login in random.sample(candidates, args.count):
        print(login)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
