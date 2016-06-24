#!/usr/bin/python2
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

from utils import command_executer
from utils import logger

from utils import buildbot_utils

# CL that uses LLVM to build the peppy image.
USE_LLVM_PATCH = '295217'


CROSTC_ROOT = '/usr/local/google/crostc'
ROLE_ACCOUNT = 'mobiletc-prebuild'
TOOLCHAIN_DIR = os.path.dirname(os.path.realpath(__file__))
MAIL_PROGRAM = '~/var/bin/mail-sheriff'
VALIDATION_RESULT_DIR = os.path.join(CROSTC_ROOT, 'validation_result')
START_DATE = datetime.date(2016, 1, 1)
TEST_PER_DAY = 2
TEST_BOARD = [
    'squawks',
    'terra',
    'lulu',
    'peach_pit',
    'falco',
    'oak',
    'veyron_jaq',
    'lumpy',
    'sentry',
    'chell',
    'nyan_big',
    ]

TEST = [
    'bvt-inline',
    'bvt-cq',
    'paygen_au_canary',
    'security',
    #'kernel_per-build_regression',
    #'kernel_per-build_benchmarks',
    'kernal_daily_regression',
    'kernel_daily_benchmarks',
    #'stress',
    ]

class ToolchainVerifier(object):
  """Class for the toolchain verifier."""

  def __init__(self,
               board,
               chromeos_root,
               weekday,
               patches,
               compiler):
    self._board = board
    self._chromeos_root = chromeos_root
    self._base_dir = os.getcwd()
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()
    self._compiler = compiler
    self._build = '%s-release' % board
    self._patches = patches.split(',')
    self._patches_string = '_'.join(str(p) for p in self._patches)

    if not weekday:
      self._weekday = time.strftime('%a')
    else:
      self._weekday = weekday
    self._reports = os.path.join(VALIDATION_RESULT_DIR, board)

  def _FinishSetup(self):
    """Make sure testing_rsa file is properly set up."""
    # Fix protections on ssh key
    command = ('chmod 600 /var/cache/chromeos-cache/distfiles/target'
               '/chrome-src-internal/src/third_party/chromite/ssh_keys'
               '/testing_rsa')
    ret_val = self._ce.ChrootRunCommand(self._chromeos_root, command)
    if ret_val != 0:
      raise RuntimeError('chmod for testing_rsa failed')

  def _TestImages(self, image):
    to_file = ''
    for test in TEST:
      command = ('test_that --board {board} :lab: suite:{test} '
                 '-i {image} --fast --autotest_dir '
                 '~/trunk/src/third_party/autotest/files '
                 '--web  cautotest.corp.google.com'.format(
                     board=self._board,
                     test=test,
                     image=image))
      ret_val = self._ce.ChrootRunCommand(self._chromeos_root, command)
      timestamp = datetime.datetime.strftime(datetime.datetime.now(),
                                             '%Y-%m-%d_%H:%M:%S')
      if ret_val:
        out = 'FAILED'
      else:
        out = '      '
      to_file += out + ' ' + test + ' ' + timestamp + '\n'
      with open(self._reports, 'w') as f:
        f.write(to_file)

  def DoAll(self):
    """Main function inside ToolchainComparator class.

    Launch trybot, get image names, create crosperf experiment file, run
    crosperf, and copy images into seven-day report directories.
    """
    date_str = datetime.date.today()
    description = 'master_%s_%s_%s' % (self._patches_string, self._build,
                                       date_str)
    trybot_image = buildbot_utils.GetTrybotImage(self._chromeos_root,
                                                 self._build,
                                                 self._patches,
                                                 description,
                                                 build_toolchain=True)
    if len(trybot_image) == 0:
      self._l.LogError('Unable to find trybot_image for %s!' % description)
      return 1

    if os.getlogin() == ROLE_ACCOUNT:
      self._FinishSetup()

    self._TestImages(trybot_image)
    return 0

def SendEmail(start_board, compiler):
  """Send out the test results for all the boards."""
  results = ""
  for i in range(len(TEST_BOARD)):
    board = TEST_BOARD[(start_board + i) % len(TEST_BOARD)]
    f = os.path.join(VALIDATION_RESULT_DIR, board)
    if not os.path.exists(f):
      continue
    results += board
    results += '\n'
    file_name = os.path.join(VALIDATION_RESULT_DIR, f)
    with open(file_name, 'r') as readin:
      read_data = readin.read()
      results += read_data

  output = os.path.join(VALIDATION_RESULT_DIR, "result")
  with open(output, 'w') as out:
    out.write(results)

  ce = command_executer.GetCommandExecuter()
  if os.path.exists(os.path.expanduser(MAIL_PROGRAM)):
    email_title = '%s validation test results' % compiler
    command = ('cat %s | %s -s "%s" -team' %
               (output, MAIL_PROGRAM, email_title))
    ce.RunCommand(command)


def Main(argv):
  """The main function."""

  # Common initializations
  command_executer.InitCommandExecuter()
  parser = argparse.ArgumentParser()
  parser.add_argument('--chromeos_root',
                      dest='chromeos_root',
                      help='The chromeos root from which to run tests.')
  parser.add_argument('--weekday',
                      default='',
                      dest='weekday',
                      help='The day of the week for which to run tests.')
  parser.add_argument('--board',
                      default='',
                      dest='board',
                      help='The board to test.')
  parser.add_argument('--patch',
                      dest='patches',
                      help='The patches to use for the testing, '
                      "seprate the patch numbers with ',' "
                      'for more than one patches.')
  parser.add_argument('--compiler',
                      dest='compiler',
                      help='Which compiler (llvm or gcc) to use for '
                      'testing.')

  options = parser.parse_args(argv[1:])
  if not options.chromeos_root:
    print('Please specify the ChromeOS root directory.')
    return 1
  if not options.compiler:
    print('Please specify which compiler to test (gcc or llvm).')
    return 1
  if options.patches:
    patches = options.patches
  elif options.compiler == 'llvm':
    patches = USE_LLVM_PATCH

  if options.board:
    fv = ToolchainVerifier(options.board, options.chromeos_root,
                           options.weekday, patches, options.compiler)
    return fv.Doall()

  today = datetime.date.today()
  delta = today - START_DATE
  days = delta.days

  start_board = (days * TEST_PER_DAY) % len(TEST_BOARD)
  for i in range(TEST_PER_DAY):
    try:
      board = TEST_BOARD[(start_board + i)  % len(TEST_BOARD)]
      fv = ToolchainVerifier(board, options.chromeos_root,
                             options.weekday, patches, options.compiler)
      fv.DoAll()
    except SystemExit:
      logfile = os.path.join(VALIDATION_RESULT_DIR, board)
      with open(logfile, 'w') as f:
        f.write("Verifier got an exception, please check the log.\n")

  SendEmail(start_board, options.compiler)

if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
