# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up src/third_party/llvm-project for cros workon from an LLVM ebuild."""

import argparse
import dataclasses
import logging
from pathlib import Path
import shlex
import subprocess
from typing import Iterable, List, Optional, Union

from cros_utils import cros_paths
from llvm_tools import cros_llvm_repo
from llvm_tools import git_llvm_rev
from llvm_tools import llvm_project_base_commit


@dataclasses.dataclass(frozen=True)
class LLVMSourceDir:
    """An LLVM source dir, with convenient additional accessors."""

    path: Path

    def cros_workon_subdir(self):
        """Returns the subdir used for communicating with the ebuild."""
        return self.path / ".ebuild"


def apply_patches(
    llvm_dir: LLVMSourceDir,
    patch_manager: Path,
    patch_metadata_file: Path,
    current_rev: git_llvm_rev.Rev,
    continue_on_failure: bool = False,
) -> None:
    """Applies patches using `patch_manager` to `llvm_dir`."""
    cmd: List[Union[str, Path]] = [
        patch_manager,
        f"--svn_version={current_rev.number}",
        f"--src_path={llvm_dir.path}",
        f"--patch_metadata_file={patch_metadata_file}",
    ]
    if continue_on_failure:
        cmd.append("--failure_mode=continue")
    subprocess.run(
        cmd,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def write_patch_application_stamp(
    llvm_dir: LLVMSourceDir, package_name: str
) -> None:
    """Writes a stamp file to note that patches have been applied."""
    stamp_path = (
        llvm_dir.cros_workon_subdir()
        / "stamps"
        / "patches_applied"
        / package_name
    )
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.touch()


def try_rev_parse(git_dir: Path, sha: str) -> Optional[str]:
    """Returns the `git rev-parse` output for `sha`.

    Returns:
        None if `sha` can't be resolved, or isn't an object in `git_dir`.
    """
    result = subprocess.run(
        # Note that the `^{object}` suffix is needed so `git rev-parse
        # --verify` actually looks for an object with the given SHA.
        ["git", "rev-parse", "--verify", sha + "^{object}"],
        check=False,
        cwd=git_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8",
    )
    if result.returncode:
        return None
    return result.stdout.strip()


def fetch_and_resolve_sha(llvm_project_dir: Path, sha: str) -> str:
    """Runs `git rev-parse` on `sha`. If that fails, tries fetching the repo."""
    if r := try_rev_parse(llvm_project_dir, sha):
        return r
    logging.info("Couldn't resolve SHA %s locally; fetching upstream...", sha)
    cros_llvm_repo.fetch_upstream(llvm_project_dir)
    if r := try_rev_parse(llvm_project_dir, sha):
        return r
    raise ValueError(f"SHA {sha} can't be resolved in {llvm_project_dir}")


def _search_overlays_for_ebuild_dir(
    package_name: str, overlays: Iterable[Path]
) -> Path:
    for overlay in overlays:
        potential_path = overlay / package_name
        potential_ebuild = potential_path / f"{potential_path.name}-9999.ebuild"
        if potential_ebuild.is_file():
            return potential_path
    raise ValueError(f"Could not find 9999 ebuild for {package_name}")


def main(argv: List[str]) -> None:
    cros_root = cros_paths.script_chromiumos_checkout_or_exit()

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--llvm-dir",
        type=lambda x: LLVMSourceDir(path=Path(x)),
        default=LLVMSourceDir(path=cros_root / cros_paths.LLVM_PROJECT),
        help="Path containing a directory with llvm sources.",
    )
    parser.add_argument(
        "--ebuild-dir",
        type=Path,
        help="""
        Directory of the ebuild we're trying to set up. If this isn't
        specified, `--package` should be specified, and this will be
        autodetected. Example: ${cros_overlay}/sys-devel/llvm.
        """,
    )
    parser.add_argument(
        "--clean-llvm",
        action="store_true",
        help="""
        If passed, a series of commands will be run to reset the LLVM directory
        to HEAD prior to applying patches. **This flag deletes all staged
        unstaged changes, and deletes all untracked files**.
        """,
    )
    parser.add_argument(
        "--package",
        help="""
        Name of the package to set up for, in the form '${CATEGORY}/${PN}'.
        This must be provided unless `--ebuild-dir` is provided. Example:
        sys-devel/llvm.
        """,
    )
    parser.add_argument(
        "--no-commit",
        dest="commit",
        action="store_false",
        help="Don't create a commit with all changes applied.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Keep applying later patches even if an earlier patch fails.",
    )
    parser.add_argument(
        "--workon-board",
        dest="workon_board",
        help="""
        Ensure cros workon for the given board after applying changes.
        Set to 'host' for working on the host system, and not a board.
        """,
    )

    checkout_group = parser.add_mutually_exclusive_group(required=True)
    checkout_group.add_argument(
        "--checkout",
        help="""
        If specified, the llvm directory will be checked out to the given SHA.
        """,
    )
    # The value of this isn't used anywhere; it's just used as an explicit
    # nudge for checking LLVM out.
    checkout_group.add_argument(
        "--no-checkout",
        action="store_true",
        help="""
        Don't check llvm-project out to anything special before running. Useful
        if you'd like to, for example, workon multiple LLVM projects
        simultaneously and have already called `setup_for_workon` on another
        one.
        """,
    )
    opts = parser.parse_args(argv)

    ebuild_dir = opts.ebuild_dir
    package = opts.package
    if not ebuild_dir and not package:
        parser.error(
            "At least one of --ebuild-dir or --package must be specified."
        )

    if not ebuild_dir:
        # All of these are either in toolchains-overlay or chromiumos-overlay.
        overlays = (
            cros_root / d
            for d in (
                cros_paths.TOOLCHAINS_OVERLAY,
                cros_paths.CHROMIUMOS_OVERLAY,
            )
        )
        ebuild_dir = _search_overlays_for_ebuild_dir(package, overlays)
        logging.info("Ebuild directory is %s.", ebuild_dir)
    elif not package:
        package = f"{ebuild_dir.parent.name}/{ebuild_dir.name}"
        logging.info("Package is %s.", package)

    git_housekeeping_commands: List[List[Union[Path, str]]] = []
    if opts.clean_llvm:
        git_housekeeping_commands.extend(
            (
                ["git", "clean", "-fd", "."],
                ["git", "reset", "--hard", "HEAD"],
            )
        )

    if opts.checkout is not None:
        sha = fetch_and_resolve_sha(opts.llvm_dir.path, opts.checkout)
        git_housekeeping_commands.append(
            ["git", "checkout", "--quiet", sha],
        )

    for cmd in git_housekeeping_commands:
        subprocess.run(
            cmd,
            cwd=opts.llvm_dir.path,
            check=True,
            stdin=subprocess.DEVNULL,
        )

    rev = git_llvm_rev.translate_sha_to_rev(
        git_llvm_rev.LLVMConfig(
            remote="cros",
            dir=opts.llvm_dir.path,
        ),
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=opts.llvm_dir.path,
            stdin=subprocess.DEVNULL,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        ).stdout.strip(),
    )

    logging.info("Applying patches...")
    files_dir = ebuild_dir / "files"
    apply_patches(
        opts.llvm_dir,
        patch_manager=files_dir / "patch_manager" / "patch_manager.py",
        patch_metadata_file=files_dir / "PATCHES.json",
        current_rev=rev,
        continue_on_failure=opts.continue_on_failure,
    )
    # Assume that the package format is <category>/<name>
    _, package_name = package.split("/")
    write_patch_application_stamp(opts.llvm_dir, package_name)
    logging.info("Applying Gentoo CMakeLists.txt hack...")
    llvm_project_base_commit.write_all_gentoo_cmake_hacks(
        opts.llvm_dir.path,
        chromiumos_overlay=cros_root / cros_paths.CHROMIUMOS_OVERLAY,
    )

    if opts.commit:
        subprocess.run(
            ["git", "add", "."],
            check=True,
            cwd=opts.llvm_dir.path,
            stdin=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "git",
                "commit",
                "--message",
                "Patches applied and markers added.",
            ],
            check=True,
            cwd=opts.llvm_dir.path,
            stdin=subprocess.DEVNULL,
        )

    if not opts.workon_board:
        logging.warning(
            "Didn't ensure 'workon' for any board or host."
            " Make sure you've called 'cros workon [...] start %s'"
            " before building!",
            package,
        )
        return

    if opts.workon_board == "host":
        cmd = ["cros", "workon", "--host", "start", package]
    else:
        cmd = [
            "cros",
            "workon",
            f"-b={opts.workon_board}",
            "start",
            package,
        ]
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    logging.info(
        "Successfully workon-ed: %s", shlex.join([str(c) for c in cmd])
    )
