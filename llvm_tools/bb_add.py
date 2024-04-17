#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs `bb add`, with additional convenience features."""

import argparse
import logging
import os
import shlex
import sys
from typing import Iterable, List

import cros_cls
import llvm_next


def generate_bb_add_command(
    use_llvm_next: bool,
    extra_cls: Iterable[cros_cls.ChangeListURL],
    bots: Iterable[str],
    tags: Iterable[str],
) -> List[str]:
    """Generates a `bb add` command.

    Args:
        use_llvm_next: if True, all current llvm-next CLs will be added to the
            run.
        extra_cls: A list of extra CLs to add to the run.
        bots: Bots that should be spawned by this command, e.g.,
            `chromeos/staging/staging-build-chromiumos-sdk`.
        tags: Tags that should be applied to the bot invocation(s). This can
            make searching for the invocations easier using tools like `bb ls`.

    Returns:
        A command that would spawn the requested builders in the requested
        configuration.
    """
    cls: List[cros_cls.ChangeListURL] = []
    if use_llvm_next:
        if not llvm_next.LLVM_NEXT_TESTING_CLS:
            raise ValueError(
                "llvm-next testing requested, but no llvm-next CLs exist."
            )
        cls += llvm_next.LLVM_NEXT_TESTING_CLS

    if extra_cls:
        cls += extra_cls

    cmd = ["bb", "add"]
    for cl in cls:
        cmd += ("-cl", cl.crrev_url_without_http())

    for tag in tags:
        cmd += ("-t", tag)
    cmd += bots
    return cmd


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
        "--dry-run",
        action="store_true",
        help="Print the `bb` command, rather than running it.",
    )
    parser.add_argument(
        "--llvm-next",
        action="store_true",
        help="Add the current llvm-next patch set.",
    )
    parser.add_argument(
        "--cl",
        action="append",
        type=cros_cls.ChangeListURL.parse,
        help="""
        CL to add to the `bb add` run. May be specified multiple times. In the
        form crrev.com/c/123456.
        """,
    )
    parser.add_argument(
        "--tag",
        action="append",
        help="""
        Tag to add to the `bb add` invocation. May be specified multiple times.
        Tags are arbitrary text.
        """,
    )
    parser.add_argument("bot", nargs="+", help="Bot(s) to run `bb add` with.")
    opts = parser.parse_args(argv)

    cmd = generate_bb_add_command(
        use_llvm_next=opts.llvm_next,
        extra_cls=opts.cl,
        bots=opts.bot,
        tags=opts.tag or (),
    )
    if opts.dry_run:
        logging.info(
            "--dry-run specified; would run: `%s` otherwise", shlex.join(cmd)
        )
        return

    logging.info("Running `bb add` command: %s...", shlex.join(cmd))
    # execvp raises if it fails, so no need to check.
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
