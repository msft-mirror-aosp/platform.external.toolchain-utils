#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Helper modules for Android toolchain test infrastructure.

Provides following Android toolchain test jobs and commands.
. Checkout Android toolchain source code
. Build Android toolchain
. Checkout and build Android tree (TODO)
. Checkout/build/run Android benchmarks (TODO)
. Generate size dashboard (TODO)
"""

__author__ = 'jingyu@google.com (Jing Yu)'

import os.path

from automation.clients.helper import jobs
from automation.clients.helper import perforce
from automation.common import command as cmd
from automation.common import job


class JobsFactory(object):
  def __init__(self, gcc_version='4.4.3', build_type='DEVELOPMENT'):
    assert gcc_version in ['4.4.3', '4.6', 'google_main', 'fsf_trunk']
    assert build_type in ['DEVELOPMENT', 'RELEASE']

    self.gcc_version = gcc_version
    self.commands = CommandsFactory(gcc_version, build_type)
    self.tc_tag = 'gcc-%s-%s' % (gcc_version, build_type)

  def CheckoutAndroidToolchain(self):
    """Check out Android toolchain sources by release and gcc version."""
    command = self.commands.CheckoutAndroidToolchain()
    new_job = jobs.CreateLinuxJob('AndroidCheckoutToolchain(%s)' % self.tc_tag,
                                  command)
    checkout_dir_dep = job.FolderDependency(
        new_job, self.commands.CHECKOUT_DIR)
    return new_job, checkout_dir_dep

  def BuildAndroidToolchain(self, checkout_dir_dep):
    """Build Android Toolchain into results/."""
    command = self.commands.BuildAndroidToolchain()
    new_job = jobs.CreateLinuxJob('AndroidBuildToolchain(%s)' % self.tc_tag,
                                  command)
    new_job.DependsOnFolder(checkout_dir_dep)
    tc_prefix_dep = job.FolderDependency(
        new_job, self.commands.toolchain_prefix_dir)
    return new_job, tc_prefix_dep


class CommandsFactory(object):
  CHECKOUT_DIR = 'androidtc-checkout-dir'
  ANDROIDTC_SRC_DIR = os.path.join(CHECKOUT_DIR, 'src')
  TOOLCHAIN_BUILD_DIR = 'obj'

  def __init__(self, gcc_version, build_type):
    assert gcc_version in ['4.4.3', '4.6', 'google_main', 'fsf_trunk']
    assert build_type in ['DEVELOPMENT', 'RELEASE']

    self.build_type = build_type
    self.gcc_version = gcc_version
    self.toolchain_prefix_dir = 'results/install-gcc-%s-%s' % (
        gcc_version, build_type)
    self.p4client = self._CreatePerforceClient()

  def _CreatePerforceClient(self):
    p4_dev_path = 'gcctools/google_vendor_src_branch'
    mobile_rel_branch = ('branches/'
                         'mobile_toolchain_v14_release_branch/gcctools/'
                         'google_vendor_src_branch')
    gcc_443_rel_path = ('branches/'
                        'android_compiler_v14_release_branch/gcctools/'
                        'google_vendor_src_branch/gcc/gcc-4.4.3/...')

    # Common views for tools
    p4view = perforce.View('depot2',
                           perforce.PathMapping.ListFromPathTuples(
                               [('gcctools/android/build/...', 'src/build/...'),
                                ('gcctools/android/Tarballs/...',
                                 'src/tarballs/...')]))
    for mapping in perforce.PathMapping.ListFromPathDict(
        {'gcctools/android': ['tools/scripts/...', 'master/...']}):
      p4view.add(mapping)

    # Add views for gdb
    p4view.add(perforce.PathMapping(('%s/gdb/gdb-7.1.x-android/...'
                                     % p4_dev_path),
                                    'src/gdb/gdb-7.1.x-android/...'))

    # Add view for binutils for ld and gold
    binutils_list = ['binutils/binutils-2.20.1-mobile',
                     'binutils/binutils-20100303']
    if self.build_type is 'RELEASE':
      binutils_branch = mobile_rel_branch
    else:
      binutils_branch = p4_dev_path
    for binutils in binutils_list:
      p4view.add(perforce.PathMapping('%s/%s/...' % (binutils_branch, binutils),
                                      'src/%s/...' % binutils))

    # Add view for gcc if gcc_version is '4.4.3'.
    if self.gcc_version == '4.4.3':
      if self.build_type is 'RELEASE':
        p4view.add(perforce.PathMapping(gcc_443_rel_path,
                                        'src/gcc/gcc-4.4.3/...'))
      else:
        p4view.add(perforce.PathMapping('%s/gcc/gcc-4.4.3/...' % p4_dev_path,
                                        'src/gcc/gcc-4.4.3/...'))

    return perforce.CommandsFactory(self.CHECKOUT_DIR, p4view)

  def _CheckoutGCCFromSVN(self):
    """Check out gcc from fsf svn.

       Return the command that check out gcc from svn
       to gcc_required_dir (=ANDROIDTC_SRC_DIR/src/gcc/gcc-xxx).

       TODO:
         Create a svn class that does these jobs.
         Parallelize p4 checkout and svn checkout.
    """
    if self.gcc_version == '4.4.3':
      return ''
    assert self.gcc_version in ['4.6', 'google_main', 'fsf_trunk']

    gcc_branches_dir = {'4.6': 'branches/google/gcc-4_6',
                        'google_main': 'branches/google/main',
                        'fsf_trunk': 'trunk'}

    svn_get_revision = cmd.Pipe(
        cmd.Shell('svn', 'info'),
        cmd.Shell('grep', '"Revision:"'),
        cmd.Shell('sed', '-E', '"s,Revision: ([0-9]+).*,\\1,"'),
        output='CLNUM')

    svn_co_command = 'svn co svn://gcc.gnu.org/svn/gcc/%s .' % (
        gcc_branches_dir[self.gcc_version])

    gcc_required_dir = os.path.join(self.ANDROIDTC_SRC_DIR, 'gcc',
                                    'gcc-%s' % self.gcc_version)

    return cmd.Chain(jobs.MakeDir(gcc_required_dir),
                     cmd.Wrapper(cmd.Chain(svn_co_command, svn_get_revision),
                                 cwd=gcc_required_dir))

  def CheckoutAndroidToolchain(self):
    p4client = self.p4client
    command = p4client.SetupAndDo(p4client.Sync(),
                                  p4client.SaveCurrentCLNumber('CLNUM'),
                                  p4client.Remove())
    if self.gcc_version != '4.4.3':
      command.append(self._CheckoutGCCFromSVN())

    return command

  def BuildAndroidToolchain(self):
    scripts = ScriptsFactory(self.gcc_version)
    return scripts.BuildAndroidToolchain(self.toolchain_prefix_dir,
                                         self.CHECKOUT_DIR,
                                         self.TOOLCHAIN_BUILD_DIR,
                                         self.ANDROIDTC_SRC_DIR)


class ScriptsFactory(object):
  def __init__(self, gcc_version):
    self._gcc_version = gcc_version

  def BuildAndroidToolchain(self, toolchain_prefix_dir, checkout_dir,
                            toolchain_build_dir, androidtc_src_dir):
    if self._gcc_version == '4.4.3':
      gold_command = '--enable-gold=both/gold'
    else:
      # Our binutils does not accept 'default' value. Our toolchain
      # needs to be modified. Before that happens, we give up
      # linker for now.
      #gold_command = '--enable-gold=default'
      gold_command = '--enable-gold'

    return cmd.Shell(
        'build_androidtoolchain.sh',
        '--toolchain-src=%s' % os.path.join('$JOB_TMP', androidtc_src_dir),
        '--build-path=%s' % os.path.join('$JOB_TMP', toolchain_build_dir),
        '--install-prefix=%s' % os.path.join('$JOB_TMP', toolchain_prefix_dir),
        '--target=arm-linux-androideabi',
        gold_command,
        '--with-gcc-version=%s' % self._gcc_version,
        '--with-binutils-version=2.20.1-mobile',
        '--with-gdb-version=7.1.x-android',
        '--log-path=%s/logs' % '$JOB_HOME',
        '--android-sysroot=%s' %
        os.path.join('$JOB_TMP', checkout_dir, 'gcctools', 'android',
                     'master', 'honeycomb_generic_sysroot'),
        path=os.path.join(checkout_dir, 'gcctools', 'android', 'tools',
                          'scripts'))
