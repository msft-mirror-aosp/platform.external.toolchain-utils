#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs benchmarks, given potentially multiple PGO profiles.

**This script is meant to be run from inside of the chroot.**

This script overwrites your chroot's LLVM temporarily, but if it runs to
completion, it will restore you to your previous version of LLVM. Care is taken
so that the same baseline LLVM is used to build all LLVM versions this script
benchmarks.
"""

import argparse
import enum
import logging
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import List, Union

import pgo_tools


# The full path to where `sys-devel/llvm` expects local profiles to be if
# `USE=llvm_pgo_use_local` is specified.
LOCAL_PROFILE_LOCATION = Path(
    "/mnt/host/source/src/third_party/chromiumos-overlay",
    "sys-devel/llvm/files/llvm-local.profdata",
).resolve()


class SpecialProfile(enum.Enum):
    """An enum representing a 'special' (non-Path) profile."""

    REMOTE = enum.auto()
    NONE = enum.auto()

    def __str__(self) -> str:
        if self is self.REMOTE:
            return "@remote"
        if self is self.NONE:
            return "@none"
        raise ValueError(f"Unknown SpecialProfile value: {repr(self)}")


ProfilePath = Union[SpecialProfile, Path]


def parse_profile_path(path: str) -> ProfilePath:
    for p in SpecialProfile:
        if path == str(p):
            return p
    return Path(path).resolve()


def ensure_hyperfine_is_installed():
    if shutil.which("hyperfine"):
        return

    logging.info("Installing hyperfine for benchmarking...")
    pgo_tools.run(
        [
            "cargo",
            "install",
            "hyperfine",
        ]
    )
    assert shutil.which(
        "hyperfine"
    ), "hyperfine was installed, but isn't on PATH?"


def construct_hyperfine_cmd(
    llvm_ebuild: Path,
    profile: ProfilePath,
    llvm_binpkg: Path,
    use_thinlto: bool,
) -> pgo_tools.Command:
    if isinstance(profile, Path):
        if profile != LOCAL_PROFILE_LOCATION:
            shutil.copyfile(profile, LOCAL_PROFILE_LOCATION)
        use_flags = "-llvm_pgo_use -llvm_next_pgo_use llvm_pgo_use_local"
    elif profile is SpecialProfile.NONE:
        use_flags = "-llvm_pgo_use -llvm_next_pgo_use"
    elif profile is SpecialProfile.REMOTE:
        use_flags = "llvm_pgo_use"
    else:
        raise ValueError(f"Unknown profile type: {type(profile)}")

    quickpkg_restore = " ".join(
        shlex.quote(str(x))
        for x in pgo_tools.generate_quickpkg_restoration_command(llvm_binpkg)
    )

    setup_cmd = (
        f"{quickpkg_restore} && "
        f"sudo FEATURES=ccache USE={shlex.quote(use_flags)}"
        # Use buildpkg-exclude so our existing llvm binpackage isn't
        # overwritten.
        "  emerge sys-devel/llvm --buildpkg-exclude=sys-devel/llvm"
    )

    if use_thinlto:
        benchmark_use = "thinlto"
    else:
        benchmark_use = "-thinlto"

    ebuild_llvm = (
        f"sudo USE={shlex.quote(benchmark_use)} "
        f"ebuild {shlex.quote(str(llvm_ebuild))}"
    )
    return [
        "hyperfine",
        "--max-runs=3",
        f"--setup={setup_cmd}",
        f"--prepare={ebuild_llvm} clean prepare",
        "--",
        # At the moment, building LLVM seems to be an OK benchmark. It has some
        # C in it, some C++, and each pass on Cloudtops takes no more than 7
        # minutes.
        f"{ebuild_llvm} compile",
    ]


def validate_profiles(
    parser: argparse.ArgumentParser, profiles: List[ProfilePath]
):
    number_of_path_profiles = 0
    nonexistent_profiles = []
    seen_profile_at_local_profile_location = False
    for profile in profiles:
        if not isinstance(profile, Path):
            continue

        if not profile.exists():
            nonexistent_profiles.append(profile)

        number_of_path_profiles += 1
        if profile == LOCAL_PROFILE_LOCATION:
            seen_profile_at_local_profile_location = True

    if number_of_path_profiles > 1 and seen_profile_at_local_profile_location:
        parser.error(
            f"Cannot use the path {LOCAL_PROFILE_LOCATION} as a profile if "
            "there are other profiles specified by path."
        )

    if nonexistent_profiles:
        nonexistent_profiles.sort()
        parser.error(
            "One or more profiles do not exist: " f"{nonexistent_profiles}"
        )


def main(argv: List[str]):
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
        "--thinlto",
        action="store_true",
        help="If specified, this will benchmark builds with ThinLTO enabled.",
    )
    parser.add_argument(
        "profile",
        nargs="+",
        type=parse_profile_path,
        help=f"""
        The path to a profile to benchmark. There are two special values here:
        '{SpecialProfile.REMOTE}' and '{SpecialProfile.NONE}'. For
        '{SpecialProfile.REMOTE}', this will just use the default LLVM PGO
        profile for a benchmark run. For '{SpecialProfile.NONE}', all PGO will
        be disabled for a benchmark run.
        """,
    )
    opts = parser.parse_args(argv)

    pgo_tools.exit_if_not_in_chroot()

    profiles = opts.profile
    validate_profiles(parser, profiles)

    ensure_hyperfine_is_installed()
    llvm_ebuild_path = Path(
        pgo_tools.run(
            ["equery", "w", "sys-devel/llvm"], stdout=subprocess.PIPE
        ).stdout.strip()
    )
    baseline_llvm_binpkg = pgo_tools.quickpkg_llvm()
    for profile in profiles:
        cmd = construct_hyperfine_cmd(
            llvm_ebuild_path,
            profile,
            baseline_llvm_binpkg,
            use_thinlto=opts.thinlto,
        )
        # Format the profile with `repr(str(profile))` so that we always get a
        # quoted, but human-friendly, representation of the profile.
        logging.info(
            "Profile %r: Running %s",
            str(profile),
            " ".join(shlex.quote(str(x)) for x in cmd),
        )
        pgo_tools.run(cmd)

    logging.info("Restoring original LLVM...")
    pgo_tools.run(
        pgo_tools.generate_quickpkg_restoration_command(baseline_llvm_binpkg)
    )


if __name__ == "__main__":
    main(sys.argv[1:])
