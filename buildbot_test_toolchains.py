#!/usr/bin/python2
"""Script for running nightly compiler tests on ChromeOS.

This script launches a buildbot to build ChromeOS with the latest compiler on
a particular board; then it finds and downloads the trybot image and the
corresponding official image, and runs crosperf performance tests comparing
the two.  It then generates a report, emails it to the c-compiler-chrome, as
well as copying the images into the seven-day reports directory.
"""

# Script to test different toolchains against ChromeOS benchmarks.

from __future__ import print_function

import datetime
import optparse
import os
import sys
import time

from utils import command_executer
from utils import logger

from utils import buildbot_utils

# CL that updated GCC ebuilds to use 'next_gcc'.
USE_NEXT_GCC_PATCH = '230260'

# CL that uses LLVM to build the peppy image.
USE_LLVM_PATCH = '295217'

# The boards on which we run weekly reports
WEEKLY_REPORT_BOARDS = ['lumpy']

CROSTC_ROOT = '/usr/local/google/crostc'
ROLE_ACCOUNT = 'mobiletc-prebuild'
TOOLCHAIN_DIR = os.path.dirname(os.path.realpath(__file__))
MAIL_PROGRAM = '~/var/bin/mail-sheriff'
WEEKLY_REPORTS_ROOT = os.path.join(CROSTC_ROOT, 'weekly_test_data')
PENDING_ARCHIVES_DIR = os.path.join(CROSTC_ROOT, 'pending_archives')
NIGHTLY_TESTS_DIR = os.path.join(CROSTC_ROOT, 'nightly_test_reports')


