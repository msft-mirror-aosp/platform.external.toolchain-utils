#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetches the size diff between two images on gs://.

If given a CL, this will autodetect a passing CQ builder on that CL and find
a corresponding release build for said CQ builder. The sizes of these images
will be compared.

**Please note** that there's often version skew between release builds and CQ
builds. While this skew shouldn't result in _huge_ binary size differences,
it can still account for a few MB of diff in an average case.
"""

import argparse
import dataclasses
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

import cros_cls


@dataclasses.dataclass(frozen=True)
class SizeDiffInfo:
    """Holds information about a size difference."""

    baseline_size_bytes: int
    new_size_bytes: int


def download_and_measure_size(image_zip: str) -> int:
    """Downloads image_zip into a tempdir dir, and measures its size."""
    with tempfile.TemporaryDirectory(prefix="fetch_size_diff_") as tempdir_str:
        into = Path(tempdir_str)
        local_image_zip = into / "image.zip"
        subprocess.run(
            ["gsutil", "cp", image_zip, local_image_zip],
            check=True,
            stdin=subprocess.DEVNULL,
        )
        binpkg_sizes_name = "chromiumos_base_image.bin-package-sizes.json"
        subprocess.run(
            [
                "unzip",
                local_image_zip.name,
                binpkg_sizes_name,
            ],
            check=True,
            cwd=into,
            stdin=subprocess.DEVNULL,
        )
        with (into / binpkg_sizes_name).open(encoding="utf-8") as f:
            loaded = json.load(f)
            try:
                size = loaded["total_size"]
            except KeyError:
                raise ValueError(f"Missing total_size in {loaded.keys()}")

            if not isinstance(size, int):
                raise ValueError(
                    f"total_size was unexpectedly {type(size)}: {size}"
                )
            return size


def compare_gs_images(
    baseline_image_zip: str, new_image_zip: str
) -> SizeDiffInfo:
    """Returns a SizeDiffInfo representing the given image.zip sizes."""
    return SizeDiffInfo(
        baseline_size_bytes=download_and_measure_size(baseline_image_zip),
        new_size_bytes=download_and_measure_size(new_image_zip),
    )


def is_probably_non_production_builder(builder_name: str) -> bool:
    """Quickly determine if a builder doesn't represent a board in production.

    Note that this is a heuristic; results should be taken as mostly accurate.
    """
    return any(
        x in builder_name
        for x in (
            "-asan-",
            "-buildtest-",
            "-fuzzer-",
            "-kernelnext-",
            "-ubsan-",
            "-vmtest-",
        )
    )


def guess_release_artifact_path(artifact_link: str) -> Optional[str]:
    """Guesses a close-enough release path for a CQ artifact.

    Returns:
        A path to the release artifact. Returns None if the given image_zip
        wasn't generated by a CQ builder.

    >>> guess_release_artifact_path("gs://chromeos-image-archive/brya-cq/"
        "R121-15677.0.0-90523-8764532770258575633/image.zip")
    "gs://chromeos-image-archive/brya-release/R121-15677.0.0/image.zip"
    """
    artifacts_link = os.path.dirname(artifact_link)
    release_version = cros_cls.parse_release_from_builder_artifacts_link(
        artifacts_link
    )
    # Scrape the board name from a level above the artifacts directory.
    builder = os.path.basename(os.path.dirname(artifacts_link))
    if not builder.endswith("-cq"):
        return None
    board = builder[:-3]
    return (
        f"gs://chromeos-image-archive/{board}-release/{release_version}/"
        f"{os.path.basename(artifact_link)}"
    )


def try_gsutil_ls(paths: List[str]) -> List[str]:
    """Returns all of the paths `gsutil` matches from `paths`.

    Ignores errors from gsutil about paths not existing.
    """
    result = subprocess.run(
        ["gsutil", "-m", "ls"] + paths,
        # If any URI doesn't exist, gsutil will fail. Ignore the failure.
        check=False,
        encoding="utf-8",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        # Ensure the error message is what's expected, rather than e.g.,
        # invalid credentials.
        err_msg = "CommandException: One or more URLs matched no objects"
        if err_msg not in result.stderr:
            logging.error(
                "gsutil had unexpected output; stderr: %r", result.stderr
            )
            result.check_returncode()
    return [x.strip() for x in result.stdout.splitlines()]


def find_size_diffable_cq_artifacts(
    cq_build_ids: List[cros_cls.BuildID],
    artifact_name: str,
) -> Optional[Tuple[str, str]]:
    """Searches the cq-orchestrator builds for candidates for size comparison.

    Returns:
        None if no candidates are found. Otherwise, returns a two-tuple: index
        0 is the baseline (release) artifact, index 1 is the corresponding
        artifact generated by the CQ.
    """
    for cq_build_id in cq_build_ids:
        logging.info("Inspecting CQ build %d...", cq_build_id)
        orch_output = cros_cls.CQOrchestratorOutput.fetch(cq_build_id)
        child_builder_values = cros_cls.CQBoardBuilderOutput.fetch_many(
            [
                val
                for name, val in orch_output.child_builders.items()
                if not is_probably_non_production_builder(name)
            ]
        )
        artifacts_links = [
            x.artifacts_link
            for x in child_builder_values
            if x.artifacts_link is not None
        ]
        if not artifacts_links:
            logging.info("No children of CQ run %d had artifacts", cq_build_id)
            continue

        potential_artifacts = try_gsutil_ls(
            [os.path.join(x, artifact_name) for x in artifacts_links]
        )
        if not potential_artifacts:
            logging.info(
                "No children of CQ run %d produced a(n) %s",
                cq_build_id,
                artifact_name,
            )
            continue

        logging.debug(
            "Found candidate %s files: %s", artifact_name, potential_artifacts
        )
        guessed_paths = [
            (x, guess_release_artifact_path(x)) for x in potential_artifacts
        ]
        release_artifacts = try_gsutil_ls([x for _, x in guessed_paths if x])
        if not release_artifacts:
            logging.info(
                "No release %s artifacts could be found for CQ builder %d.",
                artifact_name,
                cq_build_id,
            )
            continue

        # `try_gsutil_ls` makes no ordering guarantees; always pick the min()
        # artifact here for consistency across reruns.
        selected_release_artifact = min(release_artifacts)
        logging.info("Selected release artifact: %s", selected_release_artifact)
        cq_artifact = next(
            cq_path
            for cq_path, guessed_path in guessed_paths
            if guessed_path == selected_release_artifact
        )
        return selected_release_artifact, cq_artifact
    return None


def inspect_gs_impl(baseline_gs_url: str, new_gs_url: str) -> None:
    """Compares the `image.zip`s at the given URLs, logging the results."""
    size_diff = compare_gs_images(baseline_gs_url, new_gs_url)
    # `%d` doesn't support `,` as a modifier, and commas make these numbers
    # much easier to read. Prefer to keep strings interpreted as format strings
    # constant.
    logging.info("Baseline size: %s", f"{size_diff.baseline_size_bytes:,}")
    logging.info("New size: %s", f"{size_diff.new_size_bytes:,}")

    diff_pct = abs(size_diff.new_size_bytes / size_diff.baseline_size_bytes) - 1
    logging.info("Diff: %.2f%%", diff_pct * 100)


def inspect_cl(opts: argparse.Namespace) -> None:
    """Implements the `cl` subcommand of this script."""
    cq_build_ids = cros_cls.fetch_cq_orchestrator_ids(opts.cl)
    if not cq_build_ids:
        sys.exit(f"No completed cq-orchestrators found for {opts.cl}")

    # Reverse cq_build_ids so we try the newest first.
    diffable_zips = find_size_diffable_cq_artifacts(cq_build_ids, "image.zip")
    if not diffable_zips:
        sys.exit("No viable images could be found to diff.")

    baseline, new = diffable_zips
    logging.info("Comparing %s (baseline) to %s (new)", baseline, new)
    inspect_gs_impl(baseline, new)
    logging.warning(
        "Friendly reminder: CL inspection diffs between your CL and a "
        "corresponding release build. Size differences up to a few megabytes "
        "are expected and do not necessarily indicate a size difference "
        "attributable to your CL."
    )


def inspect_gs(opts: argparse.Namespace) -> None:
    """Implements the `gs` subcommand of this script."""
    inspect_gs_impl(opts.baseline, opts.new)


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    subparsers = parser.add_subparsers(required=True)

    cl_parser = subparsers.add_parser(
        "cl", help="Inspect a CL's CQ runs to find artifacts to compare."
    )
    cl_parser.set_defaults(func=inspect_cl)
    cl_parser.add_argument(
        "cl",
        type=cros_cls.ChangeListURL.parse_with_patch_set,
        help="CL to inspect CQ runs of. This must contain a patchset number.",
    )

    gs_parser = subparsers.add_parser(
        "gs", help="Directly compare two zip files from gs://."
    )
    gs_parser.add_argument("baseline", help="Baseline file to compare.")
    gs_parser.add_argument("new", help="New file to compare.")
    gs_parser.set_defaults(func=inspect_gs)
    opts = parser.parse_args(argv)

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: "
        "%(message)s",
        level=logging.DEBUG if opts.debug else logging.INFO,
    )

    assert getattr(opts, "func", None), "Unknown subcommand?"
    opts.func(opts)


if __name__ == "__main__":
    main(sys.argv[1:])
