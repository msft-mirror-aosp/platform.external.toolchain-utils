# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Attributes/utilities for the LLVM repo that's bundled with ChromeOS"""

from pathlib import Path
import subprocess


# The path to the repository, relative to the root of a ChromeOS tree.
REPO_PATH = Path("src") / "third_party" / "llvm-project"

# Git remote to query/fetch for upstream.
UPSTREAM_REMOTE = "cros"
# Git branch that contains upstream commits.
UPSTREAM_MAIN = "upstream/main"


def fetch_upstream(repo_path: Path):
    """Runs `git fetch` for the upstream branch in the given repo."""
    subprocess.run(
        ["git", "fetch", UPSTREAM_REMOTE, UPSTREAM_MAIN],
        check=True,
        cwd=repo_path,
        stdin=subprocess.DEVNULL,
    )
