#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build script that builds a binary from a bundle."""

from __future__ import print_function

import argparse
import os.path
import subprocess
import sys


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--config',
      required=True,
      choices=['cros.hardened', 'cros.nonhardened', 'cros.host'])
  parser.add_argument('--use_ccache', required=True, choices=['true', 'false'])
  parser.add_argument('--output_file', required=True, type=str)
  return parser.parse_args()


def calc_go_args(args):
  # See https://github.com/golang/go/issues/26492 for how to
  # build a fully static binary in go.
  ldFlags = [
      '-X', 'main.ConfigName=' + args.config, '-X',
      'main.UseCCache=' + args.use_ccache, '-extldflags \'-fno-PIC -static\''
  ]
  return [
      'go', 'build', '-o',
      os.path.abspath(args.output_file), '-ldflags', ' '.join(ldFlags),
      '-buildmode', 'pie', '-tags', 'osusergo netgo static_build'
  ]


def main():
  args = parse_args()
  # Note: Go does not support using absolute package names.
  # So we run go inside the directory of the the build file.
  sys.exit(subprocess.call(calc_go_args(args), cwd=os.path.dirname(__file__)))


if __name__ == '__main__':
  main()
