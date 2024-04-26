# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for auto_update_llvm_pgo_profile."""

from pathlib import Path
import subprocess
import textwrap
from unittest import mock

from llvm_tools import test_helpers
from pgo_tools import auto_update_llvm_pgo_profile


EXAMPLE_LLVM_EBUILD_SNIPPET = """
# foo
# bar

import baz

# comments
LLVM_PGO_PROFILE_REVS=(
\t516547
\t516548
)
# some more stuff
"""


class Test(test_helpers.TempDirTestCase):
    """Tests for auto_update_llvm_pgo_profile."""

    def make_tempdir_with_example_llvm_ebuild(self) -> Path:
        cros_overlay = self.make_tempdir()
        llvm_9999 = (
            cros_overlay / auto_update_llvm_pgo_profile.LLVM_EBUILD_SUBPATH
        )
        llvm_9999.parent.mkdir(parents=True)
        llvm_9999.write_text(EXAMPLE_LLVM_EBUILD_SNIPPET, encoding="utf-8")
        return cros_overlay

    def test_ebuild_updating_is_nop_when_revs_dont_change(self):
        cros_overlay = self.make_tempdir_with_example_llvm_ebuild()
        updated = auto_update_llvm_pgo_profile.overwrite_llvm_pgo_listing(
            cros_overlay, [516547, 516548]
        )
        new_contents = (
            cros_overlay / auto_update_llvm_pgo_profile.LLVM_EBUILD_SUBPATH
        ).read_text(encoding="utf-8")
        self.assertEqual(EXAMPLE_LLVM_EBUILD_SNIPPET, new_contents)
        self.assertFalse(updated)

    def test_ebuild_updating_works_when_rev_is_removed(self):
        cros_overlay = self.make_tempdir_with_example_llvm_ebuild()
        self.assertTrue(
            auto_update_llvm_pgo_profile.overwrite_llvm_pgo_listing(
                cros_overlay, [516547]
            )
        )
        new_contents = (
            cros_overlay / auto_update_llvm_pgo_profile.LLVM_EBUILD_SUBPATH
        ).read_text(encoding="utf-8")
        self.assertIn("\n\t516547\n", new_contents)
        self.assertNotIn("\n\t516548\n", new_contents)

    def test_ebuild_updating_works_when_rev_is_added(self):
        cros_overlay = self.make_tempdir_with_example_llvm_ebuild()
        self.assertTrue(
            auto_update_llvm_pgo_profile.overwrite_llvm_pgo_listing(
                cros_overlay, [516547, 516548, 516549]
            )
        )
        new_contents = (
            cros_overlay / auto_update_llvm_pgo_profile.LLVM_EBUILD_SUBPATH
        ).read_text(encoding="utf-8")
        self.assertIn("\n\t516547\n", new_contents)
        self.assertIn("\n\t516548\n", new_contents)
        self.assertIn("\n\t516549\n", new_contents)

    @mock.patch.object(subprocess, "run")
    def test_gs_parsing_works(self, mock_run):
        run_return = mock.MagicMock()
        run_return.stdout = textwrap.dedent(
            """\
            gs://chromeos-localmirror/distfiles/llvm-profdata-r1234.xz
            gs://chromeos-localmirror/distfiles/llvm-profdata-r5678.xz
            """
        )
        mock_run.return_value = run_return
        cache = auto_update_llvm_pgo_profile.GsProfileCache.fetch()
        self.assertEqual(len(cache), 2)
        self.assertIn(1234, cache)
        self.assertIn(5678, cache)
