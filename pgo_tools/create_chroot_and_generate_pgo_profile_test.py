#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for generate_llvm_next_pgo."""

from pathlib import Path
import shutil
import tempfile
import unittest

# This script's name makes lines exceed 80 chars if it's not imported `as`
# something shorter.
import create_chroot_and_generate_pgo_profile as create_chroot_etc


class Test(unittest.TestCase):
    """Tests for generate_llvm_next_pgo."""

    def make_tempdir(self) -> Path:
        tempdir = Path(tempfile.mkdtemp(prefix="generate_llvm_next_pgo_test_"))
        self.addCleanup(lambda: shutil.rmtree(tempdir))
        return tempdir

    def test_path_translation_works(self):
        repo_root = Path("/some/repo")
        chroot_info = create_chroot_etc.ChrootInfo(
            chroot_name="my-chroot",
            out_dir_name="my-out",
        )
        self.assertEqual(
            create_chroot_etc.translate_chroot_path_to_out_of_chroot(
                repo_root, "/tmp/file/path", chroot_info
            ),
            repo_root / "my-out" / "tmp/file/path",
        )


if __name__ == "__main__":
    unittest.main()
