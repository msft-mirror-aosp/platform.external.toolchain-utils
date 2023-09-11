#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Git helper functions."""


import collections
import os
import re
import subprocess
import tempfile
from typing import Iterable, Optional


CommitContents = collections.namedtuple("CommitContents", ["url", "cl_number"])


def InChroot():
    """Returns True if currently in the chroot."""
    return "CROS_WORKON_SRCROOT" in os.environ


def VerifyOutsideChroot():
    """Checks whether the script invoked was executed in the chroot.

    Raises:
      AssertionError: The script was run inside the chroot.
    """

    assert not InChroot(), "Script should be run outside the chroot."


def CreateBranch(repo, branch):
    """Creates a branch in the given repo.

    Args:
      repo: The absolute path to the repo.
      branch: The name of the branch to create.

    Raises:
      ValueError: Failed to create a repo in that directory.
    """

    if not os.path.isdir(repo):
        raise ValueError("Invalid directory path provided: %s" % repo)

    subprocess.check_output(["git", "-C", repo, "reset", "HEAD", "--hard"])

    subprocess.check_output(["repo", "start", branch], cwd=repo)


def DeleteBranch(repo, branch):
    """Deletes a branch in the given repo.

    Args:
      repo: The absolute path of the repo.
      branch: The name of the branch to delete.

    Raises:
      ValueError: Failed to delete the repo in that directory.
    """

    if not os.path.isdir(repo):
        raise ValueError("Invalid directory path provided: %s" % repo)

    def run_checked(cmd):
        subprocess.run(["git", "-C", repo] + cmd, check=True)

    run_checked(["checkout", "-q", "m/main"])
    run_checked(["reset", "-q", "HEAD", "--hard"])
    run_checked(["branch", "-q", "-D", branch])


def CommitChanges(repo, commit_messages: Iterable[str]):
    """Commit changes without uploading them."""
    if not os.path.isdir(repo):
        raise ValueError("Invalid path provided: %s" % repo)

    # Create a git commit.
    with tempfile.NamedTemporaryFile(mode="w+t", encoding="utf-8") as f:
        f.write("\n".join(commit_messages))
        f.flush()

        subprocess.check_output(["git", "commit", "-F", f.name], cwd=repo)


def UploadChanges(
    repo,
    branch: str,
    reviewers: Optional[Iterable[str]] = None,
    cc: Optional[Iterable[str]] = None,
    wip=False,
):
    """Uploads the changes in the specifed branch of the given repo for review.

    Args:
      repo: The absolute path to the repo where changes were made.
      branch: The name of the branch to upload.
      of the changes made.
      reviewers: A list of reviewers to add to the CL.
      cc: A list of contributors to CC about the CL.

    Returns:
      A nametuple that has two (key, value) pairs, where the first pair is the
      Gerrit commit URL and the second pair is the change list number.

    Raises:
      ValueError: Failed to create a commit or failed to upload the
      changes for review.
    """

    if not os.path.isdir(repo):
        raise ValueError("Invalid path provided: %s" % repo)

    # Upload the changes for review.
    git_args = [
        "repo",
        "upload",
        "--yes",
        f'--reviewers={",".join(reviewers)}' if reviewers else "--ne",
        "--no-verify",
        f"--br={branch}",
    ]

    if cc:
        git_args.append(f'--cc={",".join(cc)}')
    if wip:
        git_args.append("--wip")

    out = subprocess.check_output(
        git_args,
        stderr=subprocess.STDOUT,
        cwd=repo,
        encoding="utf-8",
    )

    print(out)
    # Matches both internal and external CLs.
    found_url = re.search(
        r"https?://[\w-]*-review.googlesource.com/c/.*/([0-9]+)",
        out.rstrip(),
    )
    if not found_url:
        raise ValueError("Failed to find change list URL.")

    return CommitContents(
        url=found_url.group(0), cl_number=int(found_url.group(1))
    )
