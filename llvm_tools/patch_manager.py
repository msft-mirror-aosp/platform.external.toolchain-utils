# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A manager for patches."""

import argparse
import enum
import os
from pathlib import Path
import sys
from typing import Callable, Iterable, List, Optional, Tuple

from llvm_tools import failure_modes
from llvm_tools import get_llvm_hash
from llvm_tools import patch_utils
from llvm_tools import subprocess_helpers


class GitBisectionCode(enum.IntEnum):
    """Git bisection exit codes.

    Used when patch_manager.py is in the bisection mode,
    as we need to return in what way we should handle
    certain patch failures.
    """

    GOOD = 0
    """All patches applied successfully."""
    BAD = 1
    """The tested patch failed to apply."""
    SKIP = 125


def GetCommandLineArgs(sys_argv: Optional[List[str]]):
    """Get the required arguments from the command line."""

    # Create parser and add optional command-line arguments.
    parser = argparse.ArgumentParser(description="A manager for patches.")

    # Add argument for the LLVM version to use for patch management.
    parser.add_argument(
        "--svn_version",
        type=int,
        help="the LLVM svn version to use for patch management (determines "
        "whether a patch is applicable). Required when not bisecting.",
    )

    # Add argument for the patch metadata file that is in $FILESDIR.
    parser.add_argument(
        "--patch_metadata_file",
        required=True,
        type=Path,
        help='the absolute path to the .json file in "$FILESDIR/" of the '
        "package which has all the patches and their metadata if applicable",
    )

    # Add argument for the absolute path to the unpacked sources.
    parser.add_argument(
        "--src_path",
        required=True,
        type=Path,
        help="the absolute path to the unpacked LLVM sources",
    )

    # Add argument for the mode of the patch manager when handling failing
    # applicable patches.
    parser.add_argument(
        "--failure_mode",
        default=failure_modes.FailureModes.FAIL,
        type=failure_modes.FailureModes,
        help="the mode of the patch manager when handling failed patches "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--test_patch",
        default="",
        help="The rel_patch_path of the patch we want to bisect the "
        "application of. Not used in other modes.",
    )

    group = parser.add_mutually_exclusive_group()
    # Add argument for the option to us git am to commit patch or
    # just using patch.
    group.add_argument(
        "--git_am",
        action="store_true",
        help="If set, use 'git am' to patch instead of GNU 'patch'. ",
    )

    # Add argument for the option to us git am chromiumos to commit patch or
    # just using patch.
    group.add_argument(
        "--chromiumos_apply",
        action="store_true",
        help="If set, use 'git am' with chromiumos footer edits.",
    )

    # Parse the command line.
    return parser.parse_args(sys_argv)


def GetHEADSVNVersion(src_path):
    """Gets the SVN version of HEAD in the src tree."""
    git_hash = subprocess_helpers.check_output(
        ["git", "-C", src_path, "rev-parse", "HEAD"]
    )
    return get_llvm_hash.GetVersionFrom(src_path, git_hash.rstrip())


def GetCommitHashesForBisection(src_path, good_svn_version, bad_svn_version):
    """Gets the good and bad commit hashes required by `git bisect start`."""

    bad_commit_hash = get_llvm_hash.GetGitHashFrom(src_path, bad_svn_version)

    good_commit_hash = get_llvm_hash.GetGitHashFrom(src_path, good_svn_version)

    return good_commit_hash, bad_commit_hash


def CheckPatchApplies(
    svn_version: int,
    llvm_src_dir: Path,
    patches_json_fp: Path,
    rel_patch_path: str,
) -> GitBisectionCode:
    """Check that a given patch with the rel_patch_path applies in the stack.

    This is used in the bisection mode of the patch manager. It's similiar
    to ApplyAllFromJson, but differs in that the patch with rel_patch_path
    will attempt to apply regardless of its version range, as we're trying
    to identify the SVN version

    Args:
        svn_version: SVN version to test at.
        llvm_src_dir: llvm-project source code diroctory (with a .git).
        patches_json_fp: PATCHES.json filepath.
        rel_patch_path: Relative patch path of the patch we want to check. If
          patches before this patch fail to apply, then the revision is
          skipped.
    """
    with patches_json_fp.open(encoding="utf-8") as f:
        patch_entries = patch_utils.json_to_patch_entries(
            patches_json_fp.parent,
            f,
        )
    with patch_utils.git_clean_context(llvm_src_dir):
        success, _, failed_patches = ApplyPatchAndPrior(
            svn_version,
            llvm_src_dir,
            patch_entries,
            rel_patch_path,
            patch_utils.git_am,
        )
    if success:
        # Everything is good, patch applied successfully.
        print(f"SUCCEEDED applying {rel_patch_path} @ r{svn_version}")
        return GitBisectionCode.GOOD
    if failed_patches and failed_patches[-1].rel_patch_path == rel_patch_path:
        # We attempted to apply this patch, but it failed.
        print(f"FAILED to apply {rel_patch_path} @ r{svn_version}")
        return GitBisectionCode.BAD
    # Didn't attempt to apply the patch, but failed regardless.
    # Skip this revision.
    print(f"SKIPPED {rel_patch_path} @ r{svn_version} due to prior failures")
    return GitBisectionCode.SKIP


