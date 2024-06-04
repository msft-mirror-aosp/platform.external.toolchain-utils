# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the latest LLVM version's hash."""

import argparse
import contextlib
import dataclasses
import functools
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterator, Optional, Tuple, Union

from cros_utils import git_utils
from llvm_tools import chroot
from llvm_tools import cros_llvm_repo
from llvm_tools import git_llvm_rev
from llvm_tools import llvm_next
from llvm_tools import manifest_utils
from llvm_tools import subprocess_helpers


_LLVM_GIT_URL = (
    "https://chromium.googlesource.com/external/github.com/llvm/llvm-project"
)

KNOWN_HASH_SOURCES = (
    "google3",
    "google3-unstable",
    "llvm",
    "llvm-next",
    "tot",
)


def GetVersionFrom(src_dir: Union[Path, str], git_hash: str) -> int:
    """Obtain an SVN-style version number based on the LLVM git hash passed in.

    Args:
        src_dir: LLVM's source directory.
        git_hash: The git hash.

    Returns:
        An SVN-style version number associated with the git hash.
    """

    version = git_llvm_rev.translate_sha_to_rev(
        git_llvm_rev.LLVMConfig(remote="origin", dir=src_dir), git_hash
    )
    # Note: branches aren't supported
    assert version.branch == git_llvm_rev.MAIN_BRANCH, version.branch
    return version.number


def GetGitHashFrom(src_dir: Union[Path, str], version: int) -> str:
    """Finds the commit hash(es) of the LLVM version in the git log history.

    Args:
        src_dir: The LLVM source tree.
        version: The version number.

    Returns:
        A git hash string corresponding to the version number.

    Raises:
        subprocess.CalledProcessError: Failed to find a git hash.
    """

    return git_llvm_rev.translate_rev_to_sha(
        git_llvm_rev.LLVMConfig(remote="origin", dir=src_dir),
        git_llvm_rev.Rev(branch=git_llvm_rev.MAIN_BRANCH, number=version),
    )


def ParseLLVMMajorVersion(cmakelist: str) -> Optional[str]:
    """Reads CMakeList.txt file contents for LLVMMajor Version.

    Args:
        cmakelist: contents of CMakeList.txt

    Returns:
        The major version number as a string, or None if it couldn't be found.
    """
    match = re.search(
        r"\n\s+set\(LLVM_VERSION_MAJOR (?P<major>\d+)\)", cmakelist
    )
    if not match:
        return None
    return match.group("major")


@functools.lru_cache(maxsize=1)
def GetLLVMMajorVersion(git_hash: Optional[str] = None) -> str:
    """Reads llvm/CMakeList.txt file contents for LLVMMajor Version.

    Args:
        git_hash: git hash of llvm version as string or None for top of trunk

    Returns:
        The major version number as a string

    Raises:
        ValueError: The major version cannot be parsed from cmakelist or
          there was a failure to checkout git_hash version
        FileExistsError: The src directory doe not contain CMakeList.txt
    """
    # b/325895866#comment36: the LLVM version number was moved from
    # `llvm/CMakeLists.txt` to `cmake/Modules/LLVMVersion.cmake` in upstream
    # commit 81e20472a0c5a4a8edc5ec38dc345d580681af81 (r530225). Until we no
    # longer care about looking before that, we need to support searching both
    # files.
    cmakelists_paths = (
        "llvm/CMakeLists.txt",
        "cmake/Modules/LLVMVersion.cmake",
    )

    repo = GetCachedUpToDateReadOnlyLLVMRepo()
    ref = git_hash if git_hash else "HEAD"
    for path in cmakelists_paths:
        contents = git_utils.maybe_show_file_at_commit(repo.path, ref, path)
        if contents is None:
            # Ignore the file if it doesn't exist yet.
            continue
        if version := ParseLLVMMajorVersion(contents):
            return version

    raise ValueError(
        f"Major version could not be parsed from any of {cmakelists_paths}"
    )


