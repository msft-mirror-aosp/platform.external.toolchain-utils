#!/usr/bin/env python3
# Copyright 2024 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for werror_logs.py."""

import io
import logging
import textwrap
from typing import Dict
import unittest

import werror_logs


class SilenceLogs:
    """Used by Test.silence_logs to ignore all logging output."""

    def filter(self, _record):
        return False


def create_warning_info(packages: Dict[str, int]) -> werror_logs.WarningInfo:
    """Constructs a WarningInfo conveniently in one line.

    Mostly useful because `WarningInfo` has a defaultdict field, and those
    don't `assertEqual` to regular dict fields.
    """
    x = werror_logs.WarningInfo()
    x.packages.update(packages)
    return x


class Test(unittest.TestCase):
    """Tests for werror_logs."""

    def silence_logs(self):
        f = SilenceLogs()
        log = logging.getLogger()
        log.addFilter(f)
        self.addCleanup(log.removeFilter, f)

    def test_clang_warning_parsing_parses_flag_errors(self):
        self.assertEqual(
            werror_logs.ClangWarning.try_parse_line(
                "clang-17: error: optimization flag -foo is not supported "
                "[-Werror,-Wfoo]"
            ),
            werror_logs.ClangWarning(
                name="-Wfoo",
                message="optimization flag -foo is not supported",
                location=None,
            ),
        )

    def test_clang_warning_parsing_doesnt_care_about_werror_order(self):
        self.assertEqual(
            werror_logs.ClangWarning.try_parse_line(
                "clang-17: error: optimization flag -foo is not supported "
                "[-Wfoo,-Werror]"
            ),
            werror_logs.ClangWarning(
                name="-Wfoo",
                message="optimization flag -foo is not supported",
                location=None,
            ),
        )

    def test_clang_warning_parsing_parses_code_errors(self):
        self.assertEqual(
            werror_logs.ClangWarning.try_parse_line(
                "/path/to/foo/bar/baz.cc:12:34: error: don't do this "
                "[-Werror,-Wbar]"
            ),
            werror_logs.ClangWarning(
                name="-Wbar",
                message="don't do this",
                location=werror_logs.ClangWarningLocation(
                    file="/path/to/foo/bar/baz.cc",
                    line=12,
                    column=34,
                ),
            ),
        )

    def test_clang_warning_parsing_skips_uninteresting_lines(self):
        self.silence_logs()

        pointless = (
            "",
            "foo",
            "error: something's wrong",
            "clang-14: warning: something's wrong [-Wsomething]",
            "clang-14: error: something's wrong [-Wsomething,-Wnot-werror]",
        )
        for line in pointless:
            self.assertIsNone(
                werror_logs.ClangWarning.try_parse_line(line), line
            )

    def test_aggregation_correctly_scrapes_warnings(self):
        aggregated = werror_logs.AggregatedWarnings()
        aggregated.add_report_json(
            {
                "cwd": "/var/tmp/portage/sys-devel/llvm/foo/bar",
                "stdout": textwrap.dedent(
                    """\
                    Foo
                    clang-17: error: failed to blah [-Werror,-Wblah]
                    /path/to/file.cc:1:2: error: other error [-Werror,-Wother]
                    """
                ),
            }
        )
        aggregated.add_report_json(
            {
                "cwd": "/var/tmp/portage/sys-devel/llvm/foo/bar",
                "stdout": textwrap.dedent(
                    """\
                    Foo
                    clang-17: error: failed to blah [-Werror,-Wblah]
                    /path/to/file.cc:1:3: error: other error [-Werror,-Wother]
                    Bar
                    """
                ),
            }
        )

        self.assertEqual(aggregated.num_reports, 2)
        self.assertEqual(
            dict(aggregated.warnings),
            {
                werror_logs.ClangWarning(
                    name="-Wblah",
                    message="failed to blah",
                    location=None,
                ): create_warning_info(
                    packages={"sys-devel/llvm": 2},
                ),
                werror_logs.ClangWarning(
                    name="-Wother",
                    message="other error",
                    location=werror_logs.ClangWarningLocation(
                        file="/path/to/file.cc",
                        line=1,
                        column=2,
                    ),
                ): create_warning_info(
                    packages={"sys-devel/llvm": 1},
                ),
                werror_logs.ClangWarning(
                    name="-Wother",
                    message="other error",
                    location=werror_logs.ClangWarningLocation(
                        file="/path/to/file.cc",
                        line=1,
                        column=3,
                    ),
                ): create_warning_info(
                    packages={"sys-devel/llvm": 1},
                ),
            },
        )

    def test_aggregation_guesses_packages_correctly(self):
        aggregated = werror_logs.AggregatedWarnings()
        cwds = (
            "/var/tmp/portage/sys-devel/llvm/foo/bar",
            "/var/cache/portage/sys-devel/llvm/foo/bar",
            "/build/amd64-host/var/tmp/portage/sys-devel/llvm/foo/bar",
            "/build/amd64-host/var/cache/portage/sys-devel/llvm/foo/bar",
        )
        for d in cwds:
            # If the directory isn't recognized, this will raise.
            aggregated.add_report_json(
                {
                    "cwd": d,
                    "stdout": "clang-17: error: foo [-Werror,-Wfoo]",
                }
            )

        self.assertEqual(len(aggregated.warnings), 1)
        warning, warning_info = next(iter(aggregated.warnings.items()))
        self.assertEqual(warning.name, "-Wfoo")
        self.assertEqual(
            warning_info, create_warning_info({"sys-devel/llvm": len(cwds)})
        )

    def test_aggregation_raises_if_package_name_cant_be_guessed(self):
        aggregated = werror_logs.AggregatedWarnings()
        with self.assertRaises(werror_logs.UnknownPackageNameError):
            aggregated.add_report_json({})

    def test_warning_by_flag_summarization_works_in_simple_case(self):
        string_io = io.StringIO()
        werror_logs.summarize_warnings_by_flag(
            {
                werror_logs.ClangWarning(
                    name="-Wother",
                    message="other error",
                    location=werror_logs.ClangWarningLocation(
                        file="/path/to/some/file.cc",
                        line=1,
                        column=2,
                    ),
                ): create_warning_info(
                    {
                        "sys-devel/llvm": 3000,
                        "sys-devel/gcc": 1,
                    }
                ),
                werror_logs.ClangWarning(
                    name="-Wother",
                    message="other error",
                    location=werror_logs.ClangWarningLocation(
                        file="/path/to/some/file.cc",
                        line=1,
                        column=3,
                    ),
                ): create_warning_info(
                    {
                        "sys-devel/llvm": 1,
                    }
                ),
            },
            file=string_io,
        )
        result = string_io.getvalue()
        self.assertEqual(
            result,
            textwrap.dedent(
                """\
                ## Instances of each fatal warning:
                \t-Wother: 3,002
                """
            ),
        )

    def test_warning_by_package_summarization_works_in_simple_case(self):
        string_io = io.StringIO()
        werror_logs.summarize_per_package_warnings(
            (
                create_warning_info(
                    {
                        "sys-devel/llvm": 3000,
                        "sys-devel/gcc": 1,
                    }
                ),
                create_warning_info(
                    {
                        "sys-devel/llvm": 1,
                    }
                ),
            ),
            file=string_io,
        )
        result = string_io.getvalue()
        self.assertEqual(
            result,
            textwrap.dedent(
                """\
                ## Per-package warning counts:
                \tsys-devel/llvm: 3,001
                \t sys-devel/gcc:     1
                """
            ),
        )


if __name__ == "__main__":
    unittest.main()