def ApplyPatchAndPrior(
    svn_version: int,
    src_dir: Path,
    patch_entries: Iterable[patch_utils.PatchEntry],
    rel_patch_path: str,
    patch_cmd: Optional[Callable] = None,
) -> Tuple[bool, List[patch_utils.PatchEntry], List[patch_utils.PatchEntry]]:
    """Apply a patch, and all patches that apply before it in the patch stack.

    Patches which did not attempt to apply (because their version range didn't
    match and they weren't the patch of interest) do not appear in the output.

    Probably shouldn't be called from outside of CheckPatchApplies, as it
    modifies the source dir contents.

    Returns:
        A tuple where:
            [0]: Did the patch of interest succeed in applying?
            [1]: List of applied patches, potentially containing the patch of
            interest.
            [2]: List of failing patches, potentially containing the patch of
            interest.
    """
    failed_patches: List[patch_utils.PatchEntry] = []
    applied_patches = []
    # We have to apply every patch up to the one we care about,
    # as patches can stack.
    for pe in patch_entries:
        is_patch_of_interest = pe.rel_patch_path == rel_patch_path
        applied, failed_hunks = patch_utils.apply_single_patch_entry(
            svn_version,
            src_dir,
            pe,
            patch_cmd,
            ignore_version_range=is_patch_of_interest,
        )
        meant_to_apply = bool(failed_hunks) or is_patch_of_interest
        if is_patch_of_interest:
            if applied:
                # We applied the patch we wanted to, we can stop.
                applied_patches.append(pe)
                return True, applied_patches, failed_patches
            else:
                # We failed the patch we cared about, we can stop.
                failed_patches.append(pe)
                return False, applied_patches, failed_patches
        else:
            if applied:
                applied_patches.append(pe)
            elif meant_to_apply:
                # Broke before we reached the patch we cared about. Stop.
                failed_patches.append(pe)
                return False, applied_patches, failed_patches
    raise ValueError(f"Did not find patch {rel_patch_path}. " "Does it exist?")


def PrintPatchResults(patch_info: patch_utils.PatchInfo):
    """Prints the results of handling the patches of a package.

    Args:
        patch_info: A dataclass that has information on the patches.
    """

    def _fmt(patches):
        return (str(pe.patch_path()) for pe in patches)

    if patch_info.applied_patches:
        print("\nThe following patches applied successfully:")
        print("\n".join(_fmt(patch_info.applied_patches)))

    if patch_info.failed_patches:
        print("\nThe following patches failed to apply:")
        print("\n".join(_fmt(patch_info.failed_patches)))

    if patch_info.non_applicable_patches:
        print("\nThe following patches were not applicable:")
        print("\n".join(_fmt(patch_info.non_applicable_patches)))

    if patch_info.modified_metadata:
        print(
            "\nThe patch metadata file %s has been modified"
            % os.path.basename(patch_info.modified_metadata)
        )

    if patch_info.disabled_patches:
        print("\nThe following patches were disabled:")
        print("\n".join(_fmt(patch_info.disabled_patches)))

    if patch_info.removed_patches:
        print(
            "\nThe following patches were removed from the patch metadata file:"
        )
        for cur_patch_path in patch_info.removed_patches:
            print("%s" % os.path.basename(cur_patch_path))


def main(sys_argv: List[str]):
    """Applies patches to the source tree and takes action on a failed patch."""

    args_output = GetCommandLineArgs(sys_argv)

    llvm_src_dir = Path(args_output.src_path)
    if not llvm_src_dir.is_dir():
        raise ValueError(f"--src_path arg {llvm_src_dir} is not a directory")
    patches_json_fp = Path(args_output.patch_metadata_file)
    if not patches_json_fp.is_file():
        raise ValueError(
            "--patch_metadata_file arg " f"{patches_json_fp} is not a file"
        )

    if args_output.git_am:
        patch_cmd = patch_utils.git_am
    elif args_output.chromiumos_apply:
        patch_cmd = patch_utils.git_am_chromiumos
    else:
        patch_cmd = patch_utils.gnu_patch

    def _apply_all(args):
        if args.svn_version is None:
            raise ValueError("--svn_version must be set when applying patches")
        result = patch_utils.apply_all_from_json(
            svn_version=args.svn_version,
            llvm_src_dir=llvm_src_dir,
            patches_json_fp=patches_json_fp,
            patch_cmd=patch_cmd,
            continue_on_failure=args.failure_mode
            == failure_modes.FailureModes.CONTINUE,
        )
        PrintPatchResults(result)

    def _disable(args):
        patch_utils.update_version_ranges(
            args.svn_version, llvm_src_dir, patches_json_fp, patch_cmd
        )

    def _test_single(args):
        if not args.test_patch:
            raise ValueError(
                "Running with bisect_patches requires the " "--test_patch flag."
            )
        svn_version = GetHEADSVNVersion(llvm_src_dir)
        error_code = CheckPatchApplies(
            svn_version,
            llvm_src_dir,
            patches_json_fp,
            args.test_patch,
        )
        # Since this is for bisection, we want to exit with the
        # GitBisectionCode enum.
        sys.exit(int(error_code))

    dispatch_table = {
        failure_modes.FailureModes.FAIL: _apply_all,
        failure_modes.FailureModes.CONTINUE: _apply_all,
        failure_modes.FailureModes.DISABLE_PATCHES: _disable,
        failure_modes.FailureModes.BISECT_PATCHES: _test_single,
    }

    if args_output.failure_mode in dispatch_table:
        dispatch_table[args_output.failure_mode](args_output)
