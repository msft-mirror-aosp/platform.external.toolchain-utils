#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for upload_llvm_testing_helper_cl"""

import unittest

from llvm_tools import patch_utils
from llvm_tools import test_helpers
from llvm_tools import upload_llvm_testing_helper_cl


class Test(test_helpers.TempDirTestCase):
    """Tests for upload_llvm_testing_helper_cl"""

    def test_force_rebuild_marker_addition(self):
        chromiumos_overlay = self.make_tempdir()
        filesdirs = []
        for package in patch_utils.CHROMEOS_PATCHES_JSON_PACKAGES:
            filesdir = chromiumos_overlay / package / "files"
            filesdir.mkdir(parents=True)
            filesdirs.append(filesdir)
        upload_llvm_testing_helper_cl.add_force_rebuild_markers(
            chromiumos_overlay
        )
        for filesdir in filesdirs:
            self.assertTrue(
                (filesdir / "force_rebuild"),
                f"Missing force_rebuild marker in {filesdir}",
            )

    def test_use_force_block_addition(self):
        chromiumos_overlay = self.make_tempdir()
        use_force_file = chromiumos_overlay / "profiles" / "base" / "use.force"
        use_force_file.parent.mkdir(parents=True)
        use_force_file.write_text("# Whee", encoding="utf-8")

        upload_llvm_testing_helper_cl.add_use_force_block(chromiumos_overlay)
        new_contents = use_force_file.read_text(encoding="utf-8")

        self.assertIn("# Whee\n", new_contents)
        self.assertIn(
            upload_llvm_testing_helper_cl.USE_FORCE_BLOCK, new_contents
        )

    def test_warning_disable_block_addition(self):
        chromiumos_overlay = self.make_tempdir()
        profile_bashrc = (
            chromiumos_overlay / "profiles" / "base" / "profile.bashrc"
        )
        profile_bashrc.parent.mkdir(parents=True)
        profile_bashrc.write_text("# Whee", encoding="utf-8")

        upload_llvm_testing_helper_cl.add_disable_warnings_block(
            chromiumos_overlay
        )
        new_contents = profile_bashrc.read_text(encoding="utf-8")

        self.assertIn("# Whee\n", new_contents)
        self.assertIn(
            upload_llvm_testing_helper_cl.DISABLE_WARNINGS_BLOCK, new_contents
        )
