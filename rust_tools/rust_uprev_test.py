#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for rust_uprev.py"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from llvm_tools import git


# rust_uprev sets SOURCE_ROOT to the output of `repo --show-toplevel`.
# The mock below makes us not actually run repo but use a fake value
# instead.
with mock.patch("subprocess.check_output", return_value="/fake/chromiumos"):
    import rust_uprev


def _fail_command(cmd, *_args, **_kwargs):
    err = subprocess.CalledProcessError(returncode=1, cmd=cmd)
    err.stderr = b"mock failure"
    raise err


def start_mock(obj, *args, **kwargs):
    """Creates a patcher, starts it, and registers a cleanup to stop it.

    Args:
        obj:
            the object to attach the cleanup to
        *args:
            passed to mock.patch()
        **kwargs:
            passsed to mock.patch()
    """
    patcher = mock.patch(*args, **kwargs)
    val = patcher.start()
    obj.addCleanup(patcher.stop)
    return val


class FetchDistfileTest(unittest.TestCase):
    """Tests rust_uprev.fetch_distfile_from_mirror()"""

    @mock.patch.object(
        rust_uprev, "get_distdir", return_value=Path("/fake/distfiles")
    )
    @mock.patch.object(subprocess, "call", side_effect=_fail_command)
    def test_fetch_difstfile_fail(self, *_args) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            rust_uprev.fetch_distfile_from_mirror("test_distfile.tar.gz")

    @mock.patch.object(
        rust_uprev,
        "get_command_output_unchecked",
        return_value="AccessDeniedException: Access denied.",
    )
    @mock.patch.object(
        rust_uprev, "get_distdir", return_value=Path("/fake/distfiles")
    )
    @mock.patch.object(subprocess, "call", return_value=0)
    def test_fetch_distfile_acl_access_denied(self, *_args) -> None:
        rust_uprev.fetch_distfile_from_mirror("test_distfile.tar.gz")

    @mock.patch.object(
        rust_uprev,
        "get_command_output_unchecked",
        return_value='[ { "entity": "allUsers", "role": "READER" } ]',
    )
    @mock.patch.object(
        rust_uprev, "get_distdir", return_value=Path("/fake/distfiles")
    )
    @mock.patch.object(subprocess, "call", return_value=0)
    def test_fetch_distfile_acl_ok(self, *_args) -> None:
        rust_uprev.fetch_distfile_from_mirror("test_distfile.tar.gz")

    @mock.patch.object(
        rust_uprev,
        "get_command_output_unchecked",
        return_value='[ { "entity": "___fake@google.com", "role": "OWNER" } ]',
    )
    @mock.patch.object(
        rust_uprev, "get_distdir", return_value=Path("/fake/distfiles")
    )
    @mock.patch.object(subprocess, "call", return_value=0)
    def test_fetch_distfile_acl_wrong(self, *_args) -> None:
        with self.assertRaisesRegex(Exception, "allUsers.*READER"):
            with self.assertLogs(level="ERROR") as log:
                rust_uprev.fetch_distfile_from_mirror("test_distfile.tar.gz")
                self.assertIn(
                    '[ { "entity": "___fake@google.com", "role": "OWNER" } ]',
                    "\n".join(log.output),
                )