class ToolchainComparator(object):
  """Class for doing the nightly tests work."""

  def __init__(self,
               board,
               remotes,
               chromeos_root,
               weekday,
               patches,
               noschedv2=False):
    self._board = board
    self._remotes = remotes
    self._chromeos_root = chromeos_root
    self._base_dir = os.getcwd()
    self._ce = command_executer.GetCommandExecuter()
    self._l = logger.GetLogger()
    self._build = '%s-release' % board
    self._patches = patches.split(',')
    self._patches_string = '_'.join(str(p) for p in self._patches)
    self._noschedv2 = noschedv2

    if not weekday:
      self._weekday = time.strftime('%a')
    else:
      self._weekday = weekday
    timestamp = datetime.datetime.strftime(datetime.datetime.now(),
                                           '%Y-%m-%d_%H:%M:%S')
    self._reports_dir = os.path.join(NIGHTLY_TESTS_DIR,
                                     '%s.%s' % (timestamp, board),)

  def _ParseVanillaImage(self, trybot_image):
    """Parse a trybot artifact name to get corresponding vanilla image.

    This function takes an artifact name, such as
    'trybot-daisy-release/R40-6394.0.0-b1389', and returns the
    corresponding official build name, e.g. 'daisy-release/R40-6394.0.0'.
    """
    start_pos = trybot_image.find(self._build)
    end_pos = trybot_image.rfind('-b')
    vanilla_image = trybot_image[start_pos:end_pos]
    return vanilla_image

  def _FinishSetup(self):
    """Make sure testing_rsa file is properly set up."""
    # Fix protections on ssh key
    command = ('chmod 600 /var/cache/chromeos-cache/distfiles/target'
               '/chrome-src-internal/src/third_party/chromite/ssh_keys'
               '/testing_rsa')
    ret_val = self._ce.ChrootRunCommand(self._chromeos_root, command)
    if ret_val != 0:
      raise RuntimeError('chmod for testing_rsa failed')

  def _TestImages(self, trybot_image, vanilla_image):
    """Create crosperf experiment file.

    Given the names of the trybot and vanilla images, create the
    appropriate crosperf experiment file and launch crosperf on it.
    """
    experiment_file_dir = os.path.join(self._chromeos_root, '..', self._weekday)
    experiment_file_name = '%s_toolchain_experiment.txt' % self._board

    compiler_string = 'gcc'
    if USE_LLVM_PATCH in self._patches_string:
      experiment_file_name = '%s_llvm_experiment.txt' % self._board
      compiler_string = 'llvm'

    experiment_file = os.path.join(experiment_file_dir, experiment_file_name)
    experiment_header = """
    board: %s
    remote: %s
    retries: 1
    """ % (self._board, self._remotes)
    experiment_tests = """
    benchmark: all_toolchain_perf {
      suite: telemetry_Crosperf
      iterations: 3
    }
    """

    with open(experiment_file, 'w') as f:
      f.write(experiment_header)
      f.write(experiment_tests)

      # Now add vanilla to test file.
      official_image = """
          vanilla_image {
            chromeos_root: %s
            build: %s
            compiler: gcc
          }
          """ % (self._chromeos_root, vanilla_image)
      f.write(official_image)

      label_string = '%s_trybot_image' % compiler_string
      if USE_NEXT_GCC_PATCH in self._patches:
        label_string = 'gcc_next_trybot_image'

      experiment_image = """
          %s {
            chromeos_root: %s
            build: %s
            compiler: %s
          }
          """ % (label_string, self._chromeos_root, trybot_image,
                 compiler_string)
      f.write(experiment_image)

    crosperf = os.path.join(TOOLCHAIN_DIR, 'crosperf', 'crosperf')
    noschedv2_opts = '--noschedv2' if self._noschedv2 else ''
    command = ('{crosperf} --no_email=True --results_dir={r_dir} '
               '--json_report=True {noschedv2_opts} {exp_file}').format(
                   crosperf=crosperf,
                   r_dir=self._reports_dir,
                   noschedv2_opts=noschedv2_opts,
                   exp_file=experiment_file)

    ret = self._ce.RunCommand(command)
    if ret != 0:
      raise RuntimeError("Couldn't run crosperf!")
    else:
      # Copy json report to pending archives directory.
      command = 'cp %s/*.json %s/.' % (self._reports_dir, PENDING_ARCHIVES_DIR)
      ret = self._ce.RunCommand(command)
    return

  def _CopyWeeklyReportFiles(self, trybot_image, vanilla_image):
    """Put files in place for running seven-day reports.

    Create tar files of the custom and official images and copy them
    to the weekly reports directory, so they exist when the weekly report
    gets generated.  IMPORTANT NOTE: This function must run *after*
    crosperf has been run; otherwise the vanilla images will not be there.
    """

    dry_run = False
    if os.getlogin() != ROLE_ACCOUNT:
      self._l.LogOutput('Running this from non-role account; not copying '
                        'tar files for weekly reports.')
      dry_run = True

    images_path = os.path.join(
        os.path.realpath(self._chromeos_root), 'chroot/tmp')

    data_dir = os.path.join(WEEKLY_REPORTS_ROOT, self._board)
    dest_dir = os.path.join(data_dir, self._weekday)
    if not os.path.exists(dest_dir):
      os.makedirs(dest_dir)

    # Make sure dest_dir is empty (clean out last week's data).
    cmd = 'cd %s; rm -Rf %s_*_image*' % (dest_dir, self._weekday)
    if dry_run:
      print('CMD: %s' % cmd)
    else:
      self._ce.RunCommand(cmd)

    # Now create new tar files and copy them over.
    labels = ['test', 'vanilla']
    for label_name in labels:
      if label_name == 'test':
        test_path = trybot_image
      else:
        test_path = vanilla_image
      tar_file_name = '%s_%s_image.tar' % (self._weekday, label_name)
      cmd = ('cd %s; tar -cvf %s %s/chromiumos_test_image.bin; '
             'cp %s %s/.') % (images_path, tar_file_name, test_path,
                              tar_file_name, dest_dir)
      if dry_run:
        print('CMD: %s' % cmd)
        tar_ret = 0
      else:
        tar_ret = self._ce.RunCommand(cmd)
      if tar_ret:
        self._l.LogOutput('Error while creating/copying test tar file(%s).' %
                          tar_file_name)

  def _SendEmail(self):
    """Find email message generated by crosperf and send it."""
    filename = os.path.join(self._reports_dir, 'msg_body.html')
    if (os.path.exists(filename) and
        os.path.exists(os.path.expanduser(MAIL_PROGRAM))):
      email_title = 'buildbot test results'
      if self._patches_string == USE_LLVM_PATCH:
        email_title = 'buildbot llvm test results'
      command = ('cat %s | %s -s "%s, %s" -team -html' %
                 (filename, MAIL_PROGRAM, email_title, self._board))
      self._ce.RunCommand(command)

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

    vanilla_image = self._ParseVanillaImage(trybot_image)

    print('trybot_image: %s' % trybot_image)
    print('vanilla_image: %s' % vanilla_image)
    if len(trybot_image) == 0:
      self._l.LogError('Unable to find trybot_image for %s!' % description)
      return 1
    if len(vanilla_image) == 0:
      self._l.LogError('Unable to find vanilla image for %s!' % description)
      return 1
    if os.getlogin() == ROLE_ACCOUNT:
      self._FinishSetup()

    self._TestImages(trybot_image, vanilla_image)
    self._SendEmail()
    if (self._patches_string == USE_NEXT_GCC_PATCH and
        self._board in WEEKLY_REPORT_BOARDS):
      # Only try to copy the image files if the test runs ran successfully.
      self._CopyWeeklyReportFiles(trybot_image, vanilla_image)
    return 0


def Main(argv):
  """The main function."""

  # Common initializations
  command_executer.InitCommandExecuter()
  parser = optparse.OptionParser()
  parser.add_option('--remote',
                    dest='remote',
                    help='Remote machines to run tests on.')
  parser.add_option('--board',
                    dest='board',
                    default='x86-zgb',
                    help='The target board.')
  parser.add_option('--chromeos_root',
                    dest='chromeos_root',
                    help='The chromeos root from which to run tests.')
  parser.add_option('--weekday',
                    default='',
                    dest='weekday',
                    help='The day of the week for which to run tests.')
  parser.add_option('--patch',
                    dest='patches',
                    help='The patches to use for the testing, '
                    "seprate the patch numbers with ',' "
                    'for more than one patches.')
  parser.add_option('--noschedv2',
                    dest='noschedv2',
                    action='store_true',
                    default=False,
                    help='Pass --noschedv2 to crosperf.')

  options, _ = parser.parse_args(argv)
  if not options.board:
    print('Please give a board.')
    return 1
  if not options.remote:
    print('Please give at least one remote machine.')
    return 1
  if not options.chromeos_root:
    print('Please specify the ChromeOS root directory.')
    return 1
  if options.patches:
    patches = options.patches
  else:
    patches = USE_NEXT_GCC_PATCH

  fc = ToolchainComparator(options.board, options.remote, options.chromeos_root,
                           options.weekday, patches, options.noschedv2)
  return fc.DoAll()


if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
