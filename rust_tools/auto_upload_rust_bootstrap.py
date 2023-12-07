#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Automatically maintains the rust-bootstrap package.

This script is responsible for:
    - uploading new rust-bootstrap prebuilts
    - adding new versions of rust-bootstrap to keep up with dev-lang/rust

It's capable of (and intended to primarily be used for) uploading CLs to do
these things on its own, so it can easily be regularly run by Chrotomation.
"""

import argparse
import dataclasses
import functools
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
from typing import Dict, List, Optional, Tuple, Union

import copy_rust_bootstrap


DEFAULT_CL_REVIEWERS = (
    "gbiv@chromium.org",
    "inglorion@chromium.org",
)


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class EbuildVersion:
    """Represents an ebuild version, simplified for rust-bootstrap versions.

    "Simplified," means that no `_pre`/etc suffixes have to be accounted for.
    """

    major: int
    minor: int
    patch: int
    rev: int

    def major_minor_only(self) -> "EbuildVersion":
        """Returns an EbuildVersion with just the major/minor from this one."""
        if not self.rev and not self.patch:
            return self
        return EbuildVersion(
            major=self.major,
            minor=self.minor,
            patch=0,
            rev=0,
        )

    def without_rev(self) -> "EbuildVersion":
        if not self.rev:
            return self
        return dataclasses.replace(self, rev=0)

    def __str__(self):
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.rev:
            result += f"-r{self.rev}"
        return result


def find_raw_bootstrap_sequence_lines(
    ebuild_lines: List[str],
) -> Tuple[int, int]:
    """Returns the start/end lines of RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE."""
    for i, line in enumerate(ebuild_lines):
        if line.startswith("RUSTC_RAW_FULL_BOOTSTRAP_SEQUENCE=("):
            start = i
            break
    else:
        raise ValueError("No bootstrap sequence start found in text")

    for i, line in enumerate(ebuild_lines[i + 1 :], i + 1):
        if line.rstrip() == ")":
            return start, i
    raise ValueError("No bootstrap sequence end found in text")


def read_bootstrap_sequence_from_ebuild(
    rust_bootstrap_ebuild: Path,
) -> List[EbuildVersion]:
    """Returns a list of EbuildVersions from the given ebuild."""
    ebuild_lines = rust_bootstrap_ebuild.read_text(
        encoding="utf-8"
    ).splitlines()
    start, end = find_raw_bootstrap_sequence_lines(ebuild_lines)
    results = []
    for line in ebuild_lines[start + 1 : end]:
        # Ignore comments.
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        assert len(line.split()) == 1, f"Unexpected line: {line!r}"
        results.append(parse_raw_ebuild_version(line.strip()))
    return results


def version_listed_in_bootstrap_sequence(
    ebuild: Path, rust_bootstrap_version: EbuildVersion
) -> bool:
    ebuild_lines = ebuild.read_text(encoding="utf-8").splitlines()
    start, end = find_raw_bootstrap_sequence_lines(ebuild_lines)
    str_version = str(rust_bootstrap_version.without_rev())
    return any(
        line.strip() == str_version for line in ebuild_lines[start + 1 : end]
    )


@functools.lru_cache(1)
def fetch_most_recent_sdk_version() -> str:
    """Fetches the most recent official SDK version from gs://."""
    latest_file_loc = "gs://chromiumos-sdk/cros-sdk-latest.conf"
    sdk_latest_file = subprocess.run(
        ["gsutil", "cat", latest_file_loc],
        check=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    ).stdout.strip()

    latest_sdk_re = re.compile(r'^LATEST_SDK="([0-9\.]+)"$')
    for line in sdk_latest_file.splitlines():
        m = latest_sdk_re.match(line)
        if m:
            latest_version = m.group(1)
            logging.info("Detected latest SDK version: %r", latest_version)
            return latest_version
    raise ValueError(f"Could not find LATEST_SDK in {latest_file_loc}")