class FetchRustSrcFromUpstreamTest(unittest.TestCase):
    """Tests for rust_uprev.fetch_rust_src_from_upstream."""

    def setUp(self) -> None:
        self._mock_get_distdir = start_mock(
            self,
            "rust_uprev.get_distdir",
            return_value=Path("/fake/distfiles"),
        )

        self._mock_gpg = start_mock(
            self,
            "subprocess.run",
            side_effect=self.fake_gpg,
        )

        self._mock_urlretrieve = start_mock(
            self,
            "urllib.request.urlretrieve",
            side_effect=self.fake_urlretrieve,
        )

        self._mock_rust_signing_key = start_mock(
            self,
            "rust_uprev.RUST_SIGNING_KEY",
            "1234567",
        )

    @staticmethod
    def fake_urlretrieve(src: str, dest: Path) -> None:
        pass

    @staticmethod
    def fake_gpg(cmd, **_kwargs):
        val = mock.Mock()
        val.returncode = 0
        val.stdout = ""
        if "--verify" in cmd:
            val.stdout = "GOODSIG 1234567"
        return val

    def test_success(self):
        with mock.patch("rust_uprev.GPG", "gnupg"):
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
            self._mock_urlretrieve.has_calls(
                [
                    (
                        "fakehttps://rustc-1.60.3-src.tar.gz",
                        Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
                    ),
                    (
                        "fakehttps://rustc-1.60.3-src.tar.gz.asc",
                        Path("/fake/distfiles/rustc-1.60.3-src.tar.gz.asc"),
                    ),
                ]
            )
            self._mock_gpg.has_calls(
                [
                    (["gnupg", "--refresh-keys", "1234567"], {"check": True}),
                ]
            )

    def test_no_signature_file(self):
        def _urlretrieve(src, dest):
            if src.endswith(".asc"):
                raise Exception("404 not found")
            return self.fake_urlretrieve(src, dest)

        self._mock_urlretrieve.side_effect = _urlretrieve

        with self.assertRaises(rust_uprev.SignatureVerificationError) as ctx:
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
        self.assertIn("error fetching signature file", ctx.exception.message)

    def test_key_expired(self):
        def _gpg_verify(cmd, *args, **kwargs):
            val = self.fake_gpg(cmd, *args, **kwargs)
            if "--verify" in cmd:
                val.stdout = "EXPKEYSIG 1234567"
            return val

        self._mock_gpg.side_effect = _gpg_verify

        with self.assertRaises(rust_uprev.SignatureVerificationError) as ctx:
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
        self.assertIn("key has expired", ctx.exception.message)

    def test_key_revoked(self):
        def _gpg_verify(cmd, *args, **kwargs):
            val = self.fake_gpg(cmd, *args, **kwargs)
            if "--verify" in cmd:
                val.stdout = "REVKEYSIG 1234567"
            return val

        self._mock_gpg.side_effect = _gpg_verify

        with self.assertRaises(rust_uprev.SignatureVerificationError) as ctx:
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
        self.assertIn("key has been revoked", ctx.exception.message)

    def test_signature_expired(self):
        def _gpg_verify(cmd, *args, **kwargs):
            val = self.fake_gpg(cmd, *args, **kwargs)
            if "--verify" in cmd:
                val.stdout = "EXPSIG 1234567"
            return val

        self._mock_gpg.side_effect = _gpg_verify

        with self.assertRaises(rust_uprev.SignatureVerificationError) as ctx:
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
        self.assertIn("signature has expired", ctx.exception.message)

    def test_wrong_key(self):
        def _gpg_verify(cmd, *args, **kwargs):
            val = self.fake_gpg(cmd, *args, **kwargs)
            if "--verify" in cmd:
                val.stdout = "GOODSIG 0000000"
            return val

        self._mock_gpg.side_effect = _gpg_verify

        with self.assertRaises(rust_uprev.SignatureVerificationError) as ctx:
            rust_uprev.fetch_rust_src_from_upstream(
                "fakehttps://rustc-1.60.3-src.tar.gz",
                Path("/fake/distfiles/rustc-1.60.3-src.tar.gz"),
            )
        self.assertIn("1234567 not found", ctx.exception.message)


