#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script updates kernel profiles based on what's available in gs://.

It supports updating on canary, stable, and beta branches.
"""

import argparse
import contextlib
import dataclasses
import datetime
import enum
import json
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Dict, Generator, Iterable, List, Optional, Tuple


# Folks who should be on the R-line of any CLs that get uploaded.
# Note that `c-compiler-chrome@` is managed by gwsq - it'll replace
# `R=c-compiler-chrome` with the current detective.
CL_REVIEWERS = ("c-compiler-chrome@google.com",)

# Folks who should be on the CC-line of any CLs that get uploaded.
CL_CC = (
    "denik@google.com",
    "gbiv@google.com",
)


class Arch(enum.Enum):
    """An enum for CPU architectures."""

    AMD64 = "amd64"
    ARM = "arm"

    @property
    def cwp_gs_location(self) -> str:
        """Returns the location in gs:// where these profiles live."""
        if self == self.AMD64:
            return "gs://chromeos-prebuilt/afdo-job/vetted/kernel/amd64"
        if self == self.ARM:
            return "gs://chromeos-prebuilt/afdo-job/vetted/kernel/arm"
        assert False, f"Uncovered arch -> gs:// mapping for {self}"


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class KernelVersion:
    """A class representing a version of the kernel."""

    major: int
    minor: int

    def __str__(self):
        return f"{self.major}.{self.minor}"

    @classmethod
    def parse(cls, val: str) -> "KernelVersion":
        m = re.fullmatch(r"(\d+).(\d+)", val)
        if not m:
            raise ValueError(f"{val!r} is an invalid kernel version")
        return cls(major=int(m.group(1)), minor=int(m.group(2)))


# Versions that rolling should be skipped on, for one reason or another.
SKIPPED_VERSIONS: Dict[int, Iterable[Tuple[Arch, KernelVersion]]] = {
    # Kernel tracing was disabled on ARM in 114, b/275560674
    114: ((Arch.ARM, KernelVersion(5, 15)),),
    115: ((Arch.ARM, KernelVersion(5, 15)),),
}


class Channel(enum.Enum):
    """An enum that discusses channels."""

    # Ordered from closest-to-ToT to farthest-from-ToT
    CANARY = "canary"
    BETA = "beta"
    STABLE = "stable"

    @classmethod
    def parse(cls, val: str) -> "Channel":
        for x in cls:
            if val == x.value:
                return x
        raise ValueError(
            f"No such channel: {val!r}; try one of {[x.value for x in cls]}"
        )


@dataclasses.dataclass(frozen=True)
class ProfileSelectionInfo:
    """Preferences about profiles to select."""

    # A consistent timestamp for the program to run with.
    now: datetime.datetime

    # Maximum age of a profile that can be selected.
    max_profile_age: datetime.timedelta


