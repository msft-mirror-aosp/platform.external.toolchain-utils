# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script generates a PGO profile for llvm-next.

Do not run it inside of a chroot. It establishes a chroot of its own.
"""

import argparse
import dataclasses
import logging
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import List

from pgo_tools import pgo_utils


SDK_VERSION_CONF_SUBDIR = (
    Path("src")
    / "third_party"
    / "chromiumos-overlay"
    / "chromeos"
    / "binhost"
    / "host"
    / "sdk_version.conf"
)


@dataclasses.dataclass(frozen=True)
class ChrootInfo:
    """Describes a unique chroot, and the SDK version to pin it to."""

    chroot_name: str
    out_dir_name: str
    sdk_version: str


def find_repo_root(base_dir: Path) -> Path:
    """Returns the root of the user's ChromeOS checkout."""
    if (base_dir / ".repo").exists():
        return base_dir

    for parent in base_dir.parents:
        if (parent / ".repo").exists():
            return parent

    raise ValueError(f"No repo found above {base_dir}")


def detect_bootstrap_sdk_version(repo_root: Path) -> str:
    sdk_version_conf = repo_root / SDK_VERSION_CONF_SUBDIR
    bootstrap_version_re = re.compile(
        r'^BOOTSTRAP_FROZEN_VERSION="([^"]+)"$',
        re.MULTILINE,
    )
    results = bootstrap_version_re.findall(
        sdk_version_conf.read_text(encoding="utf-8")
    )
    if len(results) != 1:
        raise ValueError(
            f"Expected exactly one match in {sdk_version_conf} for "
            f"{bootstrap_version_re}; found {len(results)}"
        )
    return results[0]


def create_fresh_chroot(
    repo_root: Path,
    chroot_info: ChrootInfo,
):
    """Creates a chroot. If it already exists, replaces it."""
    pgo_utils.run(
        [
            "cros_sdk",
            "--replace",
            f"--chroot={chroot_info.chroot_name}",
            f"--out-dir={chroot_info.out_dir_name}",
            f"--sdk-version={chroot_info.sdk_version}",
            "--",
            "true",
        ],
        cwd=repo_root,
    )


def generate_pgo_profile(
    repo_root: Path,
    chroot_info: ChrootInfo,
    chroot_output_file: Path,
):
    """Generates a PGO profile to `chroot_output_file`."""
    pgo_utils.run(
        [
            "cros_sdk",
            f"--chroot={chroot_info.chroot_name}",
            f"--out-dir={chroot_info.out_dir_name}",
            f"--sdk-version={chroot_info.sdk_version}",
            "--",
            "/mnt/host/source/src/third_party/toolchain-utils/pgo_tools/"
            "generate_pgo_profile.py",
            f"--output={chroot_output_file}",
        ],
        cwd=repo_root,
    )


def compress_pgo_profile(pgo_profile: Path) -> Path:
    """Compresses a PGO profile for upload to gs://."""
    pgo_utils.run(
        ["xz", "-9", "-k", pgo_profile],
    )
    return Path(str(pgo_profile) + ".xz")


def translate_chroot_path_to_out_of_chroot(
    repo_root: Path, path: Path, info: ChrootInfo
) -> Path:
    """Translates a chroot path into an out-of-chroot path."""
    path_str = str(path)
    assert path_str.startswith("/tmp"), path
    # Remove the leading `/` from the output file so it joins properly.
    return repo_root / info.out_dir_name / str(path)[1:]


def determine_upload_command(
    my_dir: Path, profile_path: Path
) -> pgo_utils.Command:
    """Returns a command that can be used to upload our PGO profile."""
    # TODO(b/333462347): Ideally, this would just use
    # `llvm_next.LLVM_NEXT_HASH` or similar, but that causes import errors.
    # Invoke the script as a subprocess as a workaround.
    llvm_next_hash = subprocess.run(
        [
            my_dir.parent / "llvm_tools" / "get_llvm_hash.py",
            "--llvm_version=llvm-next",
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ).stdout.strip()

    upload_target = (
        "gs://chromeos-localmirror/distfiles/llvm-profdata-"
        f"{llvm_next_hash}.xz"
    )
    return [
        "gsutil.py",
        "cp",
        "-n",
        "-a",
        "public-read",
        profile_path,
        upload_target,
    ]


def main(argv: List[str]):
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    my_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chroot",
        default="llvm-next-pgo-chroot",
        help="""
        Name of the chroot to create. Will be clobbered if it exists already.
        """,
    )
    parser.add_argument(
        "--out-dir",
        default="llvm-next-pgo-chroot_out",
        help="""
        Name of the out/ directory to use. Will be clobbered if it exists
        already.
        """,
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload the profile after creation. Implies --compress.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="""
        Additionally put the uncompressed profile at the this path after
        creation.
        """,
    )
    opts = parser.parse_args(argv)

    pgo_utils.exit_if_in_chroot()

    repo_root = find_repo_root(Path(os.getcwd()))
    logging.info("Repo root is %s", repo_root)

    logging.info("Creating new SDK")
    bootstrap_sdk_version = detect_bootstrap_sdk_version(repo_root)
    logging.info("Detected bootstrap SDK version: %s", bootstrap_sdk_version)
    bootstrap_chroot_info = ChrootInfo(
        opts.chroot, opts.out_dir, bootstrap_sdk_version
    )
    try:
        create_fresh_chroot(repo_root, bootstrap_chroot_info)
        chroot_profile_path = Path("/tmp/llvm-next-pgo-profile.prof")
        generate_pgo_profile(
            repo_root, bootstrap_chroot_info, chroot_profile_path
        )
        profile_path = translate_chroot_path_to_out_of_chroot(
            repo_root, chroot_profile_path, bootstrap_chroot_info
        )
        if opts.output:
            shutil.copyfile(profile_path, opts.output)

        compressed_profile_path = compress_pgo_profile(profile_path)
        upload_command = determine_upload_command(
            my_dir, compressed_profile_path
        )
        if opts.upload:
            pgo_utils.run(upload_command)
        else:
            friendly_upload_command = shlex.join(str(x) for x in upload_command)
            logging.info(
                "To upload the profile, run %r in %r",
                friendly_upload_command,
                repo_root,
            )
    except:
        logging.warning(
            "NOTE: Chroot left at %s and out dir is left at %s. "
            "If you don't plan to rerun this script, delete them.",
            bootstrap_chroot_info.chroot_name,
            bootstrap_chroot_info.out_dir_name,
        )
        raise
    else:
        logging.info(
            "Feel free to delete chroot %s and out dir %s when you're done "
            "with them.",
            bootstrap_chroot_info.chroot_name,
            bootstrap_chroot_info.out_dir_name,
        )


if __name__ == "__main__":
    main(sys.argv[1:])