class FindEbuildPathTest(unittest.TestCase):
    """Tests for rust_uprev.find_ebuild_path()"""

    def test_exact_version(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            ebuild = tmpdir / "test-1.3.4.ebuild"
            ebuild.touch()
            (tmpdir / "test-1.2.3.ebuild").touch()
            result = rust_uprev.find_ebuild_path(
                tmpdir, "test", rust_uprev.RustVersion(1, 3, 4)
            )
            self.assertEqual(result, ebuild)

    def test_no_version(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            ebuild = tmpdir / "test-1.2.3.ebuild"
            ebuild.touch()
            result = rust_uprev.find_ebuild_path(tmpdir, "test")
            self.assertEqual(result, ebuild)

    def test_patch_version(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            ebuild = tmpdir / "test-1.3.4-r3.ebuild"
            ebuild.touch()
            (tmpdir / "test-1.2.3.ebuild").touch()
            result = rust_uprev.find_ebuild_path(
                tmpdir, "test", rust_uprev.RustVersion(1, 3, 4)
            )
            self.assertEqual(result, ebuild)

    def test_multiple_versions(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            (tmpdir / "test-1.3.4-r3.ebuild").touch()
            (tmpdir / "test-1.3.5.ebuild").touch()
            with self.assertRaises(AssertionError):
                rust_uprev.find_ebuild_path(tmpdir, "test")

    def test_selected_version(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            ebuild = tmpdir / "test-1.3.4-r3.ebuild"
            ebuild.touch()
            (tmpdir / "test-1.3.5.ebuild").touch()
            result = rust_uprev.find_ebuild_path(
                tmpdir, "test", rust_uprev.RustVersion(1, 3, 4)
            )
            self.assertEqual(result, ebuild)

    def test_symlink(self):
        # Symlinks to ebuilds in the same directory are allowed, and the return
        # value is the regular file.
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            ebuild = tmpdir / "test-1.3.4.ebuild"
            ebuild.touch()
            (tmpdir / "test-1.3.4-r1.ebuild").symlink_to("test-1.3.4.ebuild")
            result = rust_uprev.find_ebuild_path(tmpdir, "test")
            self.assertEqual(result, ebuild)


class MirrorHasFileTest(unittest.TestCase):
    """Tests for rust_uprev.mirror_has_file."""

    @mock.patch.object(subprocess, "run")
    def test_no(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=1,
            stdout="CommandException: One or more URLs matched no objects.",
        )
        self.assertFalse(rust_uprev.mirror_has_file("rustc-1.69.0-src.tar.gz"))

    @mock.patch.object(subprocess, "run")
    def test_yes(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0,
            # pylint: disable=line-too-long
            stdout="gs://chromeos-localmirror/distfiles/rustc-1.69.0-src.tar.gz",
        )
        self.assertTrue(rust_uprev.mirror_has_file("rustc-1.69.0-src.tar.gz"))


class MirrorRustSourceTest(unittest.TestCase):
    """Tests for rust_uprev.mirror_rust_source."""

    def setUp(self) -> None:
        start_mock(self, "rust_uprev.GSUTIL", "gsutil")
        start_mock(self, "rust_uprev.MIRROR_PATH", "fakegs://fakemirror/")
        start_mock(
            self, "rust_uprev.get_distdir", return_value=Path("/fake/distfiles")
        )
        self.mock_mirror_has_file = start_mock(
            self,
            "rust_uprev.mirror_has_file",
        )
        self.mock_fetch_rust_src_from_upstream = start_mock(
            self,
            "rust_uprev.fetch_rust_src_from_upstream",
        )
        self.mock_subprocess_run = start_mock(
            self,
            "subprocess.run",
        )

    def test_already_present(self):
        self.mock_mirror_has_file.return_value = True
        rust_uprev.mirror_rust_source(
            rust_uprev.RustVersion.parse("1.67.3"),
        )
        self.mock_fetch_rust_src_from_upstream.assert_not_called()
        self.mock_subprocess_run.assert_not_called()

    def test_fetch_and_upload(self):
        self.mock_mirror_has_file.return_value = False
        rust_uprev.mirror_rust_source(
            rust_uprev.RustVersion.parse("1.67.3"),
        )
        self.mock_fetch_rust_src_from_upstream.called_once()
        self.mock_subprocess_run.has_calls(
            [
                (
                    [
                        "gsutil",
                        "cp",
                        "-a",
                        "public-read",
                        "/fake/distdir/rustc-1.67.3-src.tar.gz",
                        "fakegs://fakemirror/rustc-1.67.3-src.tar.gz",
                    ]
                ),
            ]
        )


class RemoveEbuildVersionTest(unittest.TestCase):
    """Tests for rust_uprev.remove_ebuild_version()"""

    @mock.patch.object(subprocess, "check_call")
    def test_single(self, check_call):
        with tempfile.TemporaryDirectory() as tmpdir:
            ebuild_dir = Path(tmpdir, "test-ebuilds")
            ebuild_dir.mkdir()
            ebuild = Path(ebuild_dir, "test-3.1.4.ebuild")
            ebuild.touch()
            Path(ebuild_dir, "unrelated-1.0.0.ebuild").touch()
            rust_uprev.remove_ebuild_version(
                ebuild_dir, "test", rust_uprev.RustVersion(3, 1, 4)
            )
            check_call.assert_called_once_with(
                ["git", "rm", "test-3.1.4.ebuild"], cwd=ebuild_dir
            )

    @mock.patch.object(subprocess, "check_call")
    def test_symlink(self, check_call):
        with tempfile.TemporaryDirectory() as tmpdir:
            ebuild_dir = Path(tmpdir, "test-ebuilds")
            ebuild_dir.mkdir()
            ebuild = Path(ebuild_dir, "test-3.1.4.ebuild")
            ebuild.touch()
            symlink = Path(ebuild_dir, "test-3.1.4-r5.ebuild")
            symlink.symlink_to(ebuild.name)
            Path(ebuild_dir, "unrelated-1.0.0.ebuild").touch()
            rust_uprev.remove_ebuild_version(
                ebuild_dir, "test", rust_uprev.RustVersion(3, 1, 4)
            )
            check_call.assert_has_calls(
                [
                    mock.call(
                        ["git", "rm", "test-3.1.4.ebuild"], cwd=ebuild_dir
                    ),
                    mock.call(
                        ["git", "rm", "test-3.1.4-r5.ebuild"], cwd=ebuild_dir
                    ),
                ],
                any_order=True,
            )


class RustVersionTest(unittest.TestCase):
    """Tests for RustVersion class"""

    def test_str(self):
        obj = rust_uprev.RustVersion(major=1, minor=2, patch=3)
        self.assertEqual(str(obj), "1.2.3")

    def test_parse_version_only(self):
        expected = rust_uprev.RustVersion(major=1, minor=2, patch=3)
        actual = rust_uprev.RustVersion.parse("1.2.3")
        self.assertEqual(expected, actual)

    def test_parse_ebuild_name(self):
        expected = rust_uprev.RustVersion(major=1, minor=2, patch=3)
        actual = rust_uprev.RustVersion.parse_from_ebuild("rust-1.2.3.ebuild")
        self.assertEqual(expected, actual)

        actual = rust_uprev.RustVersion.parse_from_ebuild(
            "rust-1.2.3-r1.ebuild"
        )
        self.assertEqual(expected, actual)

    def test_parse_fail(self):
        with self.assertRaises(AssertionError) as context:
            rust_uprev.RustVersion.parse("invalid-rust-1.2.3")
        self.assertEqual(
            "failed to parse 'invalid-rust-1.2.3'", str(context.exception)
        )


class PrepareUprevTest(unittest.TestCase):
    """Tests for prepare_uprev step in rust_uprev"""

    def setUp(self):
        self.bootstrap_version = rust_uprev.RustVersion(1, 1, 0)
        self.version_old = rust_uprev.RustVersion(1, 2, 3)
        self.version_new = rust_uprev.RustVersion(1, 3, 5)

    @mock.patch.object(
        rust_uprev,
        "find_ebuild_for_rust_version",
        return_value="/path/to/ebuild",
    )
    @mock.patch.object(rust_uprev, "find_ebuild_path")
    @mock.patch.object(rust_uprev, "get_command_output")
    def test_success_with_template(
        self, mock_command, mock_find_ebuild, _ebuild_for_version
    ):
        bootstrap_ebuild_path = Path(
            "/path/to/rust-bootstrap/",
            f"rust-bootstrap-{self.bootstrap_version}.ebuild",
        )
        mock_find_ebuild.return_value = bootstrap_ebuild_path
        expected = rust_uprev.PreparedUprev(
            self.version_old, Path("/path/to/ebuild"), self.bootstrap_version
        )
        actual = rust_uprev.prepare_uprev(
            rust_version=self.version_new, template=self.version_old
        )
        self.assertEqual(expected, actual)
        mock_command.assert_not_called()

    @mock.patch.object(
        rust_uprev,
        "find_ebuild_for_rust_version",
        return_value="/path/to/ebuild",
    )
    @mock.patch.object(
        rust_uprev,
        "get_rust_bootstrap_version",
        return_value=rust_uprev.RustVersion(0, 41, 12),
    )
    @mock.patch.object(rust_uprev, "get_command_output")
    def test_return_none_with_template_larger_than_input(
        self, mock_command, *_args
    ):
        ret = rust_uprev.prepare_uprev(
            rust_version=self.version_old, template=self.version_new
        )
        self.assertIsNone(ret)
        mock_command.assert_not_called()

    def test_prepare_uprev_from_json(self):
        ebuild_path = Path("/path/to/the/ebuild")
        json_result = (
            list(self.version_new),
            ebuild_path,
            list(self.bootstrap_version),
        )
        expected = rust_uprev.PreparedUprev(
            self.version_new,
            Path(ebuild_path),
            self.bootstrap_version,
        )
        actual = rust_uprev.prepare_uprev_from_json(json_result)
        self.assertEqual(expected, actual)


class ToggleProfileData(unittest.TestCase):
    """Tests functionality to include or exclude profile data from SRC_URI."""

    ebuild_with_profdata = """
# Some text here.
INCLUDE_PROFDATA_IN_SRC_URI=yes
some code here
"""

    ebuild_without_profdata = """
# Some text here.
INCLUDE_PROFDATA_IN_SRC_URI=
some code here
"""

    ebuild_unexpected_content = """
# Does not contain OMIT_PROFDATA_FROM_SRC_URI assignment
"""

    def setUp(self):
        self.mock_read_text = start_mock(self, "pathlib.Path.read_text")

    def test_turn_off_profdata(self):
        # Test that a file with profdata on is rewritten to a file with
        # profdata off.
        self.mock_read_text.return_value = self.ebuild_with_profdata
        ebuild_file = "/path/to/eclass/cros-rustc.eclass"
        with mock.patch("pathlib.Path.write_text") as mock_write_text:
            rust_uprev.set_include_profdata_src(ebuild_file, include=False)
            mock_write_text.assert_called_once_with(
                self.ebuild_without_profdata, encoding="utf-8"
            )

    def test_turn_on_profdata(self):
        # Test that a file with profdata off is rewritten to a file with
        # profdata on.
        self.mock_read_text.return_value = self.ebuild_without_profdata
        ebuild_file = "/path/to/eclass/cros-rustc.eclass"
        with mock.patch("pathlib.Path.write_text") as mock_write_text:
            rust_uprev.set_include_profdata_src(ebuild_file, include=True)
            mock_write_text.assert_called_once_with(
                self.ebuild_with_profdata, encoding="utf-8"
            )

    def test_turn_on_profdata_fails_if_no_assignment(self):
        # Test that if the string the code expects to find is not found,
        # this causes an exception and the file is not overwritten.
        self.mock_read_text.return_value = self.ebuild_unexpected_content
        ebuild_file = "/path/to/eclass/cros-rustc.eclass"
        with mock.patch("pathlib.Path.write_text") as mock_write_text:
            with self.assertRaises(Exception):
                rust_uprev.set_include_profdata_src(ebuild_file, include=False)
            mock_write_text.assert_not_called()


class UpdateBootstrapVersionTest(unittest.TestCase):
    """Tests for update_bootstrap_version step in rust_uprev"""

    ebuild_file_before = """
BOOTSTRAP_VERSION="1.2.0"
    """
    ebuild_file_after = """
BOOTSTRAP_VERSION="1.3.6"
    """

    def setUp(self):
        self.mock_read_text = start_mock(self, "pathlib.Path.read_text")

    def test_success(self):
        self.mock_read_text.return_value = self.ebuild_file_before
        # ebuild_file and new bootstrap version are deliberately different
        ebuild_file = "/path/to/rust/cros-rustc.eclass"
        with mock.patch("pathlib.Path.write_text") as mock_write_text:
            rust_uprev.update_bootstrap_version(
                ebuild_file, rust_uprev.RustVersion.parse("1.3.6")
            )
            mock_write_text.assert_called_once_with(
                self.ebuild_file_after, encoding="utf-8"
            )

    def test_fail_when_ebuild_misses_a_variable(self):
        self.mock_read_text.return_value = ""
        ebuild_file = "/path/to/rust/rust-1.3.5.ebuild"
        with self.assertRaises(RuntimeError) as context:
            rust_uprev.update_bootstrap_version(
                ebuild_file, rust_uprev.RustVersion.parse("1.2.0")
            )
        self.assertEqual(
            "BOOTSTRAP_VERSION not found in /path/to/rust/rust-1.3.5.ebuild",
            str(context.exception),
        )


class UpdateManifestTest(unittest.TestCase):
    """Tests for update_manifest step in rust_uprev"""

    @mock.patch.object(rust_uprev, "ebuild_actions")
    def test_update_manifest(self, mock_run):
        ebuild_file = Path("/path/to/rust/rust-1.1.1.ebuild")
        rust_uprev.update_manifest(ebuild_file)
        mock_run.assert_called_once_with("rust", ["manifest"])


class UpdateBootstrapEbuildTest(unittest.TestCase):
    """Tests for rust_uprev.update_bootstrap_ebuild()"""

    def test_update_bootstrap_ebuild(self):
        # The update should do two things:
        # 1. Create a copy of rust-bootstrap's ebuild with the
        #    new version number.
        # 2. Add the old PV to RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE.
        with tempfile.TemporaryDirectory() as tmpdir_str, mock.patch.object(
            rust_uprev, "find_ebuild_path"
        ) as mock_find_ebuild:
            tmpdir = Path(tmpdir_str)
            bootstrapdir = Path.joinpath(tmpdir, "rust-bootstrap")
            bootstrapdir.mkdir()
            old_ebuild = bootstrapdir.joinpath("rust-bootstrap-1.45.2.ebuild")
            old_ebuild.write_text(
                encoding="utf-8",
                data="""
some text
RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
\t1.43.1
\t1.44.1
)
some more text
""",
            )
            mock_find_ebuild.return_value = old_ebuild
            rust_uprev.update_bootstrap_ebuild(rust_uprev.RustVersion(1, 46, 0))
            new_ebuild = bootstrapdir.joinpath("rust-bootstrap-1.46.0.ebuild")
            self.assertTrue(new_ebuild.exists())
            text = new_ebuild.read_text(encoding="utf-8")
            self.assertEqual(
                text,
                """
some text
RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=(
\t1.43.1
\t1.44.1
\t1.45.2
)
some more text
""",
            )


class UpdateRustPackagesTests(unittest.TestCase):
    """Tests for update_rust_packages step."""

    def setUp(self):
        self.old_version = rust_uprev.RustVersion(1, 1, 0)
        self.current_version = rust_uprev.RustVersion(1, 2, 3)
        self.new_version = rust_uprev.RustVersion(1, 3, 5)
        self.ebuild_file = os.path.join(
            rust_uprev.RUST_PATH, "rust-{self.new_version}.ebuild"
        )

    def test_add_new_rust_packages(self):
        package_before = (
            f"dev-lang/rust-{self.old_version}\n"
            f"dev-lang/rust-{self.current_version}"
        )
        package_after = (
            f"dev-lang/rust-{self.old_version}\n"
            f"dev-lang/rust-{self.current_version}\n"
            f"dev-lang/rust-{self.new_version}"
        )
        mock_open = mock.mock_open(read_data=package_before)
        with mock.patch("builtins.open", mock_open):
            rust_uprev.update_rust_packages(
                "dev-lang/rust", self.new_version, add=True
            )
        mock_open.return_value.__enter__().write.assert_called_once_with(
            package_after
        )

    def test_remove_old_rust_packages(self):
        package_before = (
            f"dev-lang/rust-{self.old_version}\n"
            f"dev-lang/rust-{self.current_version}\n"
            f"dev-lang/rust-{self.new_version}"
        )
        package_after = (
            f"dev-lang/rust-{self.current_version}\n"
            f"dev-lang/rust-{self.new_version}"
        )
        mock_open = mock.mock_open(read_data=package_before)
        with mock.patch("builtins.open", mock_open):
            rust_uprev.update_rust_packages(
                "dev-lang/rust", self.old_version, add=False
            )
        mock_open.return_value.__enter__().write.assert_called_once_with(
            package_after
        )


class RustUprevOtherStagesTests(unittest.TestCase):
    """Tests for other steps in rust_uprev"""

    def setUp(self):
        self.old_version = rust_uprev.RustVersion(1, 1, 0)
        self.current_version = rust_uprev.RustVersion(1, 2, 3)
        self.new_version = rust_uprev.RustVersion(1, 3, 5)
        self.ebuild_file = os.path.join(
            rust_uprev.RUST_PATH, "rust-{self.new_version}.ebuild"
        )

    @mock.patch.object(shutil, "copyfile")
    @mock.patch.object(subprocess, "check_call")
    def test_create_rust_ebuild(self, mock_call, mock_copy):
        template_ebuild = f"/path/to/rust-{self.current_version}-r2.ebuild"
        rust_uprev.create_ebuild(
            template_ebuild, "dev-lang/rust", self.new_version
        )
        mock_copy.assert_called_once_with(
            template_ebuild,
            rust_uprev.RUST_PATH.joinpath(f"rust-{self.new_version}.ebuild"),
        )
        mock_call.assert_called_once_with(
            ["git", "add", f"rust-{self.new_version}.ebuild"],
            cwd=rust_uprev.RUST_PATH,
        )

    @mock.patch.object(shutil, "copyfile")
    @mock.patch.object(subprocess, "check_call")
    def test_create_rust_host_ebuild(self, mock_call, mock_copy):
        template_ebuild = f"/path/to/rust-host-{self.current_version}-r2.ebuild"
        rust_uprev.create_ebuild(
            template_ebuild, "dev-lang/rust-host", self.new_version
        )
        mock_copy.assert_called_once_with(
            template_ebuild,
            rust_uprev.EBUILD_PREFIX.joinpath(
                f"dev-lang/rust-host/rust-host-{self.new_version}.ebuild"
            ),
        )
        mock_call.assert_called_once_with(
            ["git", "add", f"rust-host-{self.new_version}.ebuild"],
            cwd=rust_uprev.EBUILD_PREFIX.joinpath("dev-lang/rust-host"),
        )

    @mock.patch.object(rust_uprev, "find_ebuild_for_package")
    @mock.patch.object(subprocess, "check_call")
    def test_remove_rust_bootstrap_version(self, mock_call, *_args):
        bootstrap_path = os.path.join(
            rust_uprev.RUST_PATH, "..", "rust-bootstrap"
        )
        rust_uprev.remove_rust_bootstrap_version(
            self.old_version, lambda *x: ()
        )
        mock_call.has_calls(
            [
                [
                    "git",
                    "rm",
                    os.path.join(
                        bootstrap_path,
                        "files",
                        f"rust-bootstrap-{self.old_version}-*.patch",
                    ),
                ],
                [
                    "git",
                    "rm",
                    os.path.join(
                        bootstrap_path,
                        f"rust-bootstrap-{self.old_version}.ebuild",
                    ),
                ],
            ]
        )

    @mock.patch.object(subprocess, "check_call")
    def test_remove_virtual_rust(self, mock_call):
        with tempfile.TemporaryDirectory() as tmpdir:
            ebuild_path = Path(
                tmpdir, f"virtual/rust/rust-{self.old_version}.ebuild"
            )
            os.makedirs(ebuild_path.parent)
            ebuild_path.touch()
            with mock.patch("rust_uprev.EBUILD_PREFIX", Path(tmpdir)):
                rust_uprev.remove_virtual_rust(self.old_version)
                mock_call.assert_called_once_with(
                    ["git", "rm", str(ebuild_path.name)], cwd=ebuild_path.parent
                )

    @mock.patch.object(subprocess, "check_call")
    def test_remove_virtual_rust_with_symlink(self, mock_call):
        with tempfile.TemporaryDirectory() as tmpdir:
            ebuild_path = Path(
                tmpdir, f"virtual/rust/rust-{self.old_version}.ebuild"
            )
            symlink_path = Path(
                tmpdir, f"virtual/rust/rust-{self.old_version}-r14.ebuild"
            )
            os.makedirs(ebuild_path.parent)
            ebuild_path.touch()
            symlink_path.symlink_to(ebuild_path.name)
            with mock.patch("rust_uprev.EBUILD_PREFIX", Path(tmpdir)):
                rust_uprev.remove_virtual_rust(self.old_version)
                mock_call.assert_has_calls(
                    [
                        mock.call(
                            ["git", "rm", ebuild_path.name],
                            cwd=ebuild_path.parent,
                        ),
                        mock.call(
                            ["git", "rm", symlink_path.name],
                            cwd=ebuild_path.parent,
                        ),
                    ],
                    any_order=True,
                )

    @mock.patch.object(rust_uprev, "find_ebuild_path")
    @mock.patch.object(shutil, "copyfile")
    @mock.patch.object(subprocess, "check_call")
    def test_update_virtual_rust(self, mock_call, mock_copy, mock_find_ebuild):
        ebuild_path = Path(
            f"/some/dir/virtual/rust/rust-{self.current_version}.ebuild"
        )
        mock_find_ebuild.return_value = Path(ebuild_path)
        rust_uprev.update_virtual_rust(self.current_version, self.new_version)
        mock_call.assert_called_once_with(
            ["git", "add", f"rust-{self.new_version}.ebuild"],
            cwd=ebuild_path.parent,
        )
        mock_copy.assert_called_once_with(
            ebuild_path.parent.joinpath(f"rust-{self.current_version}.ebuild"),
            ebuild_path.parent.joinpath(f"rust-{self.new_version}.ebuild"),
        )

    @mock.patch.object(os, "listdir")
    def test_find_oldest_rust_version_pass(self, mock_ls):
        oldest_version_name = f"rust-{self.old_version}.ebuild"
        mock_ls.return_value = [
            oldest_version_name,
            f"rust-{self.current_version}.ebuild",
            f"rust-{self.new_version}.ebuild",
        ]
        actual = rust_uprev.find_oldest_rust_version()
        expected = self.old_version
        self.assertEqual(expected, actual)

    @mock.patch.object(os, "listdir")
    def test_find_oldest_rust_version_fail_with_only_one_ebuild(self, mock_ls):
        mock_ls.return_value = [f"rust-{self.new_version}.ebuild"]
        with self.assertRaises(RuntimeError) as context:
            rust_uprev.find_oldest_rust_version()
        self.assertEqual(
            "Expect to find more than one Rust versions", str(context.exception)
        )

    @mock.patch.object(rust_uprev, "get_command_output")
    @mock.patch.object(git, "CreateBranch")
    def test_create_new_repo(self, mock_branch, mock_output):
        mock_output.return_value = ""
        rust_uprev.create_new_repo(self.new_version)
        mock_branch.assert_called_once_with(
            rust_uprev.EBUILD_PREFIX, f"rust-to-{self.new_version}"
        )

    @mock.patch.object(rust_uprev, "run_in_chroot")
    def test_build_cross_compiler(self, mock_run_in_chroot):
        cros_targets = [
            "x86_64-cros-linux-gnu",
            "armv7a-cros-linux-gnueabihf",
            "aarch64-cros-linux-gnu",
        ]
        all_triples = ["x86_64-pc-linux-gnu"] + cros_targets
        rust_ebuild = "RUSTC_TARGET_TRIPLES=(" + "\n\t".join(all_triples) + ")"
        with mock.patch("rust_uprev.find_ebuild_path") as mock_find_ebuild_path:
            mock_path = mock.Mock()
            mock_path.read_text.return_value = rust_ebuild
            mock_find_ebuild_path.return_value = mock_path
            rust_uprev.build_cross_compiler(rust_uprev.RustVersion(7, 3, 31))

        mock_run_in_chroot.assert_called_once_with(
            ["sudo", "emerge", "-j", "-G"]
            + [f"cross-{x}/gcc" for x in cros_targets + ["arm-none-eabi"]]
        )


if __name__ == "__main__":
    unittest.main()
