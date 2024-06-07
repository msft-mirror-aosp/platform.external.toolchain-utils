# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for create_patch_file."""

from pathlib import Path
from typing import Optional
import unittest

from llvm_tools import create_patch_file
from llvm_tools import git_llvm_rev
from llvm_tools import patch_utils


class TestCreatePatchFile(unittest.TestCase):
    """Test harness for create_patch_file."""

    @staticmethod
    def _make_patch_entry(
        from_: Optional[int], until: Optional[int], title: str = "Some title"
    ):
        return patch_utils.PatchEntry(
            workdir=Path(),
            metadata={
                "info": [],
                "title": title,
            },
            platforms=["some platform"],
            rel_patch_path="a/path/to/a/patch.patch",
            version_range={"from": from_, "until": until},
        )

    def test_find_new_patches_normal(self):
        """Test that we only find newer patches applied to a given branch."""

        llvm_rev = git_llvm_rev.Rev(git_llvm_rev.MAIN_BRANCH, 1234)
        version_ranges = (
            (1, 2),
            (5, 100),
            (1234, 1235),
            (1, 1235),
            (None, None),
        )
        existing_patches = [
            self._make_patch_entry(from_, until)
            for from_, until in version_ranges
        ]
        branch_version_ranges = ((1, 1984), (1000, 9001))
        branch_combos = [
            create_patch_file.PatchCombo(
                self._make_patch_entry(from_, until),
                "[some contents]",
            )
            for from_, until in ((1234, 1235), (1, 1235), (None, None))
            + branch_version_ranges
        ]
        branch_combos.insert(
            0,
            create_patch_file.PatchCombo(
                self._make_patch_entry(None, None, "llvm-project: Base Commit"),
                "[PATCH] llvm-project: Base Commit",
            ),
        )
        branch_context = create_patch_file.BranchContext(
            branch_ref="some-branch-name",
            merge_base="abcdef",
            llvm_rev=llvm_rev,
            patch_entry_combos=branch_combos,
        )
        new_patch_combos = create_patch_file.find_new_patches(
            branch_context, existing_patches
        )
        self.assertEqual(
            new_patch_combos, branch_combos[-len(branch_version_ranges) :]
        )