def find_rust_bootstrap_prebuilt(version: EbuildVersion) -> Optional[str]:
    """Returns a URL to a prebuilt for `version` of rust-bootstrap."""
    # Searching chroot-* is generally unsafe, because some uploads might
    # include SDK artifacts built by CQ+1 runs, so just use the most recent
    # verified SDK version.
    sdk_version = fetch_most_recent_sdk_version()

    # Search for all rust-bootstrap versions rather than specifically
    # `version`, since gsutil will exit(1) if no matches are found. exit(1) is
    # desirable if _no rust boostrap artifacts at all exist_, but substantially
    # less so if this function seeks to just `return False`.
    gs_glob = (
        f"gs://chromeos-prebuilt/board/amd64-host/chroot-{sdk_version}"
        "/packages/dev-lang/rust-bootstrap-*tbz2"
    )

    logging.info("Searching %s for rust-bootstrap version %s", gs_glob, version)
    results = subprocess.run(
        ["gsutil", "ls", gs_glob],
        check=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    ).stdout.strip()

    binpkg_name_re = re.compile(
        r"rust-bootstrap-" + re.escape(str(version)) + r"\.tbz2$"
    )
    result_lines = results.splitlines()
    for line in result_lines:
        result = line.strip()
        if binpkg_name_re.search(result):
            logging.info("Found rust-bootstrap prebuilt: %s", result)
            return result
        logging.info("Skipped rust-bootstrap prebuilt: %s", result)

    logging.info(
        "No rust-bootstrap for %s found (regex: %s); options: %s",
        version,
        binpkg_name_re,
        result_lines,
    )
    return None


def parse_raw_ebuild_version(raw_ebuild_version: str) -> EbuildVersion:
    """Parses an ebuild version without the ${PN} prefix or .ebuild suffix.

    >>> parse_raw_ebuild_version("1.70.0-r2")
    EbuildVersion(major=1, minor=70, patch=0, rev=2)
    """
    version_re = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-r(\d+))?")
    m = version_re.match(raw_ebuild_version)
    if not m:
        raise ValueError(f"Version {raw_ebuild_version} can't be recognized.")

    major, minor, patch, rev_str = m.groups()
    rev = 0 if not rev_str else int(rev_str)
    return EbuildVersion(
        major=int(major), minor=int(minor), patch=int(patch), rev=rev
    )


def parse_ebuild_version(ebuild_name: str) -> EbuildVersion:
    """Parses the version from an ebuild.

    Raises:
        ValueError if the `ebuild_name` doesn't contain a parseable version.
        Notably, version suffixes like `_pre`, `_beta`, etc are unexpected in
        Rust-y ebuilds, so they're not handled here.

    >>> parse_ebuild_version("rust-bootstrap-1.70.0-r2.ebuild")
    EbuildVersion(major=1, minor=70, patch=0, rev=2)
    """
    version_re = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-r(\d+))?\.ebuild$")
    m = version_re.search(ebuild_name)
    if not m:
        raise ValueError(f"Ebuild {ebuild_name} has no obvious version")

    major, minor, patch, rev_str = m.groups()
    rev = 0 if not rev_str else int(rev_str)
    return EbuildVersion(
        major=int(major), minor=int(minor), patch=int(patch), rev=rev
    )


def collect_ebuilds_by_version(
    ebuild_dir: Path,
) -> List[Tuple[EbuildVersion, Path]]:
    """Returns the latest ebuilds grouped by version.without_rev.

    Result is always sorted by version, latest versions are last.
    """
    ebuilds = ebuild_dir.glob("*.ebuild")
    versioned_ebuilds: Dict[EbuildVersion, Tuple[EbuildVersion, Path]] = {}
    for ebuild in ebuilds:
        version = parse_ebuild_version(ebuild.name)
        version_no_rev = version.without_rev()
        other = versioned_ebuilds.get(version_no_rev)
        this_is_newer = other is None or other[0] < version
        if this_is_newer:
            versioned_ebuilds[version_no_rev] = (version, ebuild)

    return sorted(versioned_ebuilds.values())


