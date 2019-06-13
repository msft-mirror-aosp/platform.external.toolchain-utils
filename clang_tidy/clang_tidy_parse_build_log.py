#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse log files containing clang-tidy warnings, and generate reports."""

from __future__ import print_function

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import re


def Main(argv):
  parser = argparse.ArgumentParser()

  parser.add_argument(
      '--output_dir',
      dest='out_dir',
      default='',
      help='Directory in which to write the resulting html & csv file.')
  parser.add_argument(
      '--log_file',
      dest='log_file',
      default=None,
      required=True,
      help='File containing the clang-tidy warnings to be parsed.')

  options = parser.parse_args(argv)

  output_dir = options.out_dir if options.out_dir else '/tmp/clang-tidy-output'

  cwd = os.path.dirname(os.path.realpath(__file__))
  warn_script = os.path.join(cwd, 'clang_tidy_warn.py')

  logfile = options.log_file
  if not os.path.exists(logfile):
    parser.error('Cannot find log file "%s"' % logfile)

  if not os.path.exists(warn_script):
    parser.error('Cannot find %s' % warn_script)

  # Normally, ChromeOS build logs have a filename format like:
  # 'chromeos-base:chromeos-chrome-version_rc-r1:date-time.log'.
  # Below we parse this to find the chrome version and date.  We
  # use these to create the warnings file names:
  # 'chrome-warning-{date}-R{version}.html' and
  # 'chrome-warning-{date}-R{version}.proto'.
  # If filename does not conform to ChromeOS build log format, use full
  # filename rather than the version name.

  dirname, filename = os.path.split(logfile)
  datestamp = ''
  version = filename
  pattern = r'chromeos-base:chromeos-chrome-(.*)_rc-r\d+:([^-]*)-.*'
  match = re.match(pattern, filename)
  if match:
    version, datestamp = match.groups()

  if not datestamp:
    # Get a string with the current date, in the format 'YYYYMMDD'.
    datestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d')

  new_filename = 'chrome-warning-%s-R%s' % (datestamp, version)
  html_filename = new_filename + '.html'
  proto_filename = new_filename + '.proto'

  # If the user did not specify a particular output directory and the logs
  # appear to be in the default input directory, which contains the board name,
  # extract the board name from the input directory and add it to the default
  # output directory name.
  if not options.out_dir:
    dirname_bits = dirname.split('/')
    if dirname[0] == '/' and dirname_bits[0] == '':
      dirname_bits = dirname_bits[1:]
    if (len(dirname_bits) == 3 and dirname_bits[0] == 'tmp' and
        dirname_bits[1] == 'clang-tidy-logs'):
      board = dirname_bits[2]
      output_dir = os.path.join(output_dir, board)

  # Create the output directory if it does not already exist.
  if not os.path.exists(output_dir):
    os.makedirs(output_dir)

  warnfile_html = os.path.join(output_dir, html_filename)
  warnfile_proto = os.path.join(output_dir, proto_filename)

  run_warn_py = [
      'python',
      warn_script,
      logfile,
      '--protopath',
      warnfile_proto,
      '--separator',
      '?l=',
  ]

  try:
    with open('/dev/null') as stdin, open(warnfile_html, 'w') as stdout:
      subprocess.check_call(run_warn_py, stdin=stdin, stdout=stdout)
  except subprocess.CalledProcessError:
    print("Couldn't generate warnings.html", file=sys.stderr)
    shutil.rmtree(warnfile_html, ignore_errors=True)
    shutil.rmtree(warnfile_proto, ignore_errors=True)
    return 1

  return 0


if __name__ == "__main__":
  sys.exit(Main(sys.argv[1:]))