def _GetToolchainUtilsCopyOfLLVMProject() -> Path:
    """Inits and returns ${toolchain_utils}/llvm_tools/llvm-project-copy.

    Returns:
        The absolute path to the 'llvm-project-copy' directory in 'llvm_tools'
    """
    # NOTE: At the moment, the initial sync of this is not thread-safe. It'd be
    # nice to have a flock of some sort of toolchain-utils-local stamp for
    # that.
    llvm_project_copy = Path(__file__).resolve().parent / "llvm-project-copy"
    if llvm_project_copy.is_dir():
        return llvm_project_copy

    print(
        f"llvm-project checkout requested; checking out {llvm_project_copy}.\n"
        "This may take a while, but only has to be done once.",
        file=sys.stderr,
    )
    llvm_project_copy.mkdir()
    LLVMHash().CloneLLVMRepo(str(llvm_project_copy))
    return llvm_project_copy


@dataclasses.dataclass(frozen=True)
class ReadOnlyLLVMRepo:
    """Describes an LLVM repository, and provides some useful ops on it.

    Strictly speaking, `read-only` is a bit of a misnomer: the git data of this
    repo may be updated by users of this class. The expectation is that the
    working tree won't be modified, though.
    """

    # Path to the repository.
    path: Path
    # The name of the remote to query.
    remote: str
    # The ref that points to the upstream's main branch.
    upstream_main: str

    def GetRevisionFromHash(self, git_hash: str) -> int:
        """Converts a SHA to an svn-like revision."""
        version = git_llvm_rev.translate_sha_to_rev(
            git_llvm_rev.LLVMConfig(remote=self.remote, dir=self.path), git_hash
        )
        # Note: branches aren't supported. Always match against
        # `git_llvm_rev.MAIN_BRANCH` instead of `upstream_main`, since
        # `git_llvm_rev` doesn't acknowledge `upstream_main`.
        assert version.branch == git_llvm_rev.MAIN_BRANCH, (
            "Revisions only make sense on main, but given git hash was "
            f"on {version.branch}"
        )
        return version.number

    def GetHashFromRevision(self, revision: int) -> str:
        """Converts a svn-like revision to a SHA on main."""
        return git_llvm_rev.translate_rev_to_sha(
            git_llvm_rev.LLVMConfig(remote=self.remote, dir=self.path),
            git_llvm_rev.Rev(branch=self.upstream_main, number=revision),
        )


def GetReadOnlyLLVMRepo() -> ReadOnlyLLVMRepo:
    """Returns a read-only LLVM repository."""
    if cros_llvm := cros_llvm_repo.try_get_path():
        return ReadOnlyLLVMRepo(
            path=cros_llvm,
            remote=cros_llvm_repo.UPSTREAM_REMOTE,
            upstream_main=cros_llvm_repo.UPSTREAM_MAIN,
        )
    return ReadOnlyLLVMRepo(
        path=_GetToolchainUtilsCopyOfLLVMProject(),
        remote="origin",
        upstream_main=git_llvm_rev.MAIN_BRANCH,
    )


