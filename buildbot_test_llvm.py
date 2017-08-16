#!/usr/bin/env python2
#
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Script for running llvm validation tests on ChromeOS.

This script launches a buildbot to build ChromeOS with the llvm on
a particular board; then it finds and downloads the trybot image and the
corresponding official image, and runs test for correctness.
It then generates a report, emails it to the c-compiler-chrome, as
well as copying the result into a directory.
"""

# Script to test different toolchains against ChromeOS benchmarks.

from __future__ import print_function

import argparse
import datetime
import os
import sys
import time

from cros_utils import command_executer
from cros_utils import logger

from cros_utils import buildbot_utils

CROSTC_ROOT = '/usr/local/google/crostc'
ROLE_ACCOUNT = 'mobiletc-prebuild'
TOOLCHAIN_DIR = os.path.dirname(os.path.realpath(__file__))
MAIL_PROGRAM = '~/var/bin/mail-sheriff'
VALIDATION_RESULT_DIR = os.path.join(CROSTC_ROOT, 'validation_result')
START_DATE = datetime.date(2016, 1, 1)
TEST_PER_DAY = 3

# Information about Rotating Boards
#  Board       Arch    Reference  Platform     Kernel
#                      Board                   Version
#  --------   ------   ---------  ----------   -------
#  caroline   x86_64   glados     skylake-y     3.18
#  daisy      armv7    daisy      exynos-5250   3.8.11
#  eve        x86_64   poppy      kabylake-y    4.4.79
#  gale       armv7                             3.18
#  kevin      armv7    gru        rockchip-3399 4.4.79
#  lakitu     x86_64                            4.4.79
#  link       x86_64   ivybridge  ivybridge     3.8.11
#  lumpy      x86_64   --         sandybridge   3.8.11
#  nyan_big   armv7    nyan       tegra         3.10.18
#  peach_pit  armv7    peach      exynos-5420   3.8.11
#  peppy      x86_64   slippy     haswell       3.8.11
#  reef       x86_64   reef       apollo lake   4.4.79
#  sentry     x86_64   kunimitsu  skylake-u     3.18
#  squawks    x86_64   rambi      baytrail      4.4.79
#  terra      x86_64   strago     braswell      3.18
#  whirlwind  armv7                             3.14

TEST_BOARD = [
    'caroline',
    'daisy',
    'eve',
    'gale',
    'kevin',
    'lakitu',
    'link',
    'lumpy',
    'nyan_big',
    'peach_pit',
    'peppy',
    'reef',
    'sentry',
    'squawks',
    'terra',
    'whirlwind',
]


class ToolchainVerifier(object):
  """Class for the toolchain verifier."""

  def __init__(self, board, chromeos_root, weekday, patches, compiler):
    self._board = board
    self._chromeos_root = chromeos_root
    self._base_dir = os.getcwd()
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()
    self._compiler = compiler
    self._build = '%s-%s-toolchain' % (board, compiler)
    self._patches = patches.split(',') if patches else []
    self._patches_string = '_'.join(str(p) for p in self._patches)

    if not weekday:
      self._weekday = time.strftime('%a')
    else:
      self._weekday = weekday
    self._reports = os.path.join(VALIDATION_RESULT_DIR, compiler, board)

  def _FinishSetup(self):
    """Make sure testing_rsa file is properly set up."""
    # Fix protections on ssh key
    command = ('chmod 600 /var/cache/chromeos-cache/distfiles/target'
               '/chrome-src-internal/src/third_party/chromite/ssh_keys'
               '/testing_rsa')
    ret_val = self._ce.ChrootRunCommand(self._chromeos_root, command)
    if ret_val != 0:
      raise RuntimeError('chmod for testing_rsa failed')

  def DoAll(self):
    """Main function inside ToolchainComparator class.

    Launch trybot, get image names, create crosperf experiment file, run
    crosperf, and copy images into seven-day report directories.
    """
    date_str = datetime.date.today()
    description = 'master_%s_%s_%s' % (self._patches_string, self._build,
                                       date_str)
    _ = buildbot_utils.GetTrybotImage(
        self._chromeos_root,
        self._build,
        self._patches,
        description,
        tryjob_flags=['--hwtest'],
        async=True)

    return 0


def Main(argv):
  """The main function."""

  # Common initializations
  command_executer.InitCommandExecuter()
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--chromeos_root',
      dest='chromeos_root',
      help='The chromeos root from which to run tests.')
  parser.add_argument(
      '--weekday',
      default='',
      dest='weekday',
      help='The day of the week for which to run tests.')
  parser.add_argument(
      '--board', default='', dest='board', help='The board to test.')
  parser.add_argument(
      '--patch',
      dest='patches',
      default='',
      help='The patches to use for the testing, '
      "seprate the patch numbers with ',' "
      'for more than one patches.')
  parser.add_argument(
      '--compiler',
      dest='compiler',
      help='Which compiler (llvm, llvm-next or gcc) to use for '
      'testing.')

  options = parser.parse_args(argv[1:])
  if not options.chromeos_root:
    print('Please specify the ChromeOS root directory.')
    return 1
  if not options.compiler:
    print('Please specify which compiler to test (gcc, llvm, or llvm-next).')
    return 1

  if options.board:
    fv = ToolchainVerifier(options.board, options.chromeos_root,
                           options.weekday, options.patches, options.compiler)
    return fv.Doall()

  today = datetime.date.today()
  delta = today - START_DATE
  days = delta.days

  start_board = (days * TEST_PER_DAY) % len(TEST_BOARD)
  for i in range(TEST_PER_DAY):
    try:
      board = TEST_BOARD[(start_board + i) % len(TEST_BOARD)]
      fv = ToolchainVerifier(board, options.chromeos_root, options.weekday,
                             options.patches, options.compiler)
      fv.DoAll()
    except SystemExit:
      logfile = os.path.join(VALIDATION_RESULT_DIR, options.compiler, board)
      with open(logfile, 'w') as f:
        f.write('Verifier got an exception, please check the log.\n')


if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