def get_parser():
    """Returns an argument parser for this script."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Automatically upload all changes that were made.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Run `git fetch` in toolchain-utils prior to running.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=10,
        help="""
        The maximum number of days old a kernel profile can be before
        it's ignored by this script. Default: %(default)s
        """,
    )
    parser.add_argument(
        "channel",
        nargs="*",
        type=Channel.parse,
        default=list(Channel),
        help=f"""
        Channel(s) to update. If none are passed, this will update all
        channels. Choose from {[x.value for x in Channel]}.
        """,
    )
    return parser


@contextlib.contextmanager
def git_worktree(git_directory: Path) -> Generator[Path, None, None]:
    """Creates a temp worktree of `git_directory`, yielding the result."""
    with tempfile.TemporaryDirectory(prefix="update_kernel_afdo_") as t:
        tempdir = Path(t)
        logging.info(
            "Establishing worktree of %s in %s", git_directory, tempdir
        )
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                "--force",
                tempdir,
            ],
            cwd=git_directory,
            check=True,
            stdin=subprocess.DEVNULL,
        )

        try:
            yield tempdir
        finally:
            # Explicitly `git worktree remove` here, so the parent worktree's
            # metadata is cleaned up promptly.
            subprocess.run(
                [
                    "git",
                    "worktree",
                    "remove",
                    "--force",
                    tempdir,
                ],
                cwd=git_directory,
                check=False,
                stdin=subprocess.DEVNULL,
            )


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class GitBranch:
    """Represents a ChromeOS branch."""

    remote: str
    release_number: int
    branch_name: str


def git_checkout(git_dir: Path, branch: GitBranch) -> None:
    subprocess.run(
        [
            "git",
            "checkout",
            "--quiet",
            f"{branch.remote}/{branch.branch_name}",
        ],
        check=True,
        cwd=git_dir,
        stdin=subprocess.DEVNULL,
    )


def git_fetch(git_dir: Path) -> None:
    subprocess.run(
        ["git", "fetch"],
        check=True,
        cwd=git_dir,
        stdin=subprocess.DEVNULL,
    )


def git_rev_parse(git_dir: Path, ref_or_sha: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref_or_sha],
        check=True,
        cwd=git_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ).stdout.strip()


def autodetect_branches(toolchain_utils: Path) -> Dict[Channel, GitBranch]:
    """Returns GitBranches for each branch type in toolchain_utils."""
    stdout = subprocess.run(
        [
            "git",
            "branch",
            "-r",
        ],
        cwd=toolchain_utils,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    ).stdout

    # Match "${remote}/release-R${branch_number}-${build}.B"
    branch_re = re.compile(r"([^/]+)/(release-R(\d+)-\d+\.B)")
    branches = []
    for line in stdout.splitlines():
        line = line.strip()
        if m := branch_re.fullmatch(line):
            remote, branch_name, branch_number = m.groups()
            branches.append(GitBranch(remote, int(branch_number), branch_name))

    branches.sort(key=lambda x: x.release_number)
    if len(branches) < 2:
        raise ValueError(
            f"Expected at least two branches, but only found {len(branches)}"
        )

    stable = branches[-2]
    beta = branches[-1]
    canary = GitBranch(
        remote=beta.remote,
        release_number=beta.release_number + 1,
        branch_name="main",
    )
    return {
        Channel.CANARY: canary,
        Channel.BETA: beta,
        Channel.STABLE: stable,
    }


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class ArchUpdateConfig:
    """The AFDO update config for one architecture."""

    versions_to_track: List[KernelVersion]
    metadata_file: Path


def read_update_cfg_file(
    toolchain_utils: Path, file_path: Path
) -> Dict[Arch, ArchUpdateConfig]:
    """Reads `update_kernel_afdo.cfg`."""
    # These files were originally meant to be `source`d in bash, and are very
    # simple. These are read from branches, so we'd need cherry-picks to go
    # back and replace them with a singular format. Could be nice to move to
    # JSON or something.

    # Parse assignments that look like `FOO="bar"`. No escaping or variable
    # expansion is supported.
    kv_re = re.compile(r'^([a-zA-Z_0-9]+)="([^"]*)"(?:\s*#.*)?', re.MULTILINE)
    kvs = kv_re.findall(file_path.read_text(encoding="utf-8"))
    # Subtle: the regex above makes it so `kv_re.findall` returns a series of
    # (variable_name, variable_value).
    settings = dict(kvs)

    logging.debug("Parsing cfg file gave back settings: %s", settings)
    archs = (
        (Arch.AMD64, "AMD"),
        (Arch.ARM, "ARM"),
    )

    results = {}
    for arch, arch_var_name in archs:
        # This is a space-separated list of kernel versions.
        kernel_versions = settings[f"{arch_var_name}_KVERS"]
        parsed_versions = [
            KernelVersion.parse(x) for x in kernel_versions.split()
        ]

        metadata_file = settings[f"{arch_var_name}_METADATA_FILE"]
        results[arch] = ArchUpdateConfig(
            versions_to_track=parsed_versions,
            metadata_file=toolchain_utils / metadata_file,
        )
    return results


@dataclasses.dataclass(frozen=True, eq=True)
class KernelGsProfile:
    """Represents a kernel profile in gs://."""

    release_number: int
    chrome_build: str
    cwp_timestamp: int
    suffix: str
    gs_timestamp: datetime.datetime

    _FILE_NAME_PARSE_RE = re.compile(r"R(\d+)-(\d+\.\d+)-(\d+)(\..+\..+)")

    @property
    def file_name_no_suffix(self):
        return (
            f"R{self.release_number}-{self.chrome_build}-{self.cwp_timestamp}"
        )

    @property
    def file_name(self):
        return f"{self.file_name_no_suffix}{self.suffix}"

    @classmethod
    def from_file_name(
        cls, timestamp: datetime.datetime, file_name: str
    ) -> "KernelGsProfile":
        m = cls._FILE_NAME_PARSE_RE.fullmatch(file_name)
        if not m:
            raise ValueError(f"{file_name!r} doesn't parse as a profile name")
        release_number, chrome_build, cwp_timestamp, suffix = m.groups()
        return cls(
            release_number=int(release_number),
            chrome_build=chrome_build,
            cwp_timestamp=int(cwp_timestamp),
            suffix=suffix,
            gs_timestamp=timestamp,
        )


