#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Abandons CLs from the current user that haven't been updated recently.

Note that this needs to be run from inside a ChromeOS tree. Otherwise, the
`gerrit` tool this depends on won't be found.
"""

import argparse
import logging
import subprocess
import sys
from typing import List


def enumerate_old_cls(old_days: int) -> List[int]:
    """Returns CL numbers that haven't been updated in `old_days` days."""
    stdout = subprocess.run(
        ["gerrit", "--raw", "search", f"owner:me status:open age:{old_days}d"],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ).stdout
    # Sort for prettier output; it's unclear if Gerrit always sorts, and it's
    # cheap.
    return sorted(int(x) for x in stdout.splitlines())


def abandon_cls(cls: List[int]) -> None:
    subprocess.run(
        ["gerrit", "abandon"] + [str(x) for x in cls],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def main(argv: List[str]) -> None:
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--old-days",
        default=14,
        type=int,
        help="""
        How many days a CL needs to go without modification to be considered
        'old'.
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually run the abandon command.",
    )
    opts = parser.parse_args(argv)

    old_cls = enumerate_old_cls(opts.old_days)
    if not old_cls:
        logging.info("No CLs less than %d days old found; quit", opts.old_days)
        return

    logging.info("Abandoning CLs: %s", [f"crrev.com/c/{x}" for x in old_cls])
    if opts.dry_run:
        logging.info("--dry-run specified; skip the actual abandon part")
        return

    abandon_cls(old_cls)


if __name__ == "__main__":
    main(sys.argv[1:])
