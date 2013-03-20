#!/usr/bin/python

__author__ = 'shenhan@google.com (Han Shen)'

import optparse
import os
import re
import repo_to_repo
import sys

from utils import command_executer
from utils import logger
from utils import misc

GCC_REPO_PATH='src/third_party/gcc'
CHROMIUMOS_OVERLAY_PATH='src/third_party/chromiumos-overlay'
GCC_EBUILD_PATH='src/third_party/chromiumos-overlay/sys-devel/gcc'

class Bootstrapper(object):
  def __init__(self, chromeos_root, branch=None, gcc_dir=None,
               setup_gcc_ebuild_file_only=False):
    self._chromeos_root = chromeos_root
    self._branch = branch
    self._gcc_dir = gcc_dir
    self._ce = command_executer.GetCommandExecuter()
    self._logger = logger.GetLogger()
    self._gcc_src_dir = None
    self._branch_tree = None
    self._gcc_ebuild_file = None
    self._gcc_ebuild_file_name = None
    self._setup_gcc_ebuild_file_only = setup_gcc_ebuild_file_only

  def SubmitToLocalBranch(self):
    # If "_branch" is set, we just use it.
    if self._branch:
      return True

    # The next few steps creates an internal branch to sync with the gcc dir
    # user provided.
    self._branch = 'internal_testing_branch_no_use'
    chrome_gcc_dir = os.path.join(
      self._chromeos_root, GCC_REPO_PATH)

    # 0. Test to see if git tree is free of local changes.
    if not misc.IsGitTreeClean(chrome_gcc_dir):
      self._logger.LogError(
        'Git repository "{0}" not clean, aborted.'.format(chrome_gcc_dir))
      return False

    # 1. Checkout/create a (new) branch for testing.
    command = 'cd "{0}" && git checkout -B {1} cros/master'.format(
      chrome_gcc_dir, self._branch)
    ret = self._ce.RunCommand(command)
    if ret:
      self._logger.LogError('Failed to create a temp branch for test, aborted.')
      return False

    # 2. Sync sources from user provided gcc dir to chromiumos gcc git.
    local_gcc_repo = repo_to_repo.FileRepo(self._gcc_dir)
    chrome_gcc_repo = repo_to_repo.GitRepo(chrome_gcc_dir, self._branch)
    chrome_gcc_repo._root_dir = chrome_gcc_dir
    # Delete all stuff before start mapping.
    self._ce.RunCommand('cd {0} && rm -rf *'.format(chrome_gcc_dir))
    local_gcc_repo.MapSources(chrome_gcc_repo.GetRoot())

     # 3. Verify sync successfully.
    diff = 'diff -r -x .git -x .svn "{0}" "{1}"'.format(
      self._gcc_dir, chrome_gcc_dir)
    if self._ce.RunCommand(diff):
      self._logger.LogError('Sync not successfully, aborted.')
      return False
    else:
      self._logger.LogOutput('Sync successfully done.')

    # 4. Commit all changes.
    ret = chrome_gcc_repo.CommitLocally(
      'Synced with gcc source tree at - "{0}".'.format(self._gcc_dir))
    if ret:
      self._logger.LogError('Commit to local branch "{0}" failed, aborted.'.
                            format(self._branch))
      return False
    return True

  def CheckoutBranch(self):
    self._gcc_src_dir = os.path.join(self._chromeos_root, GCC_REPO_PATH)
    command = 'cd "{0}" && git checkout {1}'.format(
      self._gcc_src_dir, self._branch)
    if not self._ce.RunCommand(command, print_to_console=True):
      # Get 'TREE' value of this commit
      command = 'cd "{0}" && git cat-file -p {1} ' \
          '| grep -E "^tree [a-f0-9]+$" | cut -d" " -f2'.format(
        self._gcc_src_dir, self._branch)
      ret, stdout, stderr  = self._ce.RunCommand(
        command, return_output=True, print_to_console=False)
      # Pipe operation always has a zero return value. So need to check if
      # stdout is valid.
      if not ret and stdout and \
            re.match('[0-9a-h]{40}', stdout.strip(), re.IGNORECASE):
        self._branch_tree = stdout.strip()
        self._logger.LogOutput('Find tree for branch "{0}" - "{1}"'.format(
            self._branch, self._branch_tree))
        return True
    self._logger.LogError(
      'Failed to checkout "{0}" or failed to get tree value, aborted.'.format(
        self._branch))
    return False

  def FindGccEbuildFile(self):
    # To get the active gcc ebuild file, we need a workable chroot first.
    if not os.path.exists(os.path.join(self._chromeos_root, 'chroot')) and \
          self._ce.RunCommand('cd "{0}" && cros_sdk --create'.format(
        self._chromeos_root)):
      self._logger.LogError(
        ('Failed to instal a initial chroot, aborted.\n'
         'If previous bootstrap failed, do a "cros_sdk --delete" to remove '
         'in-complete chroot.'))
      return False

    rv, stdout, stderr  = self._ce.ChrootRunCommand(self._chromeos_root,
      'equery w sys-devel/gcc', return_output=True, print_to_console=True)
    if rv:
      self._logger.LogError('Failed to execute inside chroot '
                            '"equery w sys-devel/gcc", aborted.')
      return False
    m = re.match('^.*/({0}/(.*\.ebuild))$'.format(GCC_EBUILD_PATH), stdout)
    if not m:
      self._logger.LogError(
        ('Failed to find gcc ebuild file, aborted. '
         'If previous bootstrap failed, do a "cros_sdk --delete" to remove '
         'in-complete chroot.'))
      return False
    self._gcc_ebuild_file = os.path.join(self._chromeos_root, m.group(1))
    self._gcc_ebuild_file_name = m.group(2)
    return True

  def InplaceModifyEbuildFile(self):
    """Using sed to fill properly the values into the following lines -
         CROS_WORKON_COMMIT="..."
         CROS_WORKON_TREE="..."
    """
    command = 'sed -i ' \
        '-e \'s!^CROS_WORKON_COMMIT=".*"$!CROS_WORKON_COMMIT="{0}"!\' ' \
        '-e \'s!^CROS_WORKON_TREE=".*"$!CROS_WORKON_TREE="{1}"!\' {2}'.format(
      self._branch, self._branch_tree, self._gcc_ebuild_file)
    rv = self._ce.RunCommand(command)
    if rv:
      self._logger.LogError(
        'Failed to modify commit and tree value for "{0}"", aborted.'.format(
          self._gcc_ebuild_file))
      return False
    return True

  def DoBootstrapping(self):
    logfile = os.path.join(self._chromeos_root, 'bootstrap.log')
    command = 'cd "{0}" && cros_sdk --delete --bootstrap |& tee "{1}"'. \
        format(self._chromeos_root, logfile)
    rv = self._ce.RunCommand(command, \
                               return_output=False, print_to_console=True)
    if rv:
      self._logger.LogError('Bootstrapping failed, log file - "{0}"\n'.format(
          logfile))
      return False

    self._logger.LogOutput('Bootstrap succeeded.')
    return True

  def Do(self):
    if self.SubmitToLocalBranch() and \
          self.CheckoutBranch() and \
          self.FindGccEbuildFile() and \
          self.InplaceModifyEbuildFile() and \
          (self._setup_gcc_ebuild_file_only or self.DoBootstrapping()):
      ret = True
    else:
      ret = False
    ## Warn that the ebuild file is modified.
    if self._gcc_ebuild_file:
      self._logger.LogWarning(
        ('Gcc ebuild file is (probably) modified, to revert the file - \n'
         'bootstrap_compiler.py --chromeos={0} --reset_gcc_ebuild_file').format(
          self._chromeos_root))

    return ret


