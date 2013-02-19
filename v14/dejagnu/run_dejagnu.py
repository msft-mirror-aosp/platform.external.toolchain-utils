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
from utils import constants
from utils import misc


def ProcessArguments(argv):
  """Processing/validating script arguments."""
  parser = optparse.OptionParser(description=(
      'Launches gcc dejagnu test in chroot for chromeos toolchain, compares '
      'the test result with a repository baseline and prints out the result.'),
                                 usage='run_dejagnu options')
  parser.add_option('-c', '--chromeos_root', dest='chromeos_root',
                    help='Required. Specify chromeos root')
  parser.add_option('-m', '--mount', dest='mount', action='store_true',
                    default=False,
                    help=('Specify testing mode to "mount" instead of "auto"'
                          '. Under "auto" mode, which is the default - gcc is '
                          'checked out and built automatically at default '
                          'directories. Under "mount" mode '
                          '- the gcc_source_dir is set to "$chromeos_'
                          'root/chroot/usr/local/toolchain_root/gcc", the '
                          'gcc-build-dir then is computed as '
                          '"${gcc_source_dir}-build-${ctarget}". In this mode, '
                          'a complete gcc build must be performed in the '
                          'computed gcc-build-dir beforehand.'))
  parser.add_option('-b', '--board', dest='board',
                    help=('Required. Specify board. Currently only support '
                          '\'x86-zgb\' and \'tegra2_kaen\''))
  parser.add_option('-r', '--remote', dest='remote',
                    help='Required. Specify remote address/name of the board.')
  parser.add_option('-f', '--flags', dest='flags',
                    help='Optional. Extra run test flags to pass to dejagnu.')
  parser.add_option('-k', '--keep', dest='keep_intermediate_files',
                    action='store_true', default=False,
                    help=('Optional. Default to false. Do not remove dejagnu '
                          'intermediate files after test run.'))
  parser.add_option('-t', '--tools', dest='tools', default='gcc,g++',
                    help=('Optional. Specify which tools to check, using '
                          '","(comma) as separator. A typical value would be '
                          '"g++" so that only g++ tests are performed.'
                          'Defaults to "gcc,g++".'))

  options, args = parser.parse_args(argv)

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

  def __init__(self, base_dir, mount, chromeos_root, remote, board,
               flags, keep_intermediate_files, tools):
    self._chromeos_root = chromeos_root
    self._chromeos_chroot = path.join(chromeos_root, 'chroot')
    if mount:
      self._gcc_source_dir = path.join(constants.mounted_toolchain_root, 'gcc')
    else:
      self._gcc_source_dir = None

    self._remote = remote
    self._board = board
    ## Compute target from board
    self._target = misc.GetCtargetFromBoard(board, chromeos_root)
    if not self._target:
      sys.exit('Unsupported board "%s"' % board)
    self._executer = command_executer.GetCommandExecuter()
    self._flags = flags or ''
    self._base_dir = base_dir
    self._tmp_abs = None
    self._keep_intermediate_files = keep_intermediate_files
    self._tools = tools.split(',')

  def SetupTestingDir(self):
    self._tmp_abs = tempfile.mkdtemp(prefix='dejagnu_', dir=path.join(
        self._chromeos_chroot, 'tmp'))
    self._tmp = self._tmp_abs[len(self._chromeos_chroot):]
    self._tmp_testing_rsa = path.join(self._tmp, 'testing_rsa')
    self._tmp_testing_rsa_abs = path.join(self._tmp_abs, 'testing_rsa')

  def MakeCheckString(self):
    return ' '.join(['check-{0}'.format(t) for t in self._tools if t])

  def CleanupTestingDir(self):
    if self._tmp_abs and path.isdir(self._tmp_abs):
      if self._keep_intermediate_files:
        print('Your intermediate dejagnu files are kept, you can re-run '
              'inside chroot the command:')
        print(('  DEJAGNU={0} make -C {1} {2} '
               'RUNTESTFLAGS="--target_board={3} {4}"').format(
                   path.join(self._tmp, 'site.exp'), self._gcc_build_dir,
                   self.MakeCheckString(), self._board, self._flags))
      else:
        print 'Removing temp dir - {0}'.format(self._tmp_abs)
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
    if self._gcc_source_dir:
      self.PrepareGccFromCustomizedPath()
    else:
      self.PrepareGccDefault()
    print 'Gcc source dir - {0}'.format(self._gcc_source_dir)
    print 'Gcc build dir - {0}'.format(self._gcc_top_build_dir)

  def PrepareGccFromCustomizedPath(self):
    """Prepare gcc source, build directory from mounted source."""
    gcc_source_dir_abs = path.join(self._chromeos_chroot,
                                   self._gcc_source_dir.lstrip('/'))
    if not (path.islink(gcc_source_dir_abs) or
            path.ismount(gcc_source_dir_abs) or
            path.isdir(gcc_source_dir_abs)):
      sys.exit('Not a valid gcc source dir:  {0}'.format(gcc_source_dir_abs))

    self._gcc_top_build_dir = '{0}-build-{1}'.format(
        self._gcc_source_dir.rstrip('/'), self._target)
    self._gcc_build_dir = path.join(self._gcc_top_build_dir, 'gcc')

    gcc_top_build_dir_abs = path.join(self._chromeos_chroot,
                                      self._gcc_top_build_dir.lstrip('/'))
    if not path.isdir(gcc_top_build_dir_abs):
      sys.exit('gcc build dir does not exist:  {0}'.
               format(gcc_top_build_dir_abs))

  def PrepareGccDefault(self):
    """Auto emerging gcc for building purpose only."""
    ret = self._executer.ChrootRunCommand(
        self._chromeos_root,
        'equery w cross-%s/gcc' % self._target, return_output=True)[1]
    ret = path.basename(ret.strip())
    # ret is expected to be something like 'gcc-4.6.2-r11.ebuild' or
    # 'gcc-9999.ebuild' parse it.
    matcher = re.match('((.*)-r\d+).ebuild', ret)
    if matcher:
      gccrevision, gccversion = matcher.group(1, 2)
    elif ret == 'gcc-9999.ebuild':
      gccrevision = 'gcc-9999'
      gccversion = 'gcc-9999'
    else:
      sys.exit('Failed to get gcc version.')

    gcc_portage_dir = '/var/tmp/portage/cross-%s/%s/work' % (
        self._target, gccrevision)
    self._gcc_source_dir = path.join(gcc_portage_dir, gccversion)
    self._gcc_top_build_dir = (gcc_portage_dir + '/%s-build-%s') % (
        gccversion, self._target)
    self._gcc_build_dir = path.join(self._gcc_top_build_dir, 'gcc')
    gcc_build_dir_abs = path.join(
        self._chromeos_root, 'chroot', self._gcc_build_dir.lstrip('/'))
    if not path.isdir(gcc_build_dir_abs):
      ret = self._executer.ChrootRunCommand(
        self._chromeos_root,
        ('ebuild $(equery w cross-%s/gcc) clean prepare compile' % (
            self._target)))
      if ret:
        raise Exception('ebuild gcc failed.')

  def MakeCheck(self):
    cmd = ('cd %s ; '
           'DEJAGNU=%s make %s RUNTESTFLAGS="--target_board=%s %s"' %
           (self._gcc_build_dir, path.join(self._tmp, 'site.exp'),
            self.MakeCheckString(), self._board, self._flags))
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
    return ret

def Main(argv):
  opts = ProcessArguments(argv)
  executer = DejagnuExecuter(misc.GetRoot(argv[0])[0],
                             opts.mount, opts.chromeos_root,
                             opts.remote, opts.board, opts.flags,
                             opts.keep_intermediate_files, opts.tools)
  ret = 1
  try:
    executer.SetupTestingDir()
    executer.PrepareTestingRsaKeys()
    executer.PrepareTestFiles()
    executer.PrepareGcc()
    executer.MakeCheck()
    ret = executer.ValidateFailures()
  finally:
    executer.CleanupTestingDir()
    return ret

if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
  
