#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helps reason about -Werror logs emitted by the compiler wrapper.

Specifically, this works with the -Werror reports produced by the compiler
wrapper in FORCE_DISABLE_WERROR mode. It's intended to be run on trees of these
reports, so devs can run roughly the following commands:

$ apply_force_disable_werror  # (There's no actual script to do this today.)
$ build_packages --board=foo --nousepkg
$ ./werror_logs.py aggregate --directory=/build/foo/var/lib/chromeos

And see a full aggregation of all warnings that were suppressed in that
`build_packages` invocation.
"""

import argparse
import collections
import dataclasses
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Counter, DefaultDict, Dict, IO, Iterable, List, Optional


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class ClangWarningLocation:
    """Represents a location at which a Clang warning was emitted."""

    file: str
    line: int
    column: int

    @classmethod
    def parse(cls, location: str) -> "ClangWarningLocation":
        split = location.rsplit(":", 2)
        if len(split) == 3:
            return cls(file=split[0], line=int(split[1]), column=int(split[2]))
        raise ValueError(f"Invalid location: {location!r}")


@dataclasses.dataclass(frozen=True, eq=True)
class ClangWarning:
    """Represents a Clang warning at a specific location (if applicable)."""

    # The name of the warning, e.g., -Wunused-variable
    name: str
    # The message of the warning, e.g., "'allocate' is deprecated."
    message: str
    # The location of this warning. Not present for frontend diagnostics.
    location: Optional[ClangWarningLocation]

    # This parses two kinds of errors:
    # 1. `clang-17: error: foo [-Werror,...]`
    # 2. `/file/path:123:45: error: foo [-Werror,...]"
    _WARNING_RE = re.compile(
        # Capture the location on its own, since `clang-\d+` is unused below.
        r"^(?:([^:]*:\d+:\d+)|clang-\d+)"
        r": error: "
        # Capture the message
        r"(.*?)\s+"
        r"\[(-W[^\][]+)]\s*$"
    )

    @classmethod
    def try_parse_line(cls, line: str) -> Optional["ClangWarning"]:
        # Fast path: we can expect "error: " in interesting lines. Break early
        # if that's not present.
        if "error: " not in line:
            return None

        m = cls._WARNING_RE.fullmatch(line)
        if not m:
            return None

        location, message, warning_flags = m.groups()
        individual_warning_flags = warning_flags.split(",")
        try:
            werror_index = individual_warning_flags.index("-Werror")
        except ValueError:
            # Somehow this warning is fatal, but not related to -Werror. Since
            # we're only interested in -Werror warnings, drop it.
            logging.warning(
                "Fatal warning that has nothing to do with -Werror? %r", line
            )
            return None

        del individual_warning_flags[werror_index]

        # This isn't impossible to handle, just unexpected. Complain about it.
        if len(individual_warning_flags) != 1:
            raise ValueError(
                f"Weird: parsed warnings {individual_warning_flags} out "
                f"of {line}"
            )

        if location is None:
            parsed_location = None
        else:
            parsed_location = ClangWarningLocation.parse(location)
        return cls(
            name=individual_warning_flags[0],
            message=message,
            location=parsed_location,
        )


@dataclasses.dataclass(frozen=True, eq=True)
class WarningInfo:
    """Carries information about a ClangWarning."""

    packages: DefaultDict[str, int] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(int)
    )


class UnknownPackageNameError(ValueError):
    """Raised when a package name can't be determined from a warning report."""