def maybe_copy_prebuilt_to_localmirror(
    copy_rust_bootstrap_script: Path, prebuilt_gs_path: str, dry_run: bool
) -> bool:
    upload_to = copy_rust_bootstrap.determine_target_path(prebuilt_gs_path)
    result = subprocess.run(
        ["gsutil", "ls", upload_to],
        check=True,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if not result.returncode:
        logging.info("Artifact at %s already exists", upload_to)
        return False

    cmd: List[Union[Path, str]] = [
        copy_rust_bootstrap_script,
        prebuilt_gs_path,
    ]

    if dry_run:
        cmd.append("--dry-run")

    subprocess.run(
        cmd,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    return True


def add_version_to_bootstrap_sequence(
    ebuild: Path, version: EbuildVersion, dry_run: bool
):
    ebuild_lines = ebuild.read_text(encoding="utf-8").splitlines(keepends=True)
    _, end = find_raw_bootstrap_sequence_lines(ebuild_lines)
    # `end` is the final paren. Since we _need_ prebuilts for all preceding
    # versions, always put this a line before the end.
    ebuild_lines.insert(end, f"\t{version}\n")
    if not dry_run:
        ebuild.write_text("".join(ebuild_lines), encoding="utf-8")


def is_ebuild_linked_to_in_dir(root_ebuild_path: Path) -> bool:
    """Returns whether symlinks point to `root_ebuild_path`.

    The only directory checked is the directory that contains
    `root_ebuild_path`.
    """
    assert (
        root_ebuild_path.is_absolute()
    ), f"{root_ebuild_path} should be an absolute path."
    in_dir = root_ebuild_path.parent
    for ebuild in in_dir.glob("*.ebuild"):
        if ebuild == root_ebuild_path or not ebuild.is_symlink():
            continue

        points_to = Path(os.path.normpath(in_dir / os.readlink(ebuild)))
        if points_to == root_ebuild_path:
            return True
    return False


def uprev_ebuild(ebuild: Path, version: EbuildVersion, dry_run: bool) -> Path:
    assert ebuild.is_absolute(), f"{ebuild} should be an absolute path."

    new_version = dataclasses.replace(version, rev=version.rev + 1)
    new_ebuild = ebuild.parent / f"rust-bootstrap-{new_version}.ebuild"
    if dry_run:
        logging.info(
            "Skipping rename of %s -> %s; dry-run specified", ebuild, new_ebuild
        )
        return new_ebuild

    # This condition tries to follow CrOS best practices. Namely:
    # - If the ebuild is a symlink, move it.
    # - Otherwise, if the ebuild is a normal file, symlink to it as long as
    #   it has no revision.
    #
    # Since rust-bootstrap's functionality relies heavily on `${PV}`, it's
    # completely expected for cross-${PV} symlinks to exist.
    uprev_via_rename = (
        version.rev != 0 or ebuild.is_symlink()
    ) and not is_ebuild_linked_to_in_dir(ebuild)

    if uprev_via_rename:
        logging.info("Moving %s -> %s", ebuild, new_ebuild)
        ebuild.rename(new_ebuild)
    else:
        logging.info("Symlinking %s to %s", new_ebuild, ebuild)
        new_ebuild.symlink_to(ebuild.relative_to(ebuild.parent))
    return new_ebuild


def update_ebuild_manifest(rust_bootstrap_ebuild: Path):
    subprocess.run(
        ["ebuild", rust_bootstrap_ebuild, "manifest"],
        check=True,
        stdin=subprocess.DEVNULL,
    )


def commit_all_changes(
    git_dir: Path, rust_bootstrap_dir: Path, commit_message: str
):
    subprocess.run(
        ["git", "add", rust_bootstrap_dir.relative_to(git_dir)],
        cwd=git_dir,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "config", "core.hooksPath"],
        cwd=git_dir,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "commit", "-m", commit_message],
        cwd=git_dir,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def scrape_git_push_cl_id(git_push_output: str) -> int:
    id_regex = re.compile(
        r"^remote:\s+https://chromium-review\S+/\+/(\d+)\s", re.MULTILINE
    )
    results = id_regex.findall(git_push_output)
    if len(results) != 1:
        raise ValueError(
            f"Found {len(results)} matches of {id_regex} in"
            f"{git_push_output!r}; expected 1"
        )
    return int(results[0])


def upload_changes(git_dir: Path):
    logging.info("Uploading changes")
    result = subprocess.run(
        ["git", "push", "cros", "HEAD:refs/for/main"],
        check=True,
        cwd=git_dir,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # Print this in case anyone's looking at the output.
    print(result.stdout, end=None)
    result.check_returncode()

    cl_id = str(scrape_git_push_cl_id(result.stdout))
    logging.info("Uploaded crrev.com/c/%s successfully!", cl_id)
    gerrit_commands = (
        ["gerrit", "label-v", cl_id, "1"],
        ["gerrit", "label-cq", cl_id, "1"],
        ["gerrit", "label-as", cl_id, "1"],
        ["gerrit", "reviewers", cl_id] + list(DEFAULT_CL_REVIEWERS),
        ["gerrit", "ready", cl_id],
    )
    for command in gerrit_commands:
        logging.info("Running gerrit command: %s", command)
        subprocess.run(
            command,
            check=True,
            stdin=subprocess.DEVNULL,
        )


def maybe_add_newest_prebuilts(
    copy_rust_bootstrap_script: Path,
    chromiumos_overlay: Path,
    rust_bootstrap_dir: Path,
    dry_run: bool,
) -> bool:
    """Ensures that prebuilts in rust-bootstrap ebuilds are up-to-date.

    If dry_run is True, no changes will be made on disk. Otherwise, changes
    will be committed to git locally.

    Returns:
        True if changes were made (or would've been made, in the case of
        dry_run being True). False otherwise.
    """
    # A list of (version, maybe_prebuilt_location).
    versions_updated: List[Tuple[EbuildVersion, Optional[str]]] = []
    for version, ebuild in collect_ebuilds_by_version(rust_bootstrap_dir):
        logging.info("Inspecting %s...", ebuild)
        if version.without_rev() in read_bootstrap_sequence_from_ebuild(ebuild):
            logging.info("Prebuilt already exists for %s.", ebuild)
            continue

        logging.info("Prebuilt isn't in ebuild; checking remotely.")
        prebuilt = find_rust_bootstrap_prebuilt(version)
        if not prebuilt:
            # `find_rust_bootstrap_prebuilt` handles logging in this case.
            continue

        # Houston, we have prebuilt.
        uploaded = maybe_copy_prebuilt_to_localmirror(
            copy_rust_bootstrap_script, prebuilt, dry_run
        )
        add_version_to_bootstrap_sequence(ebuild, version, dry_run)
        uprevved_ebuild = uprev_ebuild(ebuild, version, dry_run)
        versions_updated.append((version, prebuilt if uploaded else None))

    if not versions_updated:
        logging.info("No updates made; exiting cleanly.")
        return False

    if dry_run:
        logging.info("Dry-run specified; quit.")
        return True

    # Just pick an arbitrary ebuild to run `ebuild ... manifest` on; it always
    # updates for all ebuilds in the same package.
    update_ebuild_manifest(uprevved_ebuild)

    pretty_artifact_lines = []
    for version, maybe_gs_path in versions_updated:
        if maybe_gs_path:
            pretty_artifact_lines.append(
                f"- rust-bootstrap-{version.without_rev()} => {maybe_gs_path}"
            )
        else:
            pretty_artifact_lines.append(
                f"- rust-bootstrap-{version.without_rev()} was already on "
                "localmirror"
            )

    pretty_artifacts = "\n".join(pretty_artifact_lines)

    logging.info("Committing changes.")
    commit_all_changes(
        chromiumos_overlay,
        rust_bootstrap_dir,
        commit_message=textwrap.dedent(
            f"""\
            rust-bootstrap: use prebuilts

            This CL used the following rust-bootstrap artifacts:
            {pretty_artifacts}

            BUG=None
            TEST=CQ
            """
        ),
    )
    return True


class MissingRustBootstrapPrebuiltError(Exception):
    """Raised when rust-bootstrap can't be landed due to a missing prebuilt."""


def maybe_add_new_rust_bootstrap_version(
    chromiumos_overlay: Path,
    rust_bootstrap_dir: Path,
    dry_run: bool,
    commit: bool = True,
) -> bool:
    """Ensures that there's a rust-bootstrap-${N} ebuild matching rust-${N}.

    Args:
        chromiumos_overlay: Path to chromiumos-overlay.
        rust_bootstrap_dir: Path to rust-bootstrap's directory.
        dry_run: if True, don't commit to git or write changes to disk.
            Otherwise, write changes to disk.
        commit: if True, commit changes to git. This value is meaningless if
            `dry_run` is True.

    Returns:
        True if changes were made (or would've been made, in the case of
        dry_run being True). False otherwise.

    Raises:
        MissingRustBootstrapPrebuiltError if the creation of a new
        rust-bootstrap ebuild wouldn't be buildable, since there's no
        rust-bootstrap prebuilt of the prior version for it to sync.
    """
    # These are always returned in sorted error, so taking the last is the same
    # as `max()`.
    (
        newest_bootstrap_version,
        newest_bootstrap_ebuild,
    ) = collect_ebuilds_by_version(rust_bootstrap_dir)[-1]

    logging.info(
        "Detected newest rust-bootstrap version: %s", newest_bootstrap_version
    )

    rust_dir = rust_bootstrap_dir.parent / "rust"
    newest_rust_version, _ = collect_ebuilds_by_version(rust_dir)[-1]
    logging.info("Detected newest rust version: %s", newest_rust_version)

    # Generally speaking, we don't care about keeping up with new patch
    # releases for rust-bootstrap. It's OK to _initially land_ e.g.,
    # rust-bootstrap-1.73.1, but upgrades from rust-bootstrap-1.73.0 to
    # rust-bootstrap-1.73.1 are rare, and have added complexity, so should be
    # done manually. Hence, only check for major/minor version inequality.
    if (
        newest_rust_version.major_minor_only()
        <= newest_bootstrap_version.major_minor_only()
    ):
        logging.info("No missing rust-bootstrap versions detected.")
        return False

    available_prebuilts = read_bootstrap_sequence_from_ebuild(
        newest_bootstrap_ebuild
    )
    need_prebuilt = dataclasses.replace(
        newest_rust_version.major_minor_only(),
        minor=newest_rust_version.minor - 1,
    )

    if all(x.major_minor_only() != need_prebuilt for x in available_prebuilts):
        raise MissingRustBootstrapPrebuiltError(
            f"want version {need_prebuilt}; "
            f"available versions: {available_prebuilts}"
        )

    # Ensure the rust-bootstrap ebuild we're landing is a regular file. This
    # makes cleanup of the old files trivial, since they're dead symlinks.
    prior_ebuild_resolved = newest_bootstrap_ebuild.resolve()
    new_ebuild = (
        rust_bootstrap_dir
        / f"rust-bootstrap-{newest_rust_version.without_rev()}.ebuild"
    )
    if dry_run:
        logging.info("Would move %s to %s.", prior_ebuild_resolved, new_ebuild)
        return True

    logging.info(
        "Moving %s to %s, and creating symlink at the old location",
        prior_ebuild_resolved,
        new_ebuild,
    )
    prior_ebuild_resolved.rename(new_ebuild)
    prior_ebuild_resolved.symlink_to(new_ebuild.relative_to(rust_bootstrap_dir))

    update_ebuild_manifest(new_ebuild)
    if commit:
        commit_all_changes(
            chromiumos_overlay,
            rust_bootstrap_dir,
            commit_message=textwrap.dedent(
                f"""\
                rust-bootstrap: add version {newest_rust_version}

                Rust is now at {newest_rust_version.without_rev()}; add a
                rust-bootstrap version so prebuilts can be generated early.

                BUG=None
                TEST=CQ
                """
            ),
        )
    return True


def main(argv: List[str]):
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.INFO,
    )

    my_dir = Path(__name__).parent.resolve()
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chromiumos-overlay",
        type=Path,
        default=my_dir.parent.parent / "chromiumos-overlay",
    )
    parser.add_argument(
        "action",
        choices=("dry-run", "commit", "upload"),
        help="""
        What to do. `dry-run` makes no changes, `commit` commits changes
        locally, and `upload` commits changes and uploads the result to Gerrit,
        and sets a few labels for convenience (reviewers, CQ+1, etc).
        """,
    )
    opts = parser.parse_args(argv)

    if opts.action == "dry-run":
        dry_run = True
        upload = False
    elif opts.action == "commit":
        dry_run = False
        upload = False
    else:
        assert opts.action == "upload"
        dry_run = False
        upload = True

    rust_bootstrap_dir = opts.chromiumos_overlay / "dev-lang/rust-bootstrap"
    copy_rust_bootstrap_script = my_dir / "copy_rust_bootstrap.py"

    had_recoverable_error = False
    # Ensure prebuilts are up to date first, since it allows
    # `ensure_newest_rust_bootstrap_ebuild_exists` to succeed in edge cases.
    made_changes = maybe_add_newest_prebuilts(
        copy_rust_bootstrap_script,
        opts.chromiumos_overlay,
        rust_bootstrap_dir,
        dry_run,
    )
    try:
        made_changes |= maybe_add_new_rust_bootstrap_version(
            opts.chromiumos_overlay, rust_bootstrap_dir, dry_run
        )
    except MissingRustBootstrapPrebuiltError:
        logging.exception(
            "Ensuring newest rust-bootstrap ebuild exists failed."
        )
        had_recoverable_error = True

    if upload:
        if made_changes:
            upload_changes(opts.chromiumos_overlay)
            logging.info("Changes uploaded successfully.")
        else:
            logging.info("No changes were made; uploading skipped.")

    if had_recoverable_error:
        sys.exit("Exiting uncleanly due to above error(s).")


if __name__ == "__main__":
    main(sys.argv[1:])
