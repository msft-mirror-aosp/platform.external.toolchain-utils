#!/usr/bin/python

"""A crontab script to delete night test data."""
__author__ = 'shenhan@google.com (Han Shen)'

import datetime
import optparse
import os
import re
import sys

from utils import command_executer
from utils import constants
from utils import misc

DIR_BY_WEEKDAY = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def CleanNumberedDir(s, dry_run=False):
  """Deleted directories under each dated_dir."""
  chromeos_dirs = [os.path.join(s, x) for x in os.listdir(s)
                   if misc.IsChromeOsTree(os.path.join(s, x))]
  ce = command_executer.GetCommandExecuter(log_level="none")
  all_succeeded = True
  for cd in chromeos_dirs:
    if misc.DeleteChromeOsTree(cd, dry_run=dry_run):
      print 'Successfully removed chromeos tree "{0}".'.format(cd)
    else:
      all_succeeded = False
      print 'Failed to remove chromeos tree "{0}", please check.'.format(cd)

  if not all_succeeded:
    print 'Failed to delete at least one chromeos tree, please check.'
    return False

  ## Now delete the numbered dir Before forcibly removing the directory, just
  ## check 's' to make sure it is sane.  A valid dir to be removed must be
  ## '/usr/local/google/crostc/(SUN|MON|TUE...|SAT)'.
  valid_dir_pattern = ('^' + constants.CROSTC_WORKSPACE + '/(' +
                       '|'.join(DIR_BY_WEEKDAY) + ')')
  if not re.search(valid_dir_pattern, s):
    print ('Trying to delete an invalid dir "{0}" (must match "{1}"), '
           'please check.'.format(s, valid_dir_pattern))
    return False

  cmd = 'rm -fr {0}'.format(s)
  if dry_run:
    print cmd
  else:
    if ce.RunCommand(cmd, return_output=False, print_to_console=True,
                     terminated_timeout=480) == 0:
      print 'Successfully removed "{0}".'.format(s)
    else:
      all_succeeded = False
      print 'Failed to remove "{0}", please check.'.format(s)
  return all_succeeded


def CleanDatedDir(dated_dir, dry_run=False):
  # List subdirs under dir
  subdirs = [os.path.join(dated_dir, x) for x in os.listdir(dated_dir)
             if os.path.isdir(os.path.join(dated_dir, x))]
  all_succeeded = True
  for s in subdirs:
    if not CleanNumberedDir(s, dry_run):
      all_succeeded = False
  return all_succeeded


def ProcessArguments(argv):
  """Process arguments."""
  parser = optparse.OptionParser(
      description='Automatically delete nightly test data directories.',
      usage='auto_delete_nightly_test_data.py options')
  parser.add_option('-d', '--dry_run', dest='dry_run',
                    default=False, action='store_true',
                    help='Only print command line, do not execute anything.')
  parser.add_option('--days_to_preserve', dest='days_to_preserve', default=3,
                    help=('Specify the number of days (not including today), '
                          'test data generated on these days will *NOT* be '
                          'deleted. Defaults to 3.'))
  options, _ = parser.parse_args(argv)
  return options


def CleanChromeOsTmpAndImages():
  """Delete temporaries, images under crostc/chromeos."""

  chromeos_chroot_tmp = os.path.join(constants.CROSTC_WORKSPACE,
                                     'chromeos', 'chroot', 'tmp')

  ce = command_executer.GetCommandExecuter()
  # Clean chroot/tmp/test_that_* and chroot/tmp/tmpxxxxxx, that were last
  # accessed more than 24 hours ago.
  cmd = (r'find {0} -maxdepth 1 -type d '
         r'\( -name "test_that_*" -o -regex "{0}/tmp......" \) '
         r'-amin +1440 '
         r'-exec bash -c "echo rm -fr {{}}" \; '
         r'-exec bash -c "rm -fr {{}}" \;').format(chromeos_chroot_tmp)
  rv = ce.RunCommand(cmd, return_output=False, print_to_console=True)
  if rv == 0:
    print ('Successfully cleaned  chromeos tree tmp directory '
           '"{0}".'.format(chromeos_chroot_tmp))
  else:
    print ('Some directories are not removed under  chromeos tree '
           'tmp directory -"{0}".'.format(chromeos_chroot_tmp))

  # Clean image tar files, which were last accessed 1 hour ago and clean image
  # bin files that were last accessed more than 24 hours ago.
  cmd = ('find {0}/*-release -type f '
         r'\( -name "chromiumos_test_image.tar"    -amin +60 -o '
         r'   -name "chromiumos_test_image.tar.xz" -amin +60 -o '
         r'   -name "chromiumos_test_image.bin     -amin +1440" \) '
         r'-exec bash -c "echo rm -f {{}}" \; '
         r'-exec bash -c "rm -f {{}}" \;').format(chromeos_chroot_tmp)
  rv2 = ce.RunCommand(cmd, return_output=False, print_to_console=True)
  if rv2 == 0:
    print 'Successfully cleaned  chromeos images.'
  else:
    print 'Some chromeos images are not removed.'

  return rv + rv2


def Main(argv):
  """Delete nightly test data directories, tmps and test images."""
  options = ProcessArguments(argv)
  # Function 'isoweekday' returns 1(Monday) - 7 (Sunday).
  d = datetime.datetime.today().isoweekday()
  # We go back 1 week, delete from that day till we are
  # options.days_to_preserve away from today.
  s = d - 7
  e = d - int(options.days_to_preserve)
  rv = 0
  for i in range(s + 1, e):
    if i <= 0:
      ## Wrap around if index is negative.  6 is from i + 7 - 1, because
      ## DIR_BY_WEEKDAY starts from 0, while isoweekday is from 1-7.
      dated_dir = DIR_BY_WEEKDAY[i+6]
    else:
      dated_dir = DIR_BY_WEEKDAY[i-1]
    rv += 0 if CleanDatedDir(os.path.join(
        constants.CROSTC_WORKSPACE, dated_dir), options.dry_run) else 1

  ## Finally clean temporaries, images under crostc/chromeos
  rv2 = CleanChromeOsTmpAndImages()

  return rv + rv2


if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
