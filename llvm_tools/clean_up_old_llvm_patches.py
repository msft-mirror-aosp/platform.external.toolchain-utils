#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Removes all LLVM patches before a certain point."""

import argparse
import logging
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import List, Optional

from cros_utils import git_utils
import patch_utils


# The chromiumos-overlay packages to GC patches in.
PACKAGES_TO_COLLECT = patch_utils.CHROMEOS_PATCHES_JSON_PACKAGES

# Folks who should be on the R-line of any CLs that get uploaded.
CL_REVIEWERS = (git_utils.REVIEWER_DETECTIVE,)

# Folks who should be on the CC-line of any CLs that get uploaded.
CL_CC = ("gbiv@google.com",)


def maybe_autodetect_cros_overlay(my_dir: Path) -> Optional[Path]:
    third_party = my_dir.parent.parent
    cros_overlay = third_party / "chromiumos-overlay"
    if cros_overlay.exists():
        return cros_overlay
    return None


def remove_old_patches(cros_overlay: Path, min_revision: int) -> bool:
    """Removes patches in cros_overlay. Returns whether changes were made."""
    patches_removed = 0
    for package in PACKAGES_TO_COLLECT:
        logging.info("GC'ing patches from %s...", package)
        patches_json = cros_overlay / package / "files/PATCHES.json"
        removed_patch_files = patch_utils.remove_old_patches(
            min_revision, patches_json
        )
        if not removed_patch_files:
            logging.info("No patches removed from %s", patches_json)
            continue

        patches_removed += len(removed_patch_files)
        for patch in removed_patch_files:
            logging.info("Removing %s...", patch)
            patch.unlink()
    return patches_removed != 0


def commit_changes(cros_overlay: Path, min_rev: int):
    commit_msg = textwrap.dedent(
        f"""
        llvm: remove old patches

        These patches stopped applying before r{min_rev}, so should no longer
        be needed.

        BUG=b:332601837
        TEST=CQ
        """
    )

    subprocess.run(
        ["git", "commit", "--quiet", "-a", "-m", commit_msg],
        cwd=cros_overlay,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def upload_changes(cros_overlay: Path) -> None:
    cl_ids = git_utils.upload_to_gerrit(
        cros_overlay,
        remote="cros",
        branch="main",
        reviewers=CL_REVIEWERS,
        cc=CL_CC,
    )

    if len(cl_ids) > 1:
        raise ValueError(f"Unexpected: wanted just one CL upload; got {cl_ids}")

    cl_id = cl_ids[0]
    logging.info("Uploaded CL http://crrev.com/c/%s successfully.", cl_id)
    git_utils.try_set_autosubmit_labels(cros_overlay, cl_id)


def get_opts(my_dir: Path, argv: List[str]) -> argparse.Namespace:
    """Returns options for the script."""

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chromiumos-overlay",
        type=Path,
        help="""
        Path to chromiumos-overlay. Will autodetect if none is specified. If
        autodetection fails and none is specified, this script will fail.
        """,
    )
    parser.add_argument(
        "--revision",
        type=int,
        help="""
        Revision to delete before (exclusive). All patches that stopped
        applying before this will be removed. Phrased as an int, e.g.,
        `--revision=1234`.
        """,
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit changes after making them.",
    )
    parser.add_argument(
        "--upload-with-autoreview",
        action="store_true",
        help="""
        Upload changes after committing them. Implies --commit. Also adds
        default reviewers, and starts CQ+1 (among other convenience features).
        """,
    )
    opts = parser.parse_args(argv)

    if not opts.chromiumos_overlay:
        maybe_overlay = maybe_autodetect_cros_overlay(my_dir)
        if not maybe_overlay:
            parser.error(
                "Failed to autodetect --chromiumos-overlay; please pass a value"
            )
        opts.chromiumos_overlay = maybe_overlay
    return opts


def main(argv: List[str]) -> None:
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    my_dir = Path(__file__).resolve().parent
    opts = get_opts(my_dir, argv)

    cros_overlay = opts.chromiumos_overlay
    upload = opts.upload_with_autoreview
    commit = opts.commit or upload
    revision = opts.revision

    made_changes = remove_old_patches(cros_overlay, revision)
    if not made_changes:
        logging.info("No changes made; exiting.")
        return

    if not commit:
        logging.info(
            "Changes were made, but --commit wasn't specified. My job is done."
        )
        return

    logging.info("Committing changes...")
    commit_changes(cros_overlay, revision)
    if not upload:
        logging.info("Change with removed patches has been committed locally.")
        return

    logging.info("Uploading changes...")
    upload_changes(cros_overlay)
    logging.info("Change sent for review.")


if __name__ == "__main__":
    main(sys.argv[1:])
