# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script used to accompany the InsertBraces LSC: b/319265940.

Run this from inside of the chroot.
"""

import argparse
import contextlib
import dataclasses
import logging
from pathlib import Path
import re
import subprocess
import sys
import textwrap
from typing import List, Optional

from cros_utils import cros_paths
from cros_utils import git_utils
from llvm_tools import chroot


# Text in .clang-format files that indicates that the directory containing said
# file has not yet been migrated.
CLANG_FORMAT_MIGRATION_COMMENT = """\
# TODO(b/319265940): remove this file once this subdir is formatted.
"""
CLANG_FORMAT_INSERT_BRACES_DIRECTIVE = "\nInsertBraces: false"

# C++ file types to migrate.
CPP_FILE_TYPES = (".c", ".cc", ".cpp", ".h")


@dataclasses.dataclass(frozen=True)
class CommitMessageGenerator:
    """Generates commit messages, given params from the script's invocation."""

    platform2_base_commit: str
    flag_start_project: Optional[str]
    flag_n: Optional[int]

    def generate(self, subproject_name: str) -> str:
        if self.flag_start_project:
            start_project_explainer = f"set to {self.flag_start_project}"
        else:
            start_project_explainer = "unset"

        if self.flag_n:
            n_explainer = f"set to {self.flag_n}"
        else:
            n_explainer = "unset"

        return textwrap.dedent(
            f"""\
            {subproject_name}: IncludeBraces LSC

            This removes the IncludeBraces workaround from .clang-tidy in this
            project, and runs `cros format` to bring files in line with
            Chromium's new style.

            For more information on this LSC, see go/cros-insert-braces-lsc.

            To reproduce _just_ this CL, inside of the chroot, run:
                $ ${{toolchain_utils}}/py/bin/llvm_tools/insert_braces.py \\
                    --start-project={subproject_name} \\
                    -n 1 \\
                    --platform2-commit={self.platform2_base_commit}

            To reproduce the stack this was a part of, you can run the same
            command, but with `--start-project` {start_project_explainer} and
            -n {n_explainer}.

            BUG=b:370478040
            TEST=CQ
            """
        )


def enumerate_unmigrated_platform2_projects(platform2: Path) -> List[str]:
    results = []
    for maybe_subdir in platform2.iterdir():
        if not maybe_subdir.is_dir():
            continue

        try:
            clang_fmt = (maybe_subdir / ".clang-format").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            continue

        if CLANG_FORMAT_MIGRATION_COMMENT in clang_fmt:
            results.append(maybe_subdir.name)

    results.sort()
    return results


def clang_format_file_has_useful_directives(file_contents: str):
    """Returns True if the given clang-format config file has useful bits.

    Moreover, if the file does is nothing, or just inherits directly from its
    parent, this returns False.
    """
    based_on_parent = re.compile(r"^BasedOnStyle:\s*InheritParentConfig\s*$")
    for line in file_contents.splitlines():
        line = line.split("#")[0].strip()
        if line and not based_on_parent.fullmatch(line):
            return True
    return False


def toggle_clang_format_key(
    clang_format: str, key_name: str, new_value: str
) -> str:
    # We're guaranteed a newline before the key name, since:
    # 1. This is only ever used for top-level keys.
    # 2. All files must start with a copyright header.
    key_search = f"\n{key_name}:"
    i = clang_format.find(key_search)
    if i == -1:
        raise ValueError(f"No key {key_name} found in clang-format file")

    following_newline = clang_format.find("\n", i + len(key_search))
    if following_newline == -1:
        following_newline = len(clang_format)

    new_key_assignment = f"\n{key_name}: {new_value}"
    return (
        clang_format[:i] + new_key_assignment + clang_format[following_newline:]
    )


@contextlib.contextmanager
def disabled_include_sorting(platform2: Path):
    clang_format = platform2 / ".clang-format"
    old_clang_format_text = clang_format.read_text(encoding="utf-8")

    new_clang_format_text = toggle_clang_format_key(
        old_clang_format_text,
        "IncludeBlocks",
        "Preserve",
    )
    new_clang_format_text = toggle_clang_format_key(
        new_clang_format_text,
        "SortIncludes",
        "Never",
    )
    clang_format.write_text(new_clang_format_text, encoding="utf-8")

    try:
        yield
    finally:
        clang_format.write_text(old_clang_format_text, encoding="utf-8")