@dataclasses.dataclass
class AggregatedWarnings:
    """Aggregates warning reports incrementally."""

    num_reports: int = 0
    # Mapping of warning -> list of packages that emitted it. Warnings in
    # headers may be referred to by multiple packages.
    warnings: DefaultDict[ClangWarning, WarningInfo] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(WarningInfo)
    )

    _CWD_PACKAGE_RE = re.compile(
        r"^(?:/build/[^/]+)?/var/(?:cache|tmp)/portage/([^/]+/[^/]+)/"
    )

    @classmethod
    def _guess_package_name(cls, report: Dict[str, Any]) -> str:
        """Tries to guess what package `report` is from.

        Raises:
            UnknownPackageNameError if the package's name couldn't be
            determined.
        """
        m = cls._CWD_PACKAGE_RE.match(report.get("cwd", ""))
        if not m:
            raise UnknownPackageNameError()
        return m.group(1)

    def add_report_json(self, report_json: Dict[str, Any]) -> int:
        """Adds the given report, returning the number of warnings parsed.

        Raises:
            UnknownPackageNameError if the package's name couldn't be
            determined.
        """
        self.num_reports += 1
        package_name = self._guess_package_name(report_json)

        num_warnings = 0
        for line in report_json.get("stdout", "").splitlines():
            if parsed := ClangWarning.try_parse_line(line):
                self.warnings[parsed].packages[package_name] += 1
                num_warnings += 1

        return num_warnings

    def add_report(self, report_file: Path) -> None:
        with report_file.open(encoding="utf-8") as f:
            report = json.load(f)

        try:
            n = self.add_report_json(report)
        except UnknownPackageNameError:
            logging.warning(
                "Failed guessing package name for report at %r; ignoring file",
                report_file,
            )
            return

        if not n:
            logging.warning(
                "Report at %r had no parseable warnings", report_file
            )


def print_aligned_counts(
    name_count_map: Dict[str, int], file: Optional[IO[str]] = None
) -> None:
    assert name_count_map
    # Sort on value, highest first. Name breaks ties.
    summary = sorted(name_count_map.items(), key=lambda x: (-x[1], x[0]))
    num_col_width = len(f"{summary[0][1]:,}")
    name_col_width = max(len(x) for x in name_count_map)
    for name, count in summary:
        fmt_name = name.rjust(name_col_width)
        fmt_count = f"{count:,}".rjust(num_col_width)
        print(f"\t{fmt_name}: {fmt_count}", file=file)


def summarize_per_package_warnings(
    warning_infos: Iterable[WarningInfo],
    file: Optional[IO[str]] = None,
) -> None:
    warnings_per_package: DefaultDict[str, int] = collections.defaultdict(int)
    for info in warning_infos:
        for package_name, warning_count in info.packages.items():
            warnings_per_package[package_name] += warning_count

    if not warnings_per_package:
        return

    print("## Per-package warning counts:", file=file)
    print_aligned_counts(warnings_per_package, file=file)


def summarize_warnings_by_flag(
    warnings: Dict[ClangWarning, WarningInfo],
    file: Optional[IO[str]] = None,
) -> None:
    if not warnings:
        return

    warnings_per_flag: Counter[str] = collections.Counter()
    for warning, info in warnings.items():
        warnings_per_flag[warning.name] += sum(info.packages.values())

    print("## Instances of each fatal warning:", file=file)
    print_aligned_counts(warnings_per_flag, file=file)


def aggregate_reports(opts: argparse.Namespace) -> None:
    directory = opts.directory
    aggregated = AggregatedWarnings()
    for report in directory.glob("**/warnings_report*.json"):
        logging.debug("Discovered report %s", report)
        aggregated.add_report(report)

    if not aggregated.num_reports:
        raise ValueError(f"Found no warnings report under {directory}")

    logging.info("Discovered %d report files in total", aggregated.num_reports)
    summarize_per_package_warnings(aggregated.warnings.values())
    summarize_warnings_by_flag(aggregated.warnings)


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    subparsers = parser.add_subparsers(required=True)
    # b/318833638: While there's only one subparser here for the moment, more
    # are expected to come (specifically, one to download logs from a CQ run).
    aggregate = subparsers.add_parser(
        "aggregate",
        help="""
        Aggregate all -Werror reports beneath a directory. Note that this will
        traverse all children of the directory, so can be used either on
        unpacked -Werror reports from CQ builders, or can be used on e.g.,
        /build/cherry/var/lib/chromeos.
        """,
    )
    aggregate.set_defaults(func=aggregate_reports)
    aggregate.add_argument(
        "--directory", type=Path, required=True, help="Directory to inspect."
    )

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
