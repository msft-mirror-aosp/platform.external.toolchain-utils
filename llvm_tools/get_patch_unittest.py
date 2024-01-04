#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for get_patch."""

import json
from pathlib import Path
import tempfile
from typing import Any, Dict, Generator, List, Set
import unittest
from unittest import mock

import get_patch
import git_llvm_rev


COMMIT_FIXTURES: List[Dict[str, Any]] = [
    {"subject": "A commit subject", "sha": "abcdef1234567890", "rev": 5},
    {"subject": "Another commit subject", "sha": "feed9999", "rev": 9},
]

JSON_FIXTURE: List[Dict[str, Any]] = [
    {
        "metadata": {"title": "An existing patch"},
        "platforms": ["another platform"],
        "rel_patch_path": "cherry/nowhere.patch",
        "version_range": {"from": 1, "until": 256},
    },
]


def _mock_get_commit_subj(_, sha: str) -> str:
    gen: Generator[Dict[str, Any], None, None] = (
        fixture for fixture in COMMIT_FIXTURES if fixture["sha"] == sha
    )
    return next(gen)["subject"]


def _mock_to_rev(sha: get_patch.LLVMGitRef, _) -> git_llvm_rev.Rev:
    gen: Generator[Dict[str, Any], None, None] = (
        fixture for fixture in COMMIT_FIXTURES if fixture["sha"] == sha.git_ref
    )
    return git_llvm_rev.Rev("main", next(gen)["rev"])


def _mock_from_rev(_, rev: git_llvm_rev.Rev) -> get_patch.LLVMGitRef:
    gen: Generator[Dict[str, Any], None, None] = (
        fixture for fixture in COMMIT_FIXTURES if fixture["rev"] == rev.number
    )
    return get_patch.LLVMGitRef(next(gen)["sha"])


def _mock_git_format_patch(*_) -> str:
    return "[category] This is a fake commit fixture"


def _mock_write_patch(*_) -> None:
    return


def _mock_get_changed_packages(*_) -> Set[Path]:
    return {get_patch.LLVM_PKG_PATH}


class TestGetPatch(unittest.TestCase):
    """Test case harness for get_patch."""

    def setUp(self) -> None:
        """Set up the mocks and directory structure."""

        self.module_patcher = mock.patch.multiple(
            "get_patch",
            get_commit_subj=_mock_get_commit_subj,
            git_format_patch=_mock_git_format_patch,
            get_changed_packages=_mock_get_changed_packages,
            _write_patch=_mock_write_patch,
        )
        self.module_patcher.start()
        self.addCleanup(self.module_patcher.stop)
        self.llvm_gitsha_patcher = mock.patch.multiple(
            "get_patch.LLVMGitRef",
            to_rev=_mock_to_rev,
            from_rev=_mock_from_rev,
        )
        self.llvm_gitsha_patcher.start()
        self.addCleanup(self.llvm_gitsha_patcher.stop)

        self.llvm_project_dir = Path(tempfile.mkdtemp())
        self.addCleanup(self.llvm_project_dir.rmdir)
        self.chromiumos_root = Path(tempfile.mkdtemp())
        self.addCleanup(self.chromiumos_root.rmdir)
        self.workdir = self.chromiumos_root / get_patch.LLVM_PKG_PATH / "files"
        self.workdir.mkdir(parents=True, exist_ok=True)

        def _cleanup_workdir():
            # We individually clean up these directories as a guarantee
            # we aren't creating any extraneous files. We don't want to
            # use shm.rmtree here because we don't want clean up any
            # files unaccounted for.
            workdir_recurse = self.workdir
            while workdir_recurse not in (self.chromiumos_root, Path.root):
                workdir_recurse.rmdir()
                workdir_recurse = workdir_recurse.parent

        self.addCleanup(_cleanup_workdir)

        self.patches_json_file = (
            self.workdir / get_patch.PATCH_METADATA_FILENAME
        )
        start_ref = get_patch.LLVMGitRef("abcdef1234567890")
        self.ctx = get_patch.PatchContext(
            self.llvm_project_dir,
            self.chromiumos_root,
            start_ref,
            platforms=["some platform"],
        )

    def write_json_fixture(self) -> None:
        with self.patches_json_file.open("w", encoding="utf-8") as f:
            json.dump(JSON_FIXTURE, f)
            f.write("\n")

    def test_make_patches(self) -> None:
        """Test we can make patch entries from a git commit."""

        fixture = COMMIT_FIXTURES[0]
        # We manually write and delete this file because it must have the name
        # as specified by get_patch. tempfile cannot guarantee us this name.
        self.write_json_fixture()
        try:
            entries = self.ctx.make_patches(
                get_patch.LLVMGitRef(fixture["sha"])
            )
            self.assertEqual(len(entries), 1)
            if entries[0].metadata:
                self.assertEqual(
                    entries[0].metadata["title"], fixture["subject"]
                )
            else:
                self.fail("metadata was None")
        finally:
            self.patches_json_file.unlink()


if __name__ == "__main__":
    unittest.main()