def discard_clang_format_migration_text(platform2_subproject: Path):
    clang_format = platform2_subproject / ".clang-format"
    clang_format_text = clang_format.read_text(encoding="utf-8")
    new_clang_format_text = clang_format_text.replace(
        CLANG_FORMAT_MIGRATION_COMMENT, ""
    ).replace(CLANG_FORMAT_INSERT_BRACES_DIRECTIVE, "")
    if clang_format_file_has_useful_directives(new_clang_format_text):
        clang_format.write_text(new_clang_format_text, encoding="utf-8")
    else:
        clang_format.unlink()


def migrate_subproject(
    platform2: Path,
    subproject_name: str,
    commit_message_generator: CommitMessageGenerator,
) -> str:
    """Migrates a single subproject."""
    subproject_path = platform2 / subproject_name
    discard_clang_format_migration_text(subproject_path)
    format_command = ["cros", "format", "."]
    format_command += (f"--include=*{ext}" for ext in CPP_FILE_TYPES)
    format_command.append("--exclude=*")
    with disabled_include_sorting(platform2):
        subprocess.run(format_command, check=True, cwd=subproject_path)
    return git_utils.commit_all_changes(
        git_dir=platform2,
        message=commit_message_generator.generate(subproject_name),
    )


def main(argv: List[str]) -> None:
    chroot.VerifyInsideChroot()

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
        "--start-project",
        help="""
        Platform2 project name to start running this LSC on. This script works
        on subdirectories in sorted order, so only projects that sort equal to
        or greater than this project's name will be considered by this script.
        """,
    )
    parser.add_argument(
        "--platform2-commit",
        help="""
        If passed, platform2 will be checked out to the given commit before
        fixes are applied.
        """,
    )
    parser.add_argument(
        "-n",
        type=int,
        help="Number of projects to format. Formats all if unspecified.",
    )
    opts = parser.parse_args(argv)

    num_projects: Optional[int] = opts.n
    platform2_commit: Optional[str] = opts.platform2_commit
    start_project: Optional[str] = opts.start_project

    platform2 = cros_paths.CHROOT_SOURCE_ROOT / "src" / "platform2"
    unmigrated_projects = enumerate_unmigrated_platform2_projects(platform2)
    logging.info(
        "%d projects have yet to be migrated.", len(unmigrated_projects)
    )

    if not unmigrated_projects:
        sys.exit("All projects have seemingly been migrated")

    if start_project:
        remaining_projects = [
            x for x in unmigrated_projects if x >= start_project
        ]
        logging.info(
            "%d projects are candidates for migration", len(remaining_projects)
        )
    else:
        remaining_projects = unmigrated_projects

    if num_projects:
        skipped_projects = remaining_projects[num_projects:]
        remaining_projects = remaining_projects[:num_projects]
    else:
        skipped_projects = []

    if not remaining_projects:
        sys.exit("No migratable projects meet the given criteria")

    logging.info("Will migrate %d projects.", len(remaining_projects))
    # The loop below is guaranteed to run because `remaining_projects` has a
    # length check above. Set `sha` here to appease linting tools.
    sha = ""
    with git_utils.create_worktree(
        platform2, commitish=platform2_commit
    ) as platform2_worktree:
        commit_message_generator = CommitMessageGenerator(
            platform2_base_commit=git_utils.resolve_ref(
                git_dir=platform2_worktree, ref="HEAD"
            ),
            flag_start_project=start_project,
            flag_n=num_projects,
        )

        for subproject in remaining_projects:
            logging.info("Migrating %s...", subproject)
            sha = migrate_subproject(
                platform2_worktree,
                subproject,
                commit_message_generator,
            )
            logging.info("SHA for project %s is %s", subproject, sha)

    if skipped_projects:
        logging.info(
            "Next project that would've been migrated if not for limits: %s",
            skipped_projects[0],
        )

    assert sha, "Loop above didn't go?"
    logging.info("HEAD of platform2 with changes is %s", sha)


if __name__ == "__main__":
    main(sys.argv[1:])