def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option('-c', '--chromeos_root', dest='chromeos_root',
                    help=('ChromeOs root dir.'))
  parser.add_option('-b', '--branch', dest='branch',
                    help=('The branch to test against. '
                          'This branch must be a local branch '
                          'inside "src/third_party/gcc". '
                          'Notice, this must not be used with "--gcc".'))
  parser.add_option('-g', '--gcc_dir', dest='gcc_dir',
                    help=('Use a local gcc tree to do bootstrapping. '
                          'Notice, this must not be used with "--branch".'))
  parser.add_option('--fixperm', dest='fixperm',
                    default=False, action='store_true',
                    help=('Fix the (notorious) permission error '
                          'while trying to bootstrap the chroot. '
                          'Note this takes an extra 10-15 minutes '
                          'and is only needed once per chromiumos tree.'))
  parser.add_option('--setup_gcc_ebuild_file_only',
                    dest='setup_gcc_ebuild_file_only',
                    default=False, action='store_true',
                    help=('Setup gcc ebuild file to pick up the '
                          'branch (--branch) or user gcc source (--gcc_dir) '
                          'and exit. Keep chroot as is.'))
  parser.add_option('--reset_gcc_ebuild_file', dest='reset_gcc_ebuild_file',
                    default=False, action='store_true',
                    help=('Reset the modification that is done by this script.'
                          'Note, when this script is running, it will modify '
                          'the active gcc ebuild file. Use this option to '
                          'reset (what this script has done) and exit.'))
  options = parser.parse_args(argv)[0]
  if not options.chromeos_root:
    parser.error('Missing mandatory option "--chromeos".')
    return 1

  options.chromeos_root = os.path.abspath(
    os.path.expanduser(options.chromeos_root))

  if not os.path.isdir(options.chromeos_root):
    logger.GetLogger().LogError(
      '"{0}" does not exist.'.format(options.chromeos_root))
    return 1

  if options.fixperm:
    # Fix perm error before continuing.
    cmd = ('sudo find "{0}" \( -name ".cache" -type d -prune \) -o ' + \
             '\( -name "chroot" -type d -prune \) -o ' + \
             '\( -type f -exec chmod a+r {{}} \; \) -o ' + \
             '\( -type d -exec chmod a+rx {{}} \; \)').format(
      options.chromeos_root)
    logger.GetLogger().LogOutput(
      'Fixing perm issues for chromeos root, this might take some time.')
    command_executer.GetCommandExecuter().RunCommand(cmd)

  if options.reset_gcc_ebuild_file:
    if options.gcc_dir or options.branch:
      logger.GetLogger().LogWarning('Ignoring "--gcc_dir" or "--branch".')
    if options.setup_gcc_ebuild_file_only:
      logger.GetLogger().LogError(
        ('Conflict options "--reset_gcc_ebuild_file" '
         'and "--setup_gcc_ebuild_file_only".'))
      return 1
    # Reset gcc ebuild file and exit.
    rv = misc.GetGitChangesAsList(
      os.path.join(options.chromeos_root,CHROMIUMOS_OVERLAY_PATH),
      path='sys-devel/gcc/gcc-*.ebuild',
      staged=False)
    if rv:
      cmd = 'cd {0} && git checkout --'.format(os.path.join(
          options.chromeos_root, CHROMIUMOS_OVERLAY_PATH))
      for g in rv:
        cmd += ' ' + g
      rv = command_executer.GetCommandExecuter().RunCommand(cmd)
      if rv:
        logger.GetLogger().LogWarning('Failed to reset gcc ebuild file.')
      return rv
    else:
      logger.GetLogger().LogWarning(
        'Did not find any modified gcc ebuild file.')
      return 1

  if options.gcc_dir:
    options.gcc_dir = os.path.abspath(os.path.expanduser(options.gcc_dir))
    if not os.path.isdir(options.gcc_dir):
      logger.GetLogger().LogError(
        '"{0}" does not exist.'.format(options.gcc_dir))
      return 1

  if options.branch and options.gcc_dir:
    parser.error('Only one of "--gcc" and "--branch" can be specified.')
    return 1
  if not (options.branch or options.gcc_dir):
    parser.error('At least one of "--gcc" and "--branch" must be specified.')
    return 1

  if Bootstrapper(
    options.chromeos_root, branch=options.branch, gcc_dir=options.gcc_dir,
    setup_gcc_ebuild_file_only=options.setup_gcc_ebuild_file_only).Do():
    return 0
  return 1


if __name__ == '__main__':
  retval = Main(sys.argv)
  sys.exit(retval)
