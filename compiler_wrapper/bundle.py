#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build script that copies the go sources to a build destination."""

from __future__ import print_function

import argparse
import os.path
import re
import shutil
import subprocess
import sys


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('output_dir')
  return parser.parse_args()


def copy_files(input_dir, output_dir):
  for filename in os.listdir(input_dir):
    if ((filename.endswith('.go') and not filename.endswith('_test.go')) or
        filename == 'build.py'):
      shutil.copy(
          os.path.join(input_dir, filename), os.path.join(output_dir, filename))


def read_change_id(input_dir):
  last_commit_msg = subprocess.check_output(
      ['git', '-C', input_dir, 'log', '-1', '--pretty=%B'])
  match = re.search('Change-Id: (\\w+)', last_commit_msg)
  if not match:
    sys.exit("Couldn't find Change-Id in last commit message.")
  return match.group(1)


def write_readme(input_dir, output_dir, change_id):
  with open(os.path.join(input_dir, 'bundle.README'), 'r') as r, \
       open(os.path.join(output_dir, 'README'), 'w') as w:
    content = r.read()
    w.write(content.format(change_id=change_id))


def write_version(output_dir, change_id):
  with open(os.path.join(output_dir, 'VERSION'), 'w') as w:
    w.write(change_id)


def main():
  args = parse_args()
  input_dir = os.path.dirname(__file__)
  change_id = read_change_id(input_dir)
  shutil.rmtree(args.output_dir, ignore_errors=True)
  os.makedirs(args.output_dir)
  copy_files(input_dir, args.output_dir)
  write_readme(input_dir, args.output_dir, change_id)
  write_version(args.output_dir, change_id)


if __name__ == '__main__':
  main()
