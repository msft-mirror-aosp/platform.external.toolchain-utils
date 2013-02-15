#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Helper modules for Android toolchain test infrastructure.

Provides following Android toolchain test jobs and commands.
. Checkout Android toolchain source code
. Build Android toolchain
. Checkout and build Android tree
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
    checkout_dir_dep = job.FolderDependency(new_job, self.commands.CHECKOUT_DIR)
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

  def GetBuildAndroidTree(self, tc_prefix_dep, product='stingray',
                          branch='honeycomb-release'):
    assert product in ['stingray', 'passion', 'trygon', 'soju']
    # We may have multiple trees in the future. Reserve the assert here.
    assert branch in ['honeycomb-release']
    command = self.commands.GetBuildAndroidTree(product, branch)
    new_job = jobs.CreateLinuxJob('AndroidGetBuildTree(%s)' % self.tc_tag,
                                  command)
    new_job.DependsOnFolder(tc_prefix_dep)
    return new_job


class CommandsFactory(object):
  CHECKOUT_DIR = 'androidtc-checkout-dir'
  ANDROIDTC_SRC_DIR = os.path.join(CHECKOUT_DIR, 'src')
  TOOLCHAIN_BUILD_DIR = 'obj'
  ANDROID_TREES_DIR = 'android_trees'

  def __init__(self, gcc_version, build_type):
    assert gcc_version in ['4.4.3', '4.6', 'google_main', 'fsf_trunk']
    assert build_type in ['DEVELOPMENT', 'RELEASE']

    self.build_type = build_type
    self.gcc_version = gcc_version
    self.binutils_version = '2.21'
    self.gold_version = '2.21'
    self.toolchain_prefix_dir = 'results/install-gcc-%s-%s' % (
        gcc_version, build_type)
    self.p4client = self._CreatePerforceClient()

  def _CreatePerforceClient(self):
    p4_dev_path = 'gcctools/google_vendor_src_branch'
    mobile_rel_branch = ('branches/'
                         'mobile_toolchain_v15_release_branch/gcctools/'
                         'google_vendor_src_branch')
    gcc_443_rel_branch = ('branches/'
                          'android_compiler_v14_release_branch/gcctools/'
                          'google_vendor_src_branch')

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
    p4view.add(perforce.PathMapping(p4_dev_path, 'src',
                                    'gdb/gdb-7.1.x-android/...'))

    # Add view for binutils for ld and gold
    if self.build_type is 'RELEASE':
      binutils_branch = mobile_rel_branch
    else:
      binutils_branch = p4_dev_path
    p4view.add(perforce.PathMapping(binutils_branch, 'src',
                                    ('binutils/binutils-%s/...' %
                                     self.binutils_version)))
    if self.binutils_version != self.gold_version:
      p4view.add(perforce.PathMapping(binutils_branch, 'src',
                                      ('binutils/binutils-%s/...' %
                                       self.gold_version)))

    # Add view for gcc if gcc_version is '4.4.3'.
    if self.gcc_version == '4.4.3':
      gcc443_path = 'gcc/gcc-4.4.3/...'
      if self.build_type is 'RELEASE':
        p4view.add(perforce.PathMapping(gcc_443_rel_branch, 'src', gcc443_path))
      else:
        p4view.add(perforce.PathMapping(p4_dev_path, 'src', gcc443_path))

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

    return cmd.Chain(cmd.MakeDir(gcc_required_dir),
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
    scripts = ScriptsFactory(self.gcc_version, self.binutils_version,
                             self.gold_version)
    return scripts.BuildAndroidToolchain(self.toolchain_prefix_dir,
                                         self.CHECKOUT_DIR,
                                         self.TOOLCHAIN_BUILD_DIR,
                                         self.ANDROIDTC_SRC_DIR)

  def _BuildAndroidTree(self, local_android_branch_dir, product):
    target_tools_prefix = os.path.join('$JOB_TMP', self.toolchain_prefix_dir,
                                       'bin', 'arm-linux-androideabi-')
    java_path = '/usr/lib/jvm/java-6-sun/bin'
    build_cmd = cmd.Shell('make', '-j8',
                          'PRODUCT-%s-userdebug' % product,
                          'TARGET_TOOLS_PREFIX=%s' % target_tools_prefix,
                          'PATH=%s:$PATH' % java_path)
    return cmd.Wrapper(build_cmd, cwd=local_android_branch_dir)

  def GetBuildAndroidTree(self, product, branch):
    assert product in ['stingray', 'passion', 'trygon', 'soju']

    # Copy the tree from atree.mtv.corp to ANDROID_TREES_DIR/branch
    androidtrees_host = 'atree.mtv.corp.google.com'
    androidtrees_path = ('/usr/local/google2/home/mobiletc-prebuild/'
                         'android_trees')
    remote_android_branch_path = os.path.join(androidtrees_path, branch)
    local_android_branch_dir = os.path.join(self.ANDROID_TREES_DIR, branch)
    gettree_cmd = cmd.Chain(cmd.MakeDir(local_android_branch_dir),
                            cmd.RemoteCopyFrom(androidtrees_host,
                                               remote_android_branch_path,
                                               local_android_branch_dir))

    # Configure and build the tree
    buildtree_cmd = self._BuildAndroidTree(local_android_branch_dir, product)

    # Copy system.img to result
    result_system_img = os.path.join(local_android_branch_dir, 'out', 'target',
                                     'product', product, 'system.img')
    copy_img = cmd.Copy(result_system_img, to_dir='results')

    return cmd.Chain(gettree_cmd, buildtree_cmd, copy_img)


class ScriptsFactory(object):
  def __init__(self, gcc_version, binutils_version, gold_version):
    self._gcc_version = gcc_version
    self._binutils_version = binutils_version
    self._gold_version = gold_version

  def BuildAndroidToolchain(self, toolchain_prefix_dir, checkout_dir,
                            toolchain_build_dir, androidtc_src_dir):
    if self._gcc_version == '4.4.3':
      gold_option = 'both/gold'
    else:
      gold_option = 'default'

    return cmd.Shell(
        'build_androidtoolchain.sh',
        '--toolchain-src=%s' % os.path.join('$JOB_TMP', androidtc_src_dir),
        '--build-path=%s' % os.path.join('$JOB_TMP', toolchain_build_dir),
        '--install-prefix=%s' % os.path.join('$JOB_TMP', toolchain_prefix_dir),
        '--target=arm-linux-androideabi',
        '--enable-gold=%s' % gold_option,
        '--with-gcc-version=%s' % self._gcc_version,
        '--with-binutils-version=%s' % self._binutils_version,
        '--with-gold-version=%s' % self._gold_version,
        '--with-gdb-version=7.1.x-android',
        '--log-path=%s/logs' % '$JOB_HOME',
        '--android-sysroot=%s' %
        os.path.join('$JOB_TMP', checkout_dir, 'gcctools', 'android',
                     'master', 'honeycomb_generic_sysroot'),
        path=os.path.join(checkout_dir, 'gcctools', 'android', 'tools',
                          'scripts'))