def GetUpToDateReadOnlyLLVMRepo() -> ReadOnlyLLVMRepo:
    """GetReadOnlyLLVMRepo, with an added `git fetch` step."""
    repo = GetReadOnlyLLVMRepo()
    logging.info("Updating LLVM repository at %s...", repo.path)
    subprocess.run(
        ["git", "fetch", "--quiet", repo.remote, repo.upstream_main],
        check=True,
        cwd=repo.path,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    return repo


@functools.lru_cache(1)
def GetCachedUpToDateReadOnlyLLVMRepo() -> ReadOnlyLLVMRepo:
    """GetUpToDateReadOnlyLLVMRepo, but will cache the result."""
    return GetUpToDateReadOnlyLLVMRepo()


def GetGoogle3LLVMVersion(stable: bool) -> int:
    """Gets the latest google3 LLVM version.

    Args:
        stable: boolean, use the stable version or the unstable version

    Returns:
        The latest LLVM SVN version as an integer.

    Raises:
        subprocess.CalledProcessError: An invalid path has been provided to the
        `cat` command.
    """
    subdir = "stable" if stable else "llvm_unstable"
    cmd = [
        "cat",
        os.path.join(
            "/google/src/head/depot/google3/third_party/crosstool/v18",
            subdir,
            "installs/llvm/git_origin_rev_id",
        ),
    ]
    git_hash = subprocess_helpers.check_output(cmd).rstrip()
    return GetCachedUpToDateReadOnlyLLVMRepo().GetRevisionFromHash(git_hash)


def IsSvnOption(svn_option: str) -> Union[int, str]:
    """Validates whether the argument (string) is a git hash option.

    The argument is used to find the git hash of LLVM.

    Args:
        svn_option: The option passed in as a command line argument.

    Returns:
        lowercase svn_option if it is a known hash source, otherwise the
        svn_option as an int

    Raises:
        ValueError: Invalid svn option provided.
    """

    if svn_option.lower() in KNOWN_HASH_SOURCES:
        return svn_option.lower()

    try:
        svn_version = int(svn_option)

        return svn_version

    # Unable to convert argument to an int, so the option is invalid.
    #
    # Ex: 'one'.
    except ValueError:
        pass

    raise ValueError("Invalid LLVM git hash option provided: %s" % svn_option)


def GetLLVMHashAndVersionFromSVNOption(
    svn_option: Union[int, str]
) -> Tuple[str, int]:
    """Gets the LLVM hash and LLVM version based off of the svn option.

    Args:
        svn_option: A valid svn option obtained from the command line.
          Ex. 'google3', 'tot', or <svn_version> such as 365123.

    Returns:
        A tuple that is the LLVM git hash and LLVM version.
    """

    new_llvm_hash = LLVMHash()
    llvm_repo = GetCachedUpToDateReadOnlyLLVMRepo()
    # Determine which LLVM git hash to retrieve.
    if svn_option == "tot":
        git_hash = new_llvm_hash.GetTopOfTrunkGitHash()
        version = llvm_repo.GetRevisionFromHash(git_hash)
    elif isinstance(svn_option, int):
        version = svn_option
        git_hash = llvm_repo.GetHashFromRevision(version)
    else:
        assert svn_option in ("google3", "google3-unstable")
        version = GetGoogle3LLVMVersion(stable=svn_option == "google3")
        git_hash = llvm_repo.GetHashFromRevision(version)

    return git_hash, version


def GetCrOSCurrentLLVMHash(chromeos_root: Path) -> str:
    """Retrieves the current ChromeOS LLVM hash.

    Args:
        chromeos_root: A ChromeOS source tree root.

    Raises:
        AssertionError if `chromeos_root` isn't a CrOS tree root.
        ManifestValueError if the toolchain manifest doesn't match the
        expected structure.
    """
    assert chroot.IsChromeOSRoot(
        chromeos_root
    ), f"{chromeos_root} isn't the root of a ChromeOS checkout"
    return manifest_utils.extract_current_llvm_hash(chromeos_root)


class LLVMHash:
    """Provides methods to retrieve a LLVM hash."""

    @staticmethod
    @contextlib.contextmanager
    def CreateTempDirectory() -> Iterator:
        temp_dir = tempfile.mkdtemp()

        try:
            yield temp_dir
        finally:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def CloneLLVMRepo(self, temp_dir: str) -> None:
        """Clones the LLVM repo.

        Args:
            temp_dir: The temporary directory to clone the repo to.

        Raises:
            ValueError: Failed to clone the LLVM repo.
        """
        clone_cmd = ["git", "clone", _LLVM_GIT_URL, temp_dir]
        clone_cmd_obj = subprocess.run(
            clone_cmd, check=False, stderr=subprocess.PIPE
        )
        if clone_cmd_obj.returncode:
            raise ValueError(
                "Failed to clone the LLVM repo; stderr: "
                f"{repr(clone_cmd_obj.stderr)}"
            )

    def GetLLVMHash(self, version: int) -> str:
        """Retrieves the LLVM hash corresponding to the LLVM version passed in.

        Args:
            version: The LLVM version to use as a delimiter.

        Returns:
            The hash as a string that corresponds to the LLVM version.
        """
        return GetCachedUpToDateReadOnlyLLVMRepo().GetHashFromRevision(version)

    def GetCrOSCurrentLLVMHash(self, chromeos_tree: Path) -> str:
        """Retrieves the current ChromeOS LLVM hash."""
        return GetCrOSCurrentLLVMHash(chromeos_tree)

    def GetCrOSLLVMNextHash(self) -> str:
        """Retrieves the current ChromeOS llvm-next hash."""
        return llvm_next.LLVM_NEXT_HASH

    def GetGoogle3LLVMHash(self) -> str:
        """Retrieves the google3 LLVM hash."""
        return self.GetLLVMHash(GetGoogle3LLVMVersion(stable=True))

    def GetGoogle3UnstableLLVMHash(self) -> str:
        """Retrieves the LLVM hash of google3's unstable compiler."""
        return self.GetLLVMHash(GetGoogle3LLVMVersion(stable=False))

    def GetTopOfTrunkGitHash(self) -> str:
        """Gets the latest git hash from top of trunk of LLVM."""

        path_to_main_branch = "refs/heads/main"
        llvm_tot_git_hash = subprocess_helpers.check_output(
            ["git", "ls-remote", _LLVM_GIT_URL, path_to_main_branch]
        )
        return llvm_tot_git_hash.rstrip().split()[0]


def main() -> None:
    """Prints the git hash of LLVM.

    Parses the command line for the optional command line
    arguments.
    """
    my_dir = Path(__file__).parent.resolve()

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    # Create parser and add optional command-line arguments.
    parser = argparse.ArgumentParser(description="Finds the LLVM hash.")
    parser.add_argument(
        "--llvm_version",
        type=IsSvnOption,
        required=True,
        help="which git hash of LLVM to find. Either a svn revision, or one "
        "of %s" % sorted(KNOWN_HASH_SOURCES),
    )
    parser.add_argument(
        "--chromeos_tree",
        type=Path,
        help="""
        Path to a ChromeOS tree. If not passed, one will be inferred. If none
        can be inferred, this script will fail.
        """,
    )

    # Parse command-line arguments.
    args_output = parser.parse_args()

    cur_llvm_version = args_output.llvm_version
    chromeos_tree = args_output.chromeos_tree
    if not chromeos_tree:
        # Try to infer this unconditionally, so mishandling of this script can
        # be more easily detected (which allows more flexibility in the
        # implementation in the future for things outside of what directly
        # needs this value).
        chromeos_tree = chroot.FindChromeOSRootAbove(my_dir)

    new_llvm_hash = LLVMHash()
    if isinstance(cur_llvm_version, int):
        # Find the git hash of the specific LLVM version.
        print(new_llvm_hash.GetLLVMHash(cur_llvm_version))
    elif cur_llvm_version == "llvm":
        print(new_llvm_hash.GetCrOSCurrentLLVMHash(chromeos_tree))
    elif cur_llvm_version == "llvm-next":
        print(new_llvm_hash.GetCrOSLLVMNextHash())
    elif cur_llvm_version == "google3":
        print(new_llvm_hash.GetGoogle3LLVMHash())
    elif cur_llvm_version == "google3-unstable":
        print(new_llvm_hash.GetGoogle3UnstableLLVMHash())
    else:
        assert cur_llvm_version == "tot"
        print(new_llvm_hash.GetTopOfTrunkGitHash())
