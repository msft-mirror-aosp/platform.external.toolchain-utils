#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import os.path

from automation.common import command as cmd
from automation.common import job
from automation.clients.helper import jobs
from automation.clients.helper import perforce


class JobsFactory(object):
  def __init__(self):
    self.commands = CommandsFactory()

  def CheckoutCrosstool(self):
    command = self.commands.CheckoutCrosstool()
    new_job = jobs.CreateLinuxJob('CheckoutCrosstool(v15)', command)
    checkout_dir_dep = job.FolderDependency(
        new_job, CommandsFactory.CHECKOUT_DIR)
    return new_job, checkout_dir_dep

  def BuildRelease(self, checkout_dir, target):
    command = self.commands.BuildRelease(target)
    new_job = jobs.CreateLinuxJob('BuildRelease(%s)' % target, command)
    new_job.DependsOnFolder(checkout_dir)
    build_tree_dep = job.FolderDependency(
        new_job, self.commands.buildit_work_dir_path)
    return new_job, build_tree_dep

  def RunTests(self, checkout_dir, build_tree_dir, target, board):
    command = self.commands.RunTests(target, board)
    new_job = jobs.CreateLinuxJob('RunTests(%s, %s)' % (target, board), command)
    new_job.DependsOnFolder(checkout_dir)
    new_job.DependsOnFolder(build_tree_dir)
    return new_job

  def GenerateReport(self, test_jobs, target):
    command = self.commands.GenerateReport(target)
    new_job = jobs.CreateLinuxJob('GenerateReport(%s)' % target, command)
    for test_job in test_jobs:
      new_job.DependsOn(test_job)
    return new_job

class CommandsFactory(object):
  CHECKOUT_DIR = 'crosstool-checkout-dir'

  def __init__(self):
    self.buildit_path = os.path.join(
        self.CHECKOUT_DIR, 'gcctools', 'crosstool', 'v15')

    self.buildit_work_dir = 'buildit-tmp'
    self.buildit_work_dir_path = os.path.join('$JOB_TMP', self.buildit_work_dir)
    self.buildit_results_path = os.path.join('$JOB_HOME', 'packages')

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
            'zlib/zlib-1.2.3/...'],
        'gcctools/vendor_src': [
            'gcc/google/gcc-4_6/...']}

    p4view = perforce.View('depot2',
                           perforce.PathMapping.ListFromPathDict(paths))

    self.p4client = perforce.CommandsFactory(self.CHECKOUT_DIR, p4view)

  def CheckoutCrosstool(self):
    p4client = self.p4client

    return p4client.SetupAndDo(p4client.Sync(),
                               p4client.SaveCurrentCLNumber('CLNUM'),
                               p4client.Remove())

  def BuildRelease(self, target):
    results_path = self.buildit_results_path

    buildit_cmd = cmd.Shell(
        'buildit',
        '--keep-work-dir',
        '--build-type=release',
        '--work-dir=%s' % self.buildit_work_dir_path,
        '--results-dir=%s' % '$JOB_TMP/results/packages',
        '--force-release=$(< %s)' % os.path.join(
            '$JOB_TMP', self.CHECKOUT_DIR, 'CLNUM'),
        path='.')

    buildit_cmd.AddOption(target)

    return cmd.Wrapper(buildit_cmd, cwd=self.buildit_path)

  def RunTests(self, target, board):
    dejagnu_output_path = os.path.join(self.buildit_work_dir_path,
                                       'dejagnu-output')

    dejagnu_flags = ['--outdir=%s' % dejagnu_output_path,
                     '--target_board=%s' % board]

    site_exp_file = os.path.join('/google/src/head/depot/google3',
                                 'experimental/users/kbaclawski',
                                 'dejagnu/site.exp')

    gcc_build_dir_path = os.path.join(
        target, 'rpmbuild/BUILD/crosstool*-%s-0.0/build-gcc' % target)

    run_dejagnu = cmd.Wrapper(
        cmd.Chain(
          jobs.MakeDir(dejagnu_output_path),
          cmd.Shell('make', 'check', '-k',
                    '-j $(grep -c processor /proc/cpuinfo)',
                    'RUNTESTFLAGS="%s"' % ' '.join(dejagnu_flags),
                    'DEJAGNU="%s"' % site_exp_file,
                    ignore_error=True)),
        cwd=os.path.join(self.buildit_work_dir_path, gcc_build_dir_path))

    save_results = cmd.Wrapper(
        cmd.Chain(
            cmd.Shell('cp', '-r',
                      dejagnu_output_path + '/',
                      '$JOB_TMP/results/'),
            cmd.Shell('dejagnu.sh', 'summary', '-B', target,
                      os.path.join(dejagnu_output_path, 'gcc.sum'),
                      os.path.join(dejagnu_output_path, 'g++.sum'),
                      path='.')),
        cwd='$HOME/automation/clients/report')

    return cmd.Chain(run_dejagnu, save_results)

  def GenerateReport(self, target):
    return cmd.Wrapper(
        cmd.Shell('dejagnu.sh', 'html-report', '-B', target,
                  '$JOB_TMP/results/report.html',
                  path='.'),
        cwd='$HOME/automation/clients/report')
