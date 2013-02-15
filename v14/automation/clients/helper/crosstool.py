#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import os.path

from automation.common import command as cmd
from automation.common import job
from automation.common import machine
from automation.clients.helper import jobs
from automation.clients.helper import perforce


class JobsFactory(object):
  def __init__(self, crosstool_version):
    assert crosstool_version in ['v14', 'v15']

    self.crosstool_version = crosstool_version
    self.commands = CommandsFactory(crosstool_version)

  def CheckoutCrosstool(self):
    command = self.commands.CheckoutCrosstool()
    new_job = jobs.CreateLinuxJob(
        'CheckoutCrosstool(%s)' % self.crosstool_version, command)
    checkout_dir_dep = job.FolderDependency(
        new_job, CommandsFactory.CHECKOUT_DIR)
    return new_job, checkout_dir_dep

  def BuildRelease(self, checkout_dir, target):
    command = self.commands.BuildRelease(target)
    new_job = jobs.CreateLinuxJob(
        'BuildRelease(%s,%s)' % (self.crosstool_version, target), command)
    new_job.DependsOnFolder(checkout_dir)
    build_tree_dep = job.FolderDependency(
        new_job, self.commands.buildit_work_dir_path)
    return new_job, build_tree_dep

  def RunTests(self, checkout_dir, build_tree_dir, target):
    command = self.commands.RunTests(target)
    new_job = jobs.CreateLinuxJob(
        'RunTests(%s,%s)' % (self.crosstool_version, target), command)
    new_job.DependsOnFolder(checkout_dir)
    new_job.DependsOnFolder(build_tree_dir)
    return new_job


class CommandsFactory(object):
  CHECKOUT_DIR = 'crosstool-checkout-dir'

  def __init__(self, crosstool_version):
    self.buildit_path = os.path.join(
        self.CHECKOUT_DIR, 'gcctools', 'crosstool', crosstool_version)

    self.buildit_work_dir = 'buildit-%s-tmp' % crosstool_version
    self.buildit_work_dir_path = os.path.join('$JOB_TMP', self.buildit_work_dir)
    self.buildit_results_path = os.path.join('$JOB_HOME', 'packages')

    self.p4client = self._CreatePerforceClient(crosstool_version)

  def _CreatePerforceClient(self, crosstool_version):
    paths = {
        'gcctools': [
            'crosstool/v15/...',
            'scripts/...'],
        'gcctools/google_vendor_src_branch': [
            'binutils/binutils-2.21/...',
            'gcc/gcc-4.4.3/...',
            'gdb/gdb-7.2.x/...',
            'glibc/eglibc-2.11.1/...',
            'linux-headers/linux-headers-2.6.32.3/...',
            'mao/mao-r725/...',
            'zlib/zlib-1.2.3/...'],
        'gcctools/vendor_src': [
            'gcc/google/gcc-4_6/...',
            'gcc/google/main/...',
            'qemu/qemu-0.14.1/...']}

    p4view = perforce.View('depot2', perforce.PathMapping.ListFromPathDict(paths))

    return perforce.CommandsFactory(self.CHECKOUT_DIR, p4view)

  def CheckoutCrosstool(self):
    return cmd.Chain(
        self.p4client.Setup(),
        cmd.Wrapper(
            cmd.Chain(
                self.p4client.Create(),
                self.p4client.Sync(),
                self.p4client.Remove()),
            cwd=self.CHECKOUT_DIR,
            env={'P4CONFIG': '.p4config'}))

  def BuildRelease(self, target):
    return self.BuilditScript(target, 'release', run_tests=False)

  def RunTests(self, target):
    return self.BuilditScript(target, 'release', only_run_tests=True)

  def BuilditScript(self, target, build_type, run_tests=True,
                    only_run_tests=False):
    results_path = self.buildit_results_path

    if only_run_tests:
      results_path = None

    buildit_cmd = cmd.Shell(
        'buildit',
        '--build-type=%s' % build_type,
        '--work-dir=%s' % self.buildit_work_dir_path,
        '--results-dir=%s' % results_path,
        path='.')

    if run_tests:
      buildit_cmd.AddOption('--run-tests')
    elif only_run_tests:
      buildit_cmd.AddOption('--only-run-tests')

    if not only_run_tests:
      buildit_cmd.AddOption('--keep-work-dir')

    buildit_cmd.AddOption(target)

    return cmd.Wrapper(buildit_cmd, cwd=self.buildit_path)
