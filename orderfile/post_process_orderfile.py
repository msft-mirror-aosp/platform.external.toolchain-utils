#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to do post-process on orderfile generated by C3.

The goal of this script is to take in an orderfile generated by C3, and do
the following post process:

1. Take in the result of nm command on Chrome binary to find out all the
Builtin functions and put them after the input symbols.

2. Put special markers "chrome_begin_ordered_code" and "chrome_end_ordered_code"
in begin and end of the file.

The results of the file is intended to be uploaded and consumed when linking
Chrome in ChromeOS.
"""


import argparse
import os
import sys


def _parse_nm_output(stream):
    for line in (line.rstrip() for line in stream):
        if not line:
            continue

        pieces = line.split()
        if len(pieces) != 3:
            continue

        _, ty, symbol = pieces
        if ty not in "tT":
            continue

        # We'll sometimes see synthesized symbols that start with $. There isn't
        # much we can do about or with them, regrettably.
        if symbol.startswith("$"):
            continue

        yield symbol


def _remove_duplicates(iterable):
    seen = set()
    for item in iterable:
        if item in seen:
            continue
        seen.add(item)
        yield item


def run(c3_ordered_stream, chrome_nm_stream, output_stream):
    head_marker = "chrome_begin_ordered_code"
    tail_marker = "chrome_end_ordered_code"

    c3_ordered_syms = [x.strip() for x in c3_ordered_stream.readlines()]
    all_chrome_syms = set(_parse_nm_output(chrome_nm_stream))
    # Sort by name, so it's predictable. Otherwise, these should all land in the
    # same hugepage anyway, so order doesn't matter as much.
    builtin_syms = sorted(
        s for s in all_chrome_syms if s.startswith("Builtins_")
    )
    output = _remove_duplicates(
        [head_marker] + c3_ordered_syms + builtin_syms + [tail_marker]
    )
    output_stream.write("\n".join(output))


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome_nm", required=True, dest="chrome_nm")
    parser.add_argument("--input", required=True, dest="input_file")
    parser.add_argument("--output", required=True, dest="output_file")

    options = parser.parse_args(argv)

    if not os.path.exists(options.input_file):
        sys.exit("Input orderfile doesn't exist.")

    with open(options.input_file) as in_stream, open(
        options.chrome_nm
    ) as chrome_nm_stream, open(options.output_file, "w") as out_stream:
        run(in_stream, chrome_nm_stream, out_stream)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
