# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Automatically keeps llvm_next.py in the current toolchain-utils fresh.

The llvm_next.py file this targets is in the same directory as this script in
toolchain-utils. Actual edits are made in a worktree, and locally `git
commit`ed by this script.

It does this by:
    - Removing obsolete testing URLs
    - Auto-updating patch-sets as appropriate
"""

import argparse
import dataclasses
import json
import logging
from pathlib import Path
import subprocess
from typing import Iterable, List, Optional, Tuple

from cros_utils import cros_paths
from cros_utils import git_utils
from llvm_tools import cros_cls
from llvm_tools import llvm_next


# TODO: Should this be the Mage instead?
CL_REVIEWERS = (git_utils.REVIEWER_DETECTIVE,)


@dataclasses.dataclass(frozen=True, eq=True)
class GerritCLInfo:
    """Carries relevant info about a CL."""

    is_abandoned_or_merged: bool
    is_uploader_a_googler: bool
    most_recent_patch_set: int


def fetch_cl_info(cl: cros_cls.ChangeListURL) -> GerritCLInfo:
    gerrit_stdout = subprocess.run(
        ("gerrit", "--json", "inspect", cl.gerrit_tool_id),
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    ).stdout
    gerrit_info = json.loads(gerrit_stdout)[0]

    # cl_status is a ChangeInfo's status:
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-info
    cl_status = gerrit_info.get("status")
    if cl_status not in ("NEW", "MERGED", "ABANDONED"):
        raise ValueError(f"Unexpected CL status on {cl}: {cl_status!r}")

    current_ps_str = gerrit_info.get("currentPatchSet", {}).get("number")
    try:
        current_ps = int(current_ps_str)
    except ValueError:
        current_ps = None

    # Raise this outside of the exception handler, so the backtrace is easier
    # to understand.
    if current_ps is None:
        raise ValueError(
            f"Unexpected current patch-set number status on {cl}: "
            f"{current_ps_str!r}"
        )

    return GerritCLInfo(
        is_abandoned_or_merged=cl_status != "NEW",
        # Unfortunately, the owner that the gerrit tool reports isn't the
        # _uploader_ of the current patch set, so this field can't be
        # determined at the moment: b/354943075#comment2
        is_uploader_a_googler=False,
        most_recent_patch_set=current_ps,
    )


def update_testing_url_list(
    current_list: Iterable[str],
) -> Optional[Tuple[str, List[str]]]:
    new_list = []
    change_descriptions = []

    for url in current_list:
        cl_url = cros_cls.ChangeListURL.parse(url)
        cl_info = fetch_cl_info(cl_url)
        if cl_info.is_abandoned_or_merged:
            logging.info("%s was closed; removing from list", cl_url)
            change_descriptions.append(f"{cl_url} was closed")
            continue

        if cl_info.most_recent_patch_set == cl_url.patch_set:
            logging.info(
                "%s is alive and at most recent patch-set; nothing to do",
                cl_url,
            )
            # Append the URL verbatim to minimize diffs.
            new_list.append(url)
            continue

        if not cl_info.is_uploader_a_googler:
            logging.warning(
                "CL %s has newer patch-set, but isn't googler-uploaded. Skip.",
                cl_url,
            )
            # Append the URL verbatim to minimize diffs.
            new_list.append(url)
            continue

        logging.info("CL %s patch-set was updated; updating.", cl_url)
        change_descriptions.append(f"{cl_url} had a patch-set update")
        new_list.append(
            str(
                dataclasses.replace(
                    cl_url,
                    patch_set=cl_info.most_recent_patch_set,
                )
            )
        )

    # If there are no change descriptions, no meaningful changes were made.
    if not change_descriptions:
        return None

    return "\n".join(f"- {x}" for x in change_descriptions), new_list


def write_url_list(llvm_next_py_file_path: Path, new_url_list: List[str]):
    llvm_next_py = llvm_next_py_file_path.read_text(encoding="utf-8")
    var_start_string = "\nLLVM_NEXT_TESTING_CL_URLS: Iterable[str] = ("
    testing_cl_urls_start = llvm_next_py.index(var_start_string)

    # In a `cros format`'ed file, are two cases to handle here when finding the
    # last parenthesis:
    # 1. it's on the same line
    # 2. it's on a line of its own
    # Ignore anything else for simplicity.
    after_start_paren = testing_cl_urls_start + len(var_start_string)
    line_end = llvm_next_py.index("\n", after_start_paren)
    same_line_end_paren = llvm_next_py.find(")", after_start_paren, line_end)
    if same_line_end_paren != -1:
        end_paren = same_line_end_paren
    else:
        end_paren = llvm_next_py.index("\n)", after_start_paren)

    # N.B., "," is appended to each element rather than part of `"\n".join`,
    # since single-elem tuples need it.
    new_list_contents = "\n".join(repr(x) + "," for x in new_url_list)
    new_llvm_next_py = "\n".join(
        (
            llvm_next_py[:after_start_paren],
            new_list_contents,
            llvm_next_py[end_paren:],
        )
    )
    llvm_next_py_file_path.write_text(new_llvm_next_py, encoding="utf-8")
    subprocess.run(
        ("cros", "format", llvm_next_py_file_path),
        check=True,
    )


def main(argv: List[str]) -> None:
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
        "--upload",
        action="store_true",
        help="""
        Upload changes after making them, auto-add reviewer(s), and hit CQ+1.
        """,
    )
    opts = parser.parse_args(argv)

    update_result = update_testing_url_list(llvm_next.LLVM_NEXT_TESTING_CL_URLS)
    if not update_result:
        logging.info("All URLs are up-to-date.")
        return

    change_descriptions, new_url_list = update_result
    logging.info("URL list changed; creating commit...")
    with git_utils.create_worktree(
        cros_paths.script_toolchain_utils_root()
    ) as worktree:
        write_url_list(worktree / "llvm_tools" / "llvm_next.py", new_url_list)
        sha = git_utils.commit_all_changes(
            worktree,
            # Use "\n".join rather than textwrap.dedent, since
            # `change_descriptions` won't be indented properly
            message="\n".join(
                (
                    "llvm_tools: autoupdate CL list",
                    "",
                    change_descriptions,
                    "",
                    "BUG=None",
                    "TEST=CQ+1",
                )
            ),
        )
        logging.info("SHA of commit: %s", sha)
        if opts.upload:
            cl_list = git_utils.upload_to_gerrit(
                worktree,
                remote=git_utils.CROS_EXTERNAL_REMOTE,
                branch=git_utils.CROS_MAIN_BRANCH,
                reviewers=CL_REVIEWERS,
            )
            for cl in cl_list:
                git_utils.try_set_autosubmit_labels(worktree, cl)
