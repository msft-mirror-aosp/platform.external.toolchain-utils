# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Automatically manages LLVM's PGO profiles.

Specifically, this script:
    - generates & uploads new PGO profiles for llvm-next, if necessary
    - ensures that the revisions for said llvm-next profiles are in the
      associated manifest file
    - cleans old llvm profiles from the ebuild

Run this outside of the chroot.
"""

import argparse
import logging
from pathlib import Path
import re
import shlex
import subprocess
import textwrap
from typing import Iterable, List, Optional

from cros_utils import git_utils
from llvm_tools import chroot
from llvm_tools import get_llvm_hash
from llvm_tools import llvm_next
from pgo_tools import pgo_utils


PROFDATA_REV_PREFIX = "gs://chromeos-localmirror/distfiles/llvm-profdata-r"
PROFDATA_REV_SUFFIX = ".xz"

# Path to LLVM's 9999 ebuild from chromiumos-overlay
LLVM_EBUILD_SUBPATH = Path("sys-devel", "llvm", "llvm-9999.ebuild")


class GsProfileCache:
    """Caches which LLVM revisions we have profile information for (in gs://).

    To use this:
        1. Create an instance of this class using `GsProfileCache.fetch()`.
        2. Check if we have profile information for a revision: `123 in cache`.
        3. Inform the cache that we have information for a revision:
           `cache.insert_rev(123)`.
    """

    def __init__(self, profiles: Iterable[int]):
        self.profile_revs = set(profiles)

    def __contains__(self, rev: int) -> bool:
        return rev in self.profile_revs

    def __len__(self) -> int:
        return len(self.profile_revs)

    def insert_rev(self, rev: int) -> None:
        self.profile_revs.add(rev)

    @classmethod
    def fetch(cls) -> "GsProfileCache":
        stdout = subprocess.run(
            [
                "gsutil",
                "ls",
                f"{PROFDATA_REV_PREFIX}*{PROFDATA_REV_SUFFIX}",
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        ).stdout.strip()

        prof_re = re.compile(
            re.escape(PROFDATA_REV_PREFIX)
            + r"(\d+)"
            + re.escape(PROFDATA_REV_SUFFIX)
        )
        profiles = set()
        for line in stdout.splitlines():
            m = prof_re.fullmatch(line)
            if not m:
                if not line.strip():
                    continue
                raise ValueError(f"Unparseable line from gs://: {line!r}")
            profiles.add(int(m.group(1)))
        return cls(profiles)


def parse_args(my_dir: Path, argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chromiumos-tree",
        type=Path,
        help="""
        Path to the root of the ChromeOS tree to edit. Autodetected if not
        specified.
        """,
    )
    parser.add_argument(
        "--clobber-llvm",
        action="store_true",
        help="""
        If a profile needs to be generated and there are uncommitted changes in
        the LLVM source directory, clobber the changes.
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually upload CLs, or generate new benchmark profiles.",
    )
    parser.add_argument(
        "--force-llvm-next-pgo-generation",
        action="store_true",
        help="""
        Skip checks to see if LLVM profiles already exist. If a profile already
        exists in gs://, these will not be uploaded. This primarily exists so
        we can continuously test the PGO profile pipeline.
        """,
    )
    opts = parser.parse_args(argv)

    if not opts.chromiumos_tree:
        opts.chromiumos_tree = chroot.FindChromeOSRootAbove(my_dir)
    return opts


def maybe_upload_new_llvm_next_profile(
    *,
    profile_cache: GsProfileCache,
    dry_run: bool,
    toolchain_utils: Path,
    clobber_llvm: bool,
    force_generation: bool,
) -> None:
    llvm_next_rev = llvm_next.LLVM_NEXT_REV
    upload_profile = True
    if llvm_next_rev in profile_cache:
        if not force_generation:
            logging.info(
                "llvm-next profile already exists in gs://; no need to make a "
                "new one"
            )
            return
        logging.info(
            "llvm-next profile already exists in gs://; forcing generation "
            "without upload."
        )
        upload_profile = False

    create_script = (
        toolchain_utils
        / "py"
        / "bin"
        / "pgo_tools"
        / "create_chroot_and_generate_pgo_profile.py"
    )
    logging.info("Generating a PGO profile for LLVM r%d", llvm_next_rev)
    cmd: pgo_utils.Command = [
        create_script,
        f"--rev={llvm_next_rev}",
    ]
    logging.info(
        "Generating %s a PGO profile for LLVM r%d",
        "and uploading" if upload_profile else "without uploading",
        llvm_next_rev,
    )
    if upload_profile:
        cmd.append("--upload")
    if clobber_llvm:
        cmd.append("--clobber-llvm")

    if dry_run:
        logging.info(
            "Skipping PGO profile generation for llvm r%d due to --dry-run. "
            "Would run: %s",
            llvm_next_rev,
            shlex.join(str(x) for x in cmd),
        )
        profile_cache.insert_rev(llvm_next_rev)
        return

    pgo_utils.run(cmd)

    if upload_profile:
        profile_cache.insert_rev(llvm_next_rev)


