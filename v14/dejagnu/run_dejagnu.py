#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Tool script for auto dejagnu."""

__author__ = 'shenhan@google.com (Han Shen)'

import optparse
import os
from os import path
import re
import shutil
import stat
import sys
import tempfile

from utils import command_executer
from utils import misc


def ProcessArguments():
  """Processing/validating script arguments."""
  parser = optparse.OptionParser(description=(
      'Launches gcc dejagnu test in chroot for chromeos toolchain, compares '
      'the test result with a repository baseline and prints out the result.'),
                                 usage='run_dejagnu options')
  parser.add_option('-c', '--chromeos_root', dest='chromeos_root',
                    help='Required. Specify chromeos root')
  parser.add_option('-a', '--auto', dest='auto_mode', action='store_true',
                    default=True, help=(
                        'Default. Test using auto mode - '
                        'gcc are checked out/built automatically.'))
  parser.add_option('-b', '--board', dest='board',
                    help=('Required. Specify board. Currently only support '
                          '\'x86-zgb\' and \'tegra2_kaen\''))
  parser.add_option('-r', '--remote', dest='remote',
                    help='Required. Specify remote address/name of the board.')
  parser.add_option('-f', '--flags', dest='flags',
                    help='Optional. Extra run test flags to pass to dejagnu.')
  options, args = parser.parse_args()

  if not options.chromeos_root:
    sys.exit('Missing argument for --chromeos_root.')
  if not options.remote:
    sys.exit('Missing argument for --remote.')
  if not options.board:
    sys.exit('Missing argument for --board.')
  if args:
    print 'Warning - discarding useless arguments %s...' % args

  return options


class DejagnuExecuter(object):
  """The class wrapper for dejagnu test executer."""

  def __init__(self, chromeos_root, remote, board, flags):
    self._chromeos_root = chromeos_root
    self._remote = remote
    self._board = board
    ## Compute target from board
    self._target = misc.GetCtargetFromBoard(board, chromeos_root)
    if not self._target:
      sys.exit('Unsupported board "%s"' % board)
    self._executer = command_executer.GetCommandExecuter()
    self._flags = flags or ''
    self._base_dir = misc.GetRoot(sys.argv[0])[0]
    self._tmp_abs = None

  def SetupTestingDir(self):
    self._tmp_abs = tempfile.mkdtemp(prefix='dejagnu_', dir=path.join(
        self._chromeos_root, 'chroot', 'tmp'))
    self._tmp = self._tmp_abs[len(path.join(self._chromeos_root, 'chroot')):]
    self._tmp_testing_rsa = path.join(self._tmp, 'testing_rsa')
    self._tmp_testing_rsa_abs = path.join(self._tmp_abs, 'testing_rsa')

  def CleanupTestingDir(self):
    if self._tmp_abs:
      shutil.rmtree(self._tmp_abs)

  def PrepareTestingRsaKeys(self):
    if not path.isfile(self._tmp_testing_rsa_abs):
      shutil.copy(path.join(
          self._chromeos_root,
          'src/scripts/mod_for_test_scripts/ssh_keys/testing_rsa'),
                  self._tmp_testing_rsa_abs)
      os.chmod(self._tmp_testing_rsa_abs, stat.S_IRUSR)

  def PrepareTestFiles(self):
    """Prepare site.exp and board exp files."""
    # Create the boards directory.
    os.mkdir('%s/boards' % self._tmp_abs)

    # Generate the chromeos.exp file.
    with open('%s/chromeos.exp.in' % self._base_dir, 'r') as template_file:
      content = template_file.read()
    substitutions = dict({
        '__boardname__': self._board,
        '__board_hostname__': self._remote,
        '__tmp_testing_rsa__': self._tmp_testing_rsa,
        '__tmp_dir__': self._tmp})
    for pat, sub in substitutions.items():
      content = content.replace(pat, sub)

    board_file_name = '%s/boards/%s.exp' % (self._tmp_abs, self._board)
    with open(board_file_name, 'w') as board_file:
      board_file.write(content)

    # Generate the site file
    with open('%s/site.exp' % self._tmp_abs, 'w') as site_file:
      site_file.write('set target_list "%s"\n' % self._board)

  def PrepareGcc(self):
    """Auto emerging gcc for building purpose only."""
    ret = self._executer.ChrootRunCommand(
        self._chromeos_root,
        'equery w cross-%s/gcc' % self._target, return_output=True)[1]
    ret = path.basename(ret.rstrip('\r\n'))
    # ret is expected to be something like 'gcc-4.6.2-r11.ebuild', parse it.
    matcher = re.match('((.*)-r\d+).ebuild', ret)
    if not matcher:
      sys.exit('Failed to get gcc version.')
    gccrevision, gccversion = matcher.group(1, 2)

    gcc_portage_dir = '/var/tmp/portage/cross-%s/%s/work' % (
        self._target, gccrevision)
    self._gcc_source_dir = path.join(gcc_portage_dir, gccversion)
    self._gcc_top_build_dir = (gcc_portage_dir + '/%s-build-%s') % (
        gccversion, self._target)
    self._gcc_build_dir = path.join(self._gcc_top_build_dir, 'gcc')
    gcc_build_dir_abs = path.join(
        self._chromeos_root, 'chroot', self._gcc_build_dir.lstrip('/'))
    if not path.isdir(gcc_build_dir_abs):
      self._executer.ChrootRunCommand(
          self._chromeos_root,
          ('ebuild $(equery w cross-%s/gcc) clean prepare compile' % (
              self._target)))
    print 'gcc source dir is - "%s"' % self._gcc_source_dir
    print 'gcc top build dir is - "%s"' % self._gcc_top_build_dir
    print ('gcc build dir absolute (not inside chroot) is - "%s"' %
           gcc_build_dir_abs)

  def MakeCheck(self):
    cmd = ('cd %s ; '
           'DEJAGNU=%s make check RUNTESTFLAGS="--target_board=%s %s"' %
           (self._gcc_build_dir, path.join(self._tmp, 'site.exp'),
            self._board, self._flags))
    self._executer.ChrootRunCommand(self._chromeos_root, cmd)

  def ValidateFailures(self):
    validate_failures_py = path.join(
        self._gcc_source_dir,
        'contrib/testsuite-management/validate_failures.py')
    cmd = 'cd {0} ; {1} --build_dir={0}'.format(
        self._gcc_top_build_dir, validate_failures_py)
    ret = self._executer.ChrootRunCommand(self._chromeos_root, cmd)
    if ret != 0:
      print ('*** validate_failures.py exited with non-zero code,'
             'please run it manually inside chroot - ')
      print '   ' + cmd


if __name__ == '__main__':
  opts = ProcessArguments()
  executer = DejagnuExecuter(opts.chromeos_root, opts.remote,
                             opts.board, opts.flags)
  try:
    executer.SetupTestingDir()
    executer.PrepareTestingRsaKeys()
    executer.PrepareTestFiles()
    executer.PrepareGcc()
    executer.MakeCheck()
    executer.ValidateFailures()
  finally:
    executer.CleanupTestingDir()
