# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to create the first commit at the base of a new llvm branch.

Used primarily by new branch workflows and patch management tooling.
"""

from pathlib import Path
import shutil

from cros_utils import git_utils


# This isn't a dict to prevent adding a tomli-w dependency.
PRESUBMIT_CFG_CONTENTS = """\
[Hook Overrides]
cros_license_check: True
long_line_check: True

[Hook Overrides Options]
cros_license_check: --exclude_regex=.*
long_line_check: --exclude_regex=.*
"""

CROS_DIR_README = """\
# CrOS Directory

This directory is used to store arbitrary changes for the ChromeOS Toolchain
team. Files in this directory are never meant to be upstreamed, and only
exist for local modification.

See src/third_party/toolchain-utils to see how this directory is configured.
"""

BASE_COMMIT_MESSAGE = """\
llvm-project: ChromeOS Base Commit

This is the LLVM ChromeOS Base Commit.

This commit marks the start of the ChromeOS patch branch. It introduces
the OWNERS file, and sets up the 'cros' directory for future use.

Functional patches for the ChromeOS LLVM Toolchain land after this
commit. This commit does not change how LLVM operates. The parent
commit to this change determines the LLVM synthetic revision.

BUG=None
TEST=CQ
"""


def make_base_commit(toolchain_utils_dir: Path, llvm_src_dir: Path) -> None:
    """Create a commit which represents the base of a ChromeOS branch."""

    toolchain_utils_copy_files = (
        "OWNERS",
        "OWNERS.toolchain",
    )
    for copy_file in toolchain_utils_copy_files:
        shutil.copy(toolchain_utils_dir / copy_file, llvm_src_dir / copy_file)
    (llvm_src_dir / "PRESUBMIT.cfg").write_text(PRESUBMIT_CFG_CONTENTS)
    set_up_cros_dir(llvm_src_dir)
    git_utils.commit_all_changes(llvm_src_dir, BASE_COMMIT_MESSAGE)


def set_up_cros_dir(llvm_src_dir: Path) -> None:
    """Create and init the llvm-project/cros directory."""
    cros_dir = llvm_src_dir / "cros"
    cros_dir.mkdir()
    readme = cros_dir / "README.md"
    readme.write_text(CROS_DIR_README)