def overwrite_llvm_pgo_listing(
    chromiumos_overlay: Path, profile_revs: List[int]
) -> bool:
    ebuild = chromiumos_overlay / LLVM_EBUILD_SUBPATH
    contents = ebuild.read_text(encoding="utf-8")
    new_pgo_listing = "\t" + "\n\t".join(str(x) for x in profile_revs)

    array_start = "\nLLVM_PGO_PROFILE_REVS=(\n"
    array_start_index = contents.index(array_start)
    array_end_index = contents.index("\n)", array_start_index)

    new_contents = (
        contents[: array_start_index + len(array_start)]
        + new_pgo_listing
        + contents[array_end_index:]
    )
    if new_contents == contents:
        return False
    ebuild.write_text(new_contents, encoding="utf-8")
    return True


def update_llvm_ebuild_manifest(
    chromeos_tree: Path, chromiumos_overlay: Path
) -> None:
    overlay_relpath = chromiumos_overlay.relative_to(chromeos_tree)
    overlay_chroot_path = Path("/mnt") / "host" / "source" / overlay_relpath
    llvm_9999 = overlay_chroot_path / LLVM_EBUILD_SUBPATH
    ebuild_manifest_cmd = shlex.join(["ebuild", str(llvm_9999), "manifest"])
    logging.info("Running `%s` in the chroot...", ebuild_manifest_cmd)
    subprocess.run(
        ["cros_sdk", "--", "bash", "-c", ebuild_manifest_cmd],
        check=True,
        cwd=chromeos_tree,
    )


def create_llvm_pgo_ebuild_update(
    chromeos_tree: Path,
    chromiumos_overlay: Path,
    profile_cache: GsProfileCache,
    dry_run: bool,
) -> Optional[str]:
    llvm_dir = get_llvm_hash.GetAndUpdateLLVMProjectInLLVMTools()
    llvm_hash = get_llvm_hash.LLVMHash()
    current_llvm_sha = llvm_hash.GetCrOSCurrentLLVMHash(chromeos_tree)
    current_llvm_rev = get_llvm_hash.GetVersionFrom(llvm_dir, current_llvm_sha)
    logging.info("Current LLVM revision is %d", current_llvm_rev)
    want_revisions = [current_llvm_rev]

    llvm_next_rev = llvm_next.LLVM_NEXT_REV
    if current_llvm_rev != llvm_next_rev:
        logging.info("llvm-next rev is r%d", llvm_next_rev)
        if llvm_next_rev in profile_cache:
            want_revisions.append(llvm_next_rev)
        else:
            logging.info(
                "No PGO profile exists for r%d; skip adding to profile list",
                llvm_next_rev,
            )
    logging.info(
        "Expected LLVM PGO profile version(s) in ebuild: %s", want_revisions
    )

    made_change = overwrite_llvm_pgo_listing(chromiumos_overlay, want_revisions)
    if not made_change:
        logging.info("No LLVM ebuild changes made")
        return None

    # Skip the manifest update in this case, since the profile cache we're
    # using might have had a entry inserted by the profile generation stage of
    # this script.
    if dry_run:
        logging.info("Skipping manifest update; --dry-run was passed")
    else:
        update_llvm_ebuild_manifest(chromeos_tree, chromiumos_overlay)
    return git_utils.commit_all_changes(
        chromiumos_overlay,
        textwrap.dedent(
            """\
            llvm: update PGO profile listing

            This CL was generated by toolchain-utils'
            pgo_tools/auto_update_llvm_pgo_profile.py script.

            BUG=b:337284701
            TEST=CQ
            """
        ),
    )


def main(argv: List[str]) -> None:
    my_dir = Path(__file__).resolve().parent

    pgo_utils.exit_if_in_chroot()

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )
    opts = parse_args(my_dir, argv)

    chromeos_root = opts.chromiumos_tree
    chromiumos_overlay = (
        chromeos_root / "src" / "third_party" / "chromiumos-overlay"
    )
    dry_run = opts.dry_run

    logging.info("Populating gs:// profile cache...")
    profile_cache = GsProfileCache.fetch()
    logging.info("Found %d LLVM PGO profiles in gs://.", len(profile_cache))

    maybe_upload_new_llvm_next_profile(
        profile_cache=profile_cache,
        dry_run=dry_run,
        toolchain_utils=my_dir.parent,
        clobber_llvm=opts.clobber_llvm,
        force_generation=opts.force_llvm_next_pgo_generation,
    )

    # NOTE: `in_dir=chromeos_root` here is critical, since this function needs
    # to enter the chroot to run `ebuild manifest`. Hence, the worktree must be
    # trivially reachable from within the chroot.
    with git_utils.create_worktree(
        chromiumos_overlay, in_dir=chromeos_root
    ) as worktree:
        maybe_sha = create_llvm_pgo_ebuild_update(
            chromeos_root,
            worktree,
            profile_cache,
            dry_run,
        )

    if not maybe_sha:
        logging.info("No changes made to LLVM ebuild; quit.")
        return

    if dry_run:
        logging.info(
            "LLVM ebuild changes committed as %s. --dry-run specified; quit.",
            maybe_sha,
        )
        return

    cls = git_utils.upload_to_gerrit(
        chromiumos_overlay,
        remote=git_utils.CROS_EXTERNAL_REMOTE,
        branch=git_utils.CROS_MAIN_BRANCH,
        ref=maybe_sha,
    )
    for cl in cls:
        git_utils.try_set_autosubmit_labels(chromiumos_overlay, cl)
    logging.info("%d CL(s) uploaded.", len(cls))