def datetime_from_gs_time(timestamp_str: str) -> datetime.datetime:
    """Parses a datetime from gs."""
    return datetime.datetime.strptime(
        timestamp_str, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=datetime.timezone.utc)


class KernelProfileFetcher:
    """Fetches kernel profiles from gs://. Caches results."""

    def __init__(self):
        self._cached_results: Dict[str, List[KernelGsProfile]] = {}

    @staticmethod
    def _parse_gs_stdout(stdout: str) -> List[KernelGsProfile]:
        line_re = re.compile(r"\s*\d+\s+(\S+T\S+)\s+(gs://.+)")
        results = []
        # Ignore the last line, since that's "TOTAL:"
        for line in stdout.splitlines()[:-1]:
            line = line.strip()
            if not line:
                continue
            m = line_re.fullmatch(line)
            if m is None:
                raise ValueError(f"Unexpected line from gs: {line!r}")
            timestamp_str, gs_url = m.groups()
            timestamp = datetime_from_gs_time(timestamp_str)
            file_name = os.path.basename(gs_url)
            results.append(KernelGsProfile.from_file_name(timestamp, file_name))
        return results

    @classmethod
    def _fetch_impl(cls, gs_url: str) -> List[KernelGsProfile]:
        result = subprocess.run(
            [
                "gsutil",
                "ls",
                "-l",
                gs_url,
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        if result.returncode:
            # If nothing could be found, gsutil will exit after printing this.
            if "One or more URLs matched no objects." in result.stderr:
                return []
            logging.error(
                "gsutil ls %s failed; stderr:\n%s", gs_url, result.stderr
            )
            result.check_returncode()
            assert False, "unreachable"

        return cls._parse_gs_stdout(result.stdout)

    def fetch(self, gs_url: str) -> List[KernelGsProfile]:
        cached = self._cached_results.get(gs_url)
        if cached is None:
            logging.info("Fetching profiles from %s...", gs_url)
            fetched = self._fetch_impl(gs_url)
            logging.info("Found %d profiles in %s", len(fetched), gs_url)
            self._cached_results[gs_url] = fetched
            cached = fetched

        # Create a copy to keep mutations from causing problems.
        # KernelGsProfiles are frozen, at least.
        return cached[:]


def find_newest_afdo_artifact(
    fetcher: KernelProfileFetcher,
    arch: Arch,
    kernel_version: KernelVersion,
    release_number: int,
) -> Optional[KernelGsProfile]:
    """Returns info about the latest AFDO artifact for the given parameters."""
    gs_base_location = arch.cwp_gs_location
    kernel_profile_dir = os.path.join(gs_base_location, str(kernel_version))
    kernel_profiles = fetcher.fetch(kernel_profile_dir)
    if not kernel_profiles:
        logging.error(
            "Failed to find any kernel profiles in %s", kernel_profile_dir
        )
        return None

    valid_profiles = [
        x for x in kernel_profiles if x.release_number == release_number
    ]
    if not valid_profiles:
        logging.error(
            "Failed to find any M%d kernel profiles in %s",
            release_number,
            kernel_profile_dir,
        )
        return None

    # We want the most recently uploaded profile, since that should correspond
    # with the newest profile. If there're multiple profiles for some reason,
    # choose what _should_ be a consistent tie-breaker.
    return max(
        valid_profiles,
        key=lambda x: (x.gs_timestamp, x.cwp_timestamp, x.chrome_build),
    )


def read_afdo_descriptor_file(path: Path) -> Dict[KernelVersion, str]:
    """Reads the AFDO descriptor file.

    "AFDO descriptor file" is jargon to refer to the actual JSON file that PUpr
    monitors.
    """
    try:
        with path.open(encoding="utf-8") as f:
            raw_contents = json.load(f)
    except FileNotFoundError:
        return {}

    # The format of this is:
    # {
    #   "chromeos-kernel-${major}_${minor}": {
    #     "name": "${profile_gs_name}",
    #   }
    # }
    key_re = re.compile(r"^chromeos-kernel-(\d)+_(\d+)$")
    result = {}
    for kernel_key, val in raw_contents.items():
        m = key_re.fullmatch(kernel_key)
        if not m:
            raise ValueError(f"Invalid key in JSON: {kernel_key}")
        major, minor = m.groups()
        version = KernelVersion(major=int(major), minor=int(minor))
        result[version] = val["name"]
    return result


def write_afdo_descriptor_file(
    path: Path, contents: Dict[KernelVersion, str]
) -> bool:
    """Writes the file at path with the given contents.

    Returns:
        True if the file was written due to changes, False otherwise.
    """
    contents_dict = {
        f"chromeos-kernel-{k.major}_{k.minor}": {"name": gs_name}
        for k, gs_name in contents.items()
    }

    contents_json = json.dumps(contents_dict, indent=4, sort_keys=True)
    try:
        existing_contents = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing_contents = ""

    # Compare the _textual representation_ of each of these, since things like
    # formatting changes should be propagated eagerly.
    if contents_json == existing_contents:
        return False

    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(contents_json, encoding="utf-8")
    tmp_path.rename(path)
    return True


@dataclasses.dataclass
class UpdateResult:
    """Result of `update_afdo_for_channel`."""

    # True if changes were made to the AFDO files that map kernel versions to
    # AFDO profiles.
    made_changes: bool

    # Whether issues were had updating one or more profiles. If this is True,
    # you may expect that there will be logs about the issues already.
    had_failures: bool


def fetch_and_validate_newest_afdo_artifact(
    fetcher: KernelProfileFetcher,
    selection_info: ProfileSelectionInfo,
    arch: Arch,
    kernel_version: KernelVersion,
    branch: GitBranch,
    channel: Channel,
) -> Optional[str]:
    """Tries to update one AFDO profile on a branch.

    Returns:
        The newest artifact name if all went well. None if something failed
        along the way, and the update couldn't be completed.
    """
    newest_artifact = find_newest_afdo_artifact(
        fetcher, arch, kernel_version, branch.release_number
    )
    # Try an older branch if we're not on stable. We should fail harder if we
    # only have old profiles on stable, though.
    if newest_artifact is None and channel != Channel.STABLE:
        newest_artifact = find_newest_afdo_artifact(
            fetcher, arch, kernel_version, branch.release_number - 1
        )

    if newest_artifact is None:
        logging.error(
            "No new profile found for %s/%s on M%d; not updating entry",
            arch,
            kernel_version,
            branch.release_number,
        )
        return None

    logging.info(
        "Newest profile is %s for %s/%s on M%d",
        newest_artifact.file_name,
        arch,
        kernel_version,
        branch.release_number,
    )
    age = selection_info.now - newest_artifact.gs_timestamp
    if age > selection_info.max_profile_age:
        logging.error(
            "Profile %s is %s old. Skipping it, since the configured limit "
            "is %s.",
            newest_artifact.file_name,
            age,
            selection_info.max_profile_age,
        )
        return None
    return newest_artifact.file_name_no_suffix


def update_afdo_for_channel(
    fetcher: KernelProfileFetcher,
    toolchain_utils: Path,
    selection_info: ProfileSelectionInfo,
    channel: Channel,
    branch: GitBranch,
    skipped_versions: Dict[int, Iterable[Tuple[Arch, KernelVersion]]],
) -> UpdateResult:
    """Updates AFDO on the given channel."""
    git_checkout(toolchain_utils, branch)
    update_cfgs = read_update_cfg_file(
        toolchain_utils,
        toolchain_utils / "afdo_tools" / "update_kernel_afdo.cfg",
    )

    to_skip = skipped_versions.get(branch.release_number)
    made_changes = False
    had_failures = False
    for arch, cfg in update_cfgs.items():
        afdo_mappings = read_afdo_descriptor_file(cfg.metadata_file)
        for kernel_version in cfg.versions_to_track:
            if to_skip and (arch, kernel_version) in to_skip:
                logging.info(
                    "%s/%s on M%d is in the skip list; ignoring it.",
                    arch,
                    kernel_version,
                    branch.release_number,
                )
                continue

            newest_name = fetch_and_validate_newest_afdo_artifact(
                fetcher,
                selection_info,
                arch,
                kernel_version,
                branch,
                channel,
            )
            if newest_name is None:
                # Assume that the problem was already logged.
                had_failures = True
            else:
                afdo_mappings[kernel_version] = newest_name

        if write_afdo_descriptor_file(cfg.metadata_file, afdo_mappings):
            made_changes = True
            logging.info(
                "Wrote new AFDO mappings for arch %s on M%d",
                arch,
                branch.release_number,
            )
        else:
            logging.info(
                "No changes to write for arch %s on M%d",
                arch,
                branch.release_number,
            )
    return UpdateResult(
        made_changes=made_changes,
        had_failures=had_failures,
    )


def commit_new_profiles(
    toolchain_utils: Path, channel: Channel, had_failures: bool
):
    """Runs `git commit -a` with an appropriate message."""
    commit_message_lines = [
        "afdo_metadata: Publish the new kernel profiles",
        "",
    ]

    if had_failures:
        commit_message_lines += (
            "This brings some profiles to their newest versions. The CrOS",
            "toolchain detective has been notified about the failures that",
            "occurred in this update.",
        )
    else:
        commit_message_lines.append(
            "This brings all profiles to their newest versions."
        )

    if channel != Channel.CANARY:
        commit_message_lines += (
            "",
            "Have PM pre-approval because this shouldn't break the release",
            "branch.",
        )

    commit_message_lines += (
        "",
        "BUG=None",
        "TEST=Verified in kernel-release-afdo-verify-orchestrator",
    )

    commit_msg = "\n".join(commit_message_lines)
    subprocess.run(
        [
            "git",
            "commit",
            "--quiet",
            "-a",
            "-m",
            commit_msg,
        ],
        cwd=toolchain_utils,
        check=True,
        stdin=subprocess.DEVNULL,
    )


def parse_cl_from_upload_output(upload_output: str) -> str:
    """Returns the CL number in the given upload output."""
    id_regex = re.compile(
        r"^remote:\s+https://chromium-review\S+/\+/(\d+)\s", re.MULTILINE
    )

    results = id_regex.findall(upload_output)
    if len(results) != 1:
        raise ValueError(
            f"Wanted exactly one match for {id_regex} in {upload_output!r}; "
            f"found {len(results)}"
        )
    return results[0]


def upload_head_to_gerrit(
    toolchain_utils: Path,
    branch: GitBranch,
):
    """Uploads HEAD to gerrit as a CL, and sets reviewers/CCs."""
    option_list = [f"r={x}" for x in CL_REVIEWERS]
    option_list += (f"cc={x}" for x in CL_CC)
    options = ",".join(option_list)
    run_result = subprocess.run(
        [
            "git",
            "push",
            branch.remote,
            # https://gerrit-review.googlesource.com/Documentation/user-upload.html#reviewers
            # for more info on the `%` params.
            f"HEAD:refs/for/{branch.branch_name}%{options}",
        ],
        cwd=toolchain_utils,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )

    logging.info(
        "`git push`ing to %s had this output:\n%s",
        branch.branch_name,
        run_result.stdout,
    )
    run_result.check_returncode()

    cl_id = parse_cl_from_upload_output(run_result.stdout)
    logging.info("Uploaded CL http://crrev.com/c/%s successfully.", cl_id)

    # To make the life of the reviewers marginally easier, click buttons
    # automatically.
    gerrit_commands = (
        ["gerrit", "label-as", cl_id, "1"],
        ["gerrit", "label-cq", cl_id, "1"],
        ["gerrit", "label-v", cl_id, "1"],
    )
    for cmd in gerrit_commands:
        # Run the gerrit commands inside of toolchain_utils, since `gerrit`
        # needs to be run inside of a ChromeOS tree to work. While
        # `toolchain-utils` can be checked out on its own, that's not how this
        # script is expeted to be used.
        return_code = subprocess.run(
            cmd,
            check=False,
            stdin=subprocess.DEVNULL,
        ).returncode
        if return_code:
            logging.warning(
                "Failed to run gerrit command %s. Ignoring.",
                shlex.join(cmd),
            )


def main(argv: List[str]) -> None:
    my_dir = Path(__file__).resolve().parent
    toolchain_utils = my_dir.parent

    opts = get_parser().parse_args(argv)
    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.DEBUG if opts.debug else logging.INFO,
    )

    if opts.fetch:
        logging.info("Fetching in %s...", toolchain_utils)
        git_fetch(toolchain_utils)

    selection_info = ProfileSelectionInfo(
        now=datetime.datetime.now(datetime.timezone.utc),
        max_profile_age=datetime.timedelta(days=opts.max_age_days),
    )

    branches = autodetect_branches(toolchain_utils)
    logging.debug("Current branches: %s", branches)

    assert all(x in branches for x in Channel), "branches are missing channels?"

    fetcher = KernelProfileFetcher()
    had_failures = False
    with git_worktree(toolchain_utils) as worktree:
        for channel in opts.channel:
            branch = branches[channel]
            result = update_afdo_for_channel(
                fetcher,
                worktree,
                selection_info,
                channel,
                branch,
                SKIPPED_VERSIONS,
            )
            had_failures = had_failures or result.had_failures
            if not result.made_changes:
                logging.info("No new updates to post on %s", channel)
                continue

            commit_new_profiles(worktree, channel, result.had_failures)
            if opts.upload:
                logging.info("New profiles were committed. Uploading...")
                upload_head_to_gerrit(worktree, branch)
            else:
                logging.info(
                    "--upload not specified. Leaving commit for %s at %s",
                    channel,
                    git_rev_parse(worktree, "HEAD"),
                )

    if had_failures:
        sys.exit(
            "At least one failure was encountered running this script; see "
            "above logs."
        )


if __name__ == "__main__":
    main(sys.argv[1:])
