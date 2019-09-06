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
  parser.add_argument('--old_wrapper_path', required=True)
  parser.add_argument('--output_file', required=True, type=str)
  return parser.parse_args()


def calc_go_args(args, version):
  ldFlags = [
      '-X',
      'main.ConfigName=' + args.config,
      '-X',
      'main.UseCCache=' + args.use_ccache,
      '-X',
      'main.OldWrapperPath=' + args.old_wrapper_path,
      '-X',
      'main.Version=' + version,
  ]
  return [
      'go', 'build', '-o',
      os.path.abspath(args.output_file), '-ldflags', ' '.join(ldFlags)
  ]


def read_version(build_dir):
  with open(os.path.join(build_dir, 'VERSION'), 'r') as r:
    return r.read()


def main():
  args = parse_args()
  build_dir = os.path.dirname(__file__)
  version = read_version(build_dir)
  # Note: Go does not support using absolute package names.
  # So we run go inside the directory of the the build file.
  sys.exit(subprocess.call(calc_go_args(args, version), cwd=build_dir))


if __name__ == '__main__':
  main()
