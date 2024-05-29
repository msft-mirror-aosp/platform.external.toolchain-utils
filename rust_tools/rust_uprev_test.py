# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for rust_uprev.py"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from cros_utils import git_utils


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


class FindStableRustVersionTest(unittest.TestCase):
    """Tests for rust_uprev.find_stable_rust_version."""

    def test_with_symlinks(self):
        with tempfile.TemporaryDirectory() as t:
            tmpdir = Path(t)
            rust_1_50_0_ebuild = tmpdir / "rust-1.50.0.ebuild"
            rust_1_50_0_r1_ebuild = tmpdir / "rust-1.50.0-r1.ebuild"
            rust_9999_ebuild = tmpdir / "rust-9999.ebuild"
            rust_1_50_0_ebuild.touch()
            rust_1_50_0_r1_ebuild.symlink_to(rust_1_50_0_ebuild)
            rust_9999_ebuild.touch()
            with mock.patch("rust_uprev.RUST_PATH", tmpdir):
                actual = rust_uprev.find_stable_rust_version()
                self.assertEqual(actual, rust_uprev.RustVersion(1, 50, 0))


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


class UpdateEbuildVariableVersionTest(unittest.TestCase):
    """Tests for update_ebuild_variable_version function in rust_uprev"""

    ebuild_file_before = """
SOME_OTHER_VAR=foo
# Comment
BOOTSTRAP_VERSION="1.2.0"
SOME_OTHER_VAR2=baz
    """
    ebuild_file_after = """
SOME_OTHER_VAR=foo
# Comment
BOOTSTRAP_VERSION="1.3.6"
SOME_OTHER_VAR2=baz
    """

    def setUp(self):
        self.mock_read_text = start_mock(self, "pathlib.Path.read_text")

    def test_success(self):
        self.mock_read_text.return_value = self.ebuild_file_before
        # ebuild_file and new bootstrap version are deliberately different
        ebuild_file = "/path/to/rust/cros-rustc.eclass"
        with mock.patch("pathlib.Path.write_text") as mock_write_text:
            rust_uprev.update_ebuild_variable_version(
                ebuild_file,
                "BOOTSTRAP_VERSION",
                rust_uprev.RustVersion.parse("1.3.6"),
            )
            mock_write_text.assert_called_once_with(
                self.ebuild_file_after, encoding="utf-8"
            )

    def test_fail_when_ebuild_misses_a_variable(self):
        self.mock_read_text.return_value = ""
        ebuild_file = "/path/to/rust/rust-1.3.5.ebuild"
        with self.assertRaisesRegex(
            RuntimeError,
            r"^BOOTSTRAP_VERSION not found in "
            r"/path/to/rust/rust-1\.3\.5\.ebuild$",
        ):
            rust_uprev.update_ebuild_variable_version(
                ebuild_file,
                "BOOTSTRAP_VERSION",
                rust_uprev.RustVersion.parse("1.2.0"),
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

    @mock.patch.object(rust_uprev, "get_command_output")
    @mock.patch.object(git_utils, "create_branch")
    def test_create_rust_upgrade_branch(self, mock_create_branch, mock_output):
        mock_output.return_value = ""
        rust_uprev.create_rust_uprev_branch(self.new_version)
        mock_create_branch.assert_called_once_with(
            rust_uprev.EBUILD_PREFIX, branch_name=f"rust-to-{self.new_version}"
        )

    @mock.patch.object(rust_uprev, "get_command_output")
    @mock.patch.object(git_utils, "create_branch")
    def test_create_rust_upgrade_branch_raises_if_unclean(
        self, mock_create_branch, mock_output
    ):
        mock_output.return_value = "some file has modifications"
        with self.assertRaisesRegex(RuntimeError, ".*uncommitted changes.*"):
            rust_uprev.create_rust_uprev_branch(self.new_version)
        mock_create_branch.assert_not_called()

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
