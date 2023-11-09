#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for auto_upload_rust_bootstrap."""


from pathlib import Path
import shutil
import tempfile
import textwrap
import unittest

import auto_upload_rust_bootstrap


_GIT_PUSH_OUTPUT = r"""
remote: Waiting for private key checker: 2/2 objects left
remote:
remote: Processing changes: new: 1 (\)
remote: Processing changes: new: 1 (|)
remote: Processing changes: new: 1 (/)
remote: Processing changes: refs: 1, new: 1 (/)
remote: Processing changes: refs: 1, new: 1 (/)
remote: Processing changes: refs: 1, new: 1 (/)
remote: Processing changes: refs: 1, new: 1, done
remote:
remote: SUCCESS
remote:
remote:   https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5018826 rust-bootstrap: use prebuilts [WIP] [NEW]
remote:
To https://chromium.googlesource.com/chromiumos/overlays/chromiumos-overlay
 * [new reference]             HEAD -> refs/for/main
"""


class Test(unittest.TestCase):
    """Tests for auto_upload_rust_bootstrap."""

    def make_tempdir(self) -> Path:
        tempdir = Path(
            tempfile.mkdtemp(prefix="auto_upload_rust_bootstrap_test_")
        )
        self.addCleanup(shutil.rmtree, tempdir)
        return tempdir

    def test_git_cl_id_scraping(self):
        self.assertEqual(
            auto_upload_rust_bootstrap.scrape_git_push_cl_id(_GIT_PUSH_OUTPUT),
            5018826,
        )

    def test_ebuild_linking_logic_handles_direct_relative_symlinks(self):
        tempdir = self.make_tempdir()
        target = tempdir / "target.ebuild"
        target.touch()
        (tempdir / "symlink.ebuild").symlink_to(target.name)
        self.assertTrue(
            auto_upload_rust_bootstrap.is_ebuild_linked_to_in_dir(target)
        )

    def test_ebuild_linking_logic_handles_direct_absolute_symlinks(self):
        tempdir = self.make_tempdir()
        target = tempdir / "target.ebuild"
        target.touch()
        (tempdir / "symlink.ebuild").symlink_to(target)
        self.assertTrue(
            auto_upload_rust_bootstrap.is_ebuild_linked_to_in_dir(target)
        )

    def test_ebuild_linking_logic_handles_indirect_relative_symlinks(self):
        tempdir = self.make_tempdir()
        target = tempdir / "target.ebuild"
        target.touch()
        (tempdir / "symlink.ebuild").symlink_to(
            Path("..") / tempdir.name / target.name
        )
        self.assertTrue(
            auto_upload_rust_bootstrap.is_ebuild_linked_to_in_dir(target)
        )

    def test_ebuild_linking_logic_handles_broken_symlinks(self):
        tempdir = self.make_tempdir()
        target = tempdir / "target.ebuild"
        target.touch()
        (tempdir / "symlink.ebuild").symlink_to("doesnt_exist.ebuild")
        self.assertFalse(
            auto_upload_rust_bootstrap.is_ebuild_linked_to_in_dir(target)
        )

    def test_ebuild_linking_logic_only_steps_through_one_symlink(self):
        tempdir = self.make_tempdir()
        target = tempdir / "target.ebuild"
        target.symlink_to("doesnt_exist.ebuild")
        (tempdir / "symlink.ebuild").symlink_to(target.name)
        self.assertTrue(
            auto_upload_rust_bootstrap.is_ebuild_linked_to_in_dir(target)
        )

    def test_raw_bootstrap_seq_finding_functions(self):
        ebuild_contents = textwrap.dedent(
            """\
            # Some copyright
            FOO=bar
            # Comment about RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
            RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=( # another comment
                1.2.3 # (with a comment with parens)
                4.5.6
            )
            """
        )

        ebuild_lines = ebuild_contents.splitlines()
        (
            start,
            end,
        ) = auto_upload_rust_bootstrap.find_raw_bootstrap_sequence_lines(
            ebuild_lines
        )
        self.assertEqual(start, len(ebuild_lines) - 4)
        self.assertEqual(end, len(ebuild_lines) - 1)

    def test_collect_rust_bootstrap_ebuilds_ignores_older_versions(self):
        tempdir = self.make_tempdir()
        ebuild_170 = tempdir / "rust-bootstrap-1.70.0.ebuild"
        ebuild_170.touch()
        ebuild_170_r1 = tempdir / "rust-bootstrap-1.70.0-r1.ebuild"
        ebuild_170_r1.touch()
        ebuild_171_r2 = tempdir / "rust-bootstrap-1.71.1-r2.ebuild"
        ebuild_171_r2.touch()

        self.assertEqual(
            auto_upload_rust_bootstrap.collect_rust_bootstrap_ebuilds(tempdir),
            [
                (
                    auto_upload_rust_bootstrap.EbuildVersion(
                        major=1, minor=70, patch=0, rev=1
                    ),
                    ebuild_170_r1,
                ),
                (
                    auto_upload_rust_bootstrap.EbuildVersion(
                        major=1, minor=71, patch=1, rev=2
                    ),
                    ebuild_171_r2,
                ),
            ],
        )

    def test_has_prebuilt_works(self):
        tempdir = self.make_tempdir()
        ebuild = tempdir / "rust-bootstrap-1.70.0.ebuild"
        ebuild.write_text(
            textwrap.dedent(
                """\
                # Some copyright
                FOO=bar
                # Comment about RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
                RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=( # another comment
                    1.67.0
                    1.68.1
                    1.69.0
                )
                """
            ),
            encoding="utf-8",
        )

        self.assertTrue(
            auto_upload_rust_bootstrap.version_listed_in_bootstrap_sequence(
                ebuild,
                auto_upload_rust_bootstrap.EbuildVersion(
                    major=1,
                    minor=69,
                    patch=0,
                    rev=0,
                ),
            )
        )

        self.assertFalse(
            auto_upload_rust_bootstrap.version_listed_in_bootstrap_sequence(
                ebuild,
                auto_upload_rust_bootstrap.EbuildVersion(
                    major=1,
                    minor=70,
                    patch=0,
                    rev=0,
                ),
            )
        )

    def test_ebuild_updating_works(self):
        tempdir = self.make_tempdir()
        ebuild = tempdir / "rust-bootstrap-1.70.0.ebuild"
        ebuild.write_text(
            textwrap.dedent(
                """\
                # Some copyright
                FOO=bar
                RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
                \t1.67.0
                \t1.68.1
                \t1.69.0
                )
                """
            ),
            encoding="utf-8",
        )

        auto_upload_rust_bootstrap.add_version_to_bootstrap_sequence(
            ebuild,
            auto_upload_rust_bootstrap.EbuildVersion(
                major=1,
                minor=70,
                patch=1,
                rev=2,
            ),
            dry_run=False,
        )

        self.assertEqual(
            ebuild.read_text(encoding="utf-8"),
            textwrap.dedent(
                """\
                # Some copyright
                FOO=bar
                RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
                \t1.67.0
                \t1.68.1
                \t1.69.0
                \t1.70.1-r2
                )
                """
            ),
        )

    def test_ebuild_version_parsing_works(self):
        self.assertEqual(
            auto_upload_rust_bootstrap.parse_rust_bootstrap_ebuild_version(
                "rust-bootstrap-1.70.0-r2.ebuild"
            ),
            auto_upload_rust_bootstrap.EbuildVersion(
                major=1, minor=70, patch=0, rev=2
            ),
        )

        self.assertEqual(
            auto_upload_rust_bootstrap.parse_rust_bootstrap_ebuild_version(
                "rust-bootstrap-2.80.3.ebuild"
            ),
            auto_upload_rust_bootstrap.EbuildVersion(
                major=2, minor=80, patch=3, rev=0
            ),
        )


if __name__ == "__main__":
    unittest.main()
