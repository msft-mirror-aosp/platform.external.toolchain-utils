#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittest for suite_runner."""

from __future__ import print_function

import os.path
import time

import unittest
import mock

import suite_runner
import label

from benchmark import Benchmark

from cros_utils import command_executer
from cros_utils import logger

BIG_LITTLE_CPUINFO = """processor       : 0
model name      : ARMv8 Processor rev 4 (v8l)
BogoMIPS        : 48.00
Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 1
model name      : ARMv8 Processor rev 4 (v8l)
BogoMIPS        : 48.00
Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 2
model name      : ARMv8 Processor rev 2 (v8l)
BogoMIPS        : 48.00
Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd08
CPU revision    : 2
"""
LITTLE_ONLY_CPUINFO = """processor       : 0
model name      : ARMv8 Processor rev 4 (v8l)
BogoMIPS        : 48.00
Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4

processor       : 1
model name      : ARMv8 Processor rev 4 (v8l)
BogoMIPS        : 48.00
Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 8
CPU variant     : 0x0
CPU part        : 0xd03
CPU revision    : 4
"""

NOT_BIG_LITTLE_CPUINFO = """processor       : 0
model name      : ARMv7 Processor rev 1 (v7l)
Features        : swp half thumb fastmult vfp edsp thumbee neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 7
CPU variant     : 0x0
CPU part        : 0xc0d
CPU revision    : 1

processor       : 1
model name      : ARMv7 Processor rev 1 (v7l)
Features        : swp half thumb fastmult vfp edsp thumbee neon vfpv3 tls vfpv4
CPU implementer : 0x41
CPU architecture: 7
CPU variant     : 0x0
CPU part        : 0xc0d
CPU revision    : 1

Hardware        : Rockchip (Device Tree)
Revision        : 0000
Serial          : 0000000000000000
"""


class SuiteRunnerTest(unittest.TestCase):
  """Class of SuiteRunner test."""
  real_logger = logger.GetLogger()

  mock_cmd_exec = mock.Mock(spec=command_executer.CommandExecuter)
  mock_cmd_term = mock.Mock(spec=command_executer.CommandTerminator)
  mock_logger = mock.Mock(spec=logger.Logger)
  mock_label = label.MockLabel('lumpy', 'build', 'lumpy_chromeos_image', '', '',
                               '/tmp/chromeos', 'lumpy',
                               ['lumpy1.cros', 'lumpy.cros2'], '', '', False,
                               'average', 'gcc', False, '')
  telemetry_crosperf_bench = Benchmark(
      'b1_test',  # name
      'octane',  # test_name
      '',  # test_args
      3,  # iterations
      False,  # rm_chroot_tmp
      'record -e cycles',  # perf_args
      'telemetry_Crosperf',  # suite
      True)  # show_all_results

  test_that_bench = Benchmark(
      'b2_test',  # name
      'octane',  # test_name
      '',  # test_args
      3,  # iterations
      False,  # rm_chroot_tmp
      'record -e cycles')  # perf_args

  telemetry_bench = Benchmark(
      'b3_test',  # name
      'octane',  # test_name
      '',  # test_args
      3,  # iterations
      False,  # rm_chroot_tmp
      'record -e cycles',  # perf_args
      'telemetry',  # suite
      False)  # show_all_results

  def __init__(self, *args, **kwargs):
    super(SuiteRunnerTest, self).__init__(*args, **kwargs)
    self.call_test_that_run = False
    self.disable_aslr_args = []
    self.pin_governor_args = []
    self.setup_cpu_usage_args = []
    self.skylab_run_args = []
    self.test_that_args = []
    self.telemetry_run_args = []
    self.telemetry_crosperf_args = []
    self.call_skylab_run = False
    self.call_telemetry_crosperf_run = False
    self.call_disable_aslr = False
    self.call_pin_governor = False
    self.call_setup_cpu_usage = False

  def setUp(self):
    self.runner = suite_runner.SuiteRunner(
        {}, self.mock_logger, 'verbose', self.mock_cmd_exec, self.mock_cmd_term)

  def test_get_profiler_args(self):
    input_str = ('--profiler=custom_perf --profiler_args=\'perf_options'
                 '="record -a -e cycles,instructions"\'')
    output_str = ("profiler=custom_perf profiler_args='record -a -e "
                  "cycles,instructions'")
    res = suite_runner.GetProfilerArgs(input_str)
    self.assertEqual(res, output_str)

  def test_run(self):

    def reset():
      self.call_pin_governor = False
      self.call_setup_cpu_usage = False
      self.call_test_that_run = False
      self.call_skylab_run = False
      self.call_telemetry_crosperf_run = False
      self.pin_governor_args = []
      self.setup_cpu_usage_args = []
      self.skylab_run_args = []
      self.test_that_args = []
      self.telemetry_run_args = []
      self.telemetry_crosperf_args = []

    def FakeDisableASLR(machine, chroot):
      self.call_disable_aslr = True
      self.disable_aslr_args = [machine, chroot]

    def FakePinGovernor(machine, chroot):
      self.call_pin_governor = True
      self.pin_governor_args = [machine, chroot]

    def FakeSetupCpuUsage(machine, chroot):
      self.call_setup_cpu_usage = True
      self.setup_cpu_usage_args = [machine, chroot]

    def FakeSkylabRun(test_label, benchmark, test_args, profiler_args):
      self.skylab_run_args = [test_label, benchmark, test_args, profiler_args]
      self.call_skylab_run = True
      return 'Ran FakeSkylabRun'

    def FakeTelemetryCrosperfRun(machine, test_label, benchmark, test_args,
                                 profiler_args):
      self.telemetry_crosperf_args = [
          machine, test_label, benchmark, test_args, profiler_args
      ]
      self.call_telemetry_crosperf_run = True
      return 'Ran FakeTelemetryCrosperfRun'

    def FakeTestThatRun(machine, test_label, benchmark, test_args,
                        profiler_args):
      self.test_that_args = [
          machine, test_label, benchmark, test_args, profiler_args
      ]
      self.call_test_that_run = True
      return 'Ran FakeTestThatRun'

    self.runner.DisableASLR = FakeDisableASLR
    self.runner.PinGovernorExecutionFrequencies = FakePinGovernor
    self.runner.SetupCpuUsage = FakeSetupCpuUsage
    self.runner.Skylab_Run = FakeSkylabRun
    self.runner.Telemetry_Crosperf_Run = FakeTelemetryCrosperfRun
    self.runner.Test_That_Run = FakeTestThatRun
    machine = 'fake_machine'
    test_args = ''
    profiler_args = ''

    reset()
    self.mock_label.skylab = True
    self.runner.Run(machine, self.mock_label, self.telemetry_bench, test_args,
                    profiler_args)
    self.assertFalse(self.call_disable_aslr)
    self.assertFalse(self.call_pin_governor)
    self.assertFalse(self.call_setup_cpu_usage)
    self.assertTrue(self.call_skylab_run)
    self.assertFalse(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(self.skylab_run_args,
                     [self.mock_label, self.telemetry_bench, '', ''])
    self.mock_label.skylab = False

    reset()
    self.runner.Run(machine, self.mock_label, self.test_that_bench, test_args,
                    profiler_args)
    self.assertTrue(self.call_disable_aslr)
    self.assertTrue(self.call_pin_governor)
    self.assertTrue(self.call_setup_cpu_usage)
    self.assertEqual(self.setup_cpu_usage_args,
                     [machine, self.mock_label.chromeos_root])
    self.assertTrue(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(
        self.test_that_args,
        ['fake_machine', self.mock_label, self.test_that_bench, '', ''])

    reset()
    self.runner.Run(machine, self.mock_label, self.telemetry_crosperf_bench,
                    test_args, profiler_args)
    self.assertTrue(self.call_disable_aslr)
    self.assertTrue(self.call_pin_governor)
    self.assertTrue(self.call_setup_cpu_usage)
    self.assertFalse(self.call_test_that_run)
    self.assertTrue(self.call_telemetry_crosperf_run)
    self.assertEqual(self.telemetry_crosperf_args, [
        'fake_machine', self.mock_label, self.telemetry_crosperf_bench, '', ''
    ])

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_disable_aslr(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.DisableASLR('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    cmd = mock_cros_runcmd.call_args_list[0][0]
    # pyformat: disable
    set_cpu_cmd = ('set -e && '
                   'stop ui; '
                   'if [[ -e /proc/sys/kernel/randomize_va_space ]]; then '
                   '  echo 0 > /proc/sys/kernel/randomize_va_space; '
                   'fi; '
                   'start ui ')
    # pyformat: enable
    self.assertEqual(cmd, (set_cpu_cmd,))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_pin_governor_execution_frequencies(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.PinGovernorExecutionFrequencies('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    cmd = mock_cros_runcmd.call_args_list[0][0]
    # pyformat: disable
    set_cpu_cmd = (
        'for f in `ls -d /sys/devices/system/cpu/cpu*/cpufreq 2>/dev/null`; do '
        # Skip writing scaling_governor if cpu is not online.
        ' [[ -e ${f/cpufreq/online} ]] && grep -q 0 ${f/cpufreq/online} '
        '   && continue; '
        # The cpu is online, can update.
        ' cd $f; '
        ' if [[ -e scaling_governor ]]; then '
        '  echo performance > scaling_governor; fi; '
        'done; '
        # Disable Turbo in Intel pstate driver
        'if [[ -e /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then '
        '  if grep -q 0 /sys/devices/system/cpu/intel_pstate/no_turbo;  then '
        '    echo -n 1 > /sys/devices/system/cpu/intel_pstate/no_turbo; '
        '  fi; '
        'fi; ')
    # pyformat: enable
    self.assertEqual(cmd, (set_cpu_cmd,))

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_setup_cpu_usage_little_on_arm(self, mock_cros_runcmd_wout,
                                         mock_setup_arm):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    self.runner.SetupArmCores = mock_setup_arm
    mock_cros_runcmd_wout.return_value = (0, 'armv7l', '')
    self.runner.dut_config['cpu_usage'] = 'little_only'
    self.runner.SetupCpuUsage('remote.cros', '/tmp/chromeos')
    self.assertEqual(mock_setup_arm.call_count, 1)

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_setup_cpu_usage_big_on_aarch64(self, mock_cros_runcmd_wout,
                                          mock_setup_arm):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    self.runner.SetupArmCores = mock_setup_arm
    mock_cros_runcmd_wout.return_value = (0, 'aarch64', '')
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupCpuUsage('remote.cros', '/tmp/chromeos')
    self.assertEqual(mock_setup_arm.call_count, 1)

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_setup_cpu_usage_all_on_intel(self, mock_cros_runcmd_wout,
                                        mock_setup_arm):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    self.runner.SetupArmCores = mock_setup_arm
    mock_cros_runcmd_wout.return_value = (0, 'x86_64', '')
    self.runner.dut_config['cpu_usage'] = 'all'
    self.runner.SetupCpuUsage('remote.cros', '/tmp/chromeos')
    # Check that SetupArmCores not called.
    self.assertEqual(mock_setup_arm.call_count, 0)

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_setup_arm_cores_big_on_big_little(self, mock_cros_runcmd,
                                             mock_cros_runcmd_wout):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    mock_cros_runcmd_wout.return_value = (0, BIG_LITTLE_CPUINFO, '')
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores('remote.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0],
                     ('echo 1 | tee /sys/devices/system/cpu/cpu{2}/online; '
                      'echo 0 | tee /sys/devices/system/cpu/cpu{0,1}/online',))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_setup_arm_cores_little_on_big_little(self, mock_cros_runcmd,
                                                mock_cros_runcmd_wout):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    mock_cros_runcmd_wout.return_value = (0, BIG_LITTLE_CPUINFO, '')
    self.runner.dut_config['cpu_usage'] = 'little_only'
    self.runner.SetupArmCores('remote.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0],
                     ('echo 1 | tee /sys/devices/system/cpu/cpu{0,1}/online; '
                      'echo 0 | tee /sys/devices/system/cpu/cpu{2}/online',))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_setup_arm_cores_invalid_config(self, mock_cros_runcmd,
                                          mock_cros_runcmd_wout):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    mock_cros_runcmd_wout.return_value = (0, LITTLE_ONLY_CPUINFO, '')
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores('remote.cros', '/tmp/chromeos')
    # Check that CrosRun is not called when trying
    # to use 'big_only' on a platform with all little cores.
    self.assertEqual(mock_cros_runcmd.call_count, 0)

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_setup_arm_cores_not_big_little(self, mock_cros_runcmd,
                                          mock_cros_runcmd_wout):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    mock_cros_runcmd_wout.return_value = (0, NOT_BIG_LITTLE_CPUINFO, '')
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores('remote.cros', '/tmp/chromeos')
    # Check that CrosRun is not called when trying
    # to use 'big_only' on a platform w/o support of big/little.
    self.assertEqual(mock_cros_runcmd.call_count, 0)

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_setup_arm_cores_unsupported_cpu_usage(self, mock_cros_runcmd,
                                                 mock_cros_runcmd_wout):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd_wout
    mock_cros_runcmd_wout.return_value = (0, BIG_LITTLE_CPUINFO, '')
    self.runner.dut_config['cpu_usage'] = 'exclusive_cores'
    self.runner.SetupArmCores('remote.cros', '/tmp/chromeos')
    # Check that CrosRun is not called when trying to use
    # 'exclusive_cores' on ARM CPU setup.
    self.assertEqual(mock_cros_runcmd.call_count, 0)

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_reboot_machine(self, mock_cros_runcmd):

    def FakePinGovernor(machine_name, chromeos_root):
      if machine_name or chromeos_root:
        pass

    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.PinGovernorExecutionFrequencies = FakePinGovernor
    self.runner.RestartUI('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0],
                     ('stop ui; sleep 5; start ui',))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def test_test_that_run(self, mock_chroot_runcmd, mock_cros_runcmd):

    def FakeLogMsg(fd, termfd, msg, flush=True):
      if fd or termfd or msg or flush:
        pass

    save_log_msg = self.real_logger.LogMsg
    self.real_logger.LogMsg = FakeLogMsg
    self.runner.logger = self.real_logger

    raised_exception = False
    try:
      self.runner.Test_That_Run('lumpy1.cros', self.mock_label,
                                self.test_that_bench, '', 'record -a -e cycles')
    except SystemExit:
      raised_exception = True
    self.assertTrue(raised_exception)

    mock_chroot_runcmd.return_value = 0
    self.mock_cmd_exec.ChrootRunCommandWOutput = mock_chroot_runcmd
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    res = self.runner.Test_That_Run('lumpy1.cros', self.mock_label,
                                    self.test_that_bench, '--iterations=2', '')
    self.assertEqual(mock_cros_runcmd.call_count, 2)
    self.assertEqual(mock_chroot_runcmd.call_count, 1)
    self.assertEqual(res, 0)
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0],
                     ('rm -rf /usr/local/autotest/results/*',))
    args_list = mock_chroot_runcmd.call_args_list[0][0]
    args_dict = mock_chroot_runcmd.call_args_list[0][1]
    self.assertEqual(len(args_list), 2)
    self.assertEqual(args_list[0], '/tmp/chromeos')
    self.assertEqual(args_list[1], ('/usr/bin/test_that  '
                                    '--fast  --board=lumpy '
                                    '--iterations=2 lumpy1.cros octane'))
    self.assertEqual(args_dict['command_terminator'], self.mock_cmd_term)
    self.real_logger.LogMsg = save_log_msg

  @mock.patch.object(os.path, 'isdir')
  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def test_telemetry_crosperf_run(self, mock_chroot_runcmd, mock_isdir):

    mock_isdir.return_value = True
    mock_chroot_runcmd.return_value = 0
    self.mock_cmd_exec.ChrootRunCommandWOutput = mock_chroot_runcmd
    profiler_args = ('--profiler=custom_perf --profiler_args=\'perf_options'
                     '="record -a -e cycles,instructions"\'')
    res = self.runner.Telemetry_Crosperf_Run('lumpy1.cros', self.mock_label,
                                             self.telemetry_crosperf_bench, '',
                                             profiler_args)
    self.assertEqual(res, 0)
    self.assertEqual(mock_chroot_runcmd.call_count, 1)
    args_list = mock_chroot_runcmd.call_args_list[0][0]
    args_dict = mock_chroot_runcmd.call_args_list[0][1]
    self.assertEqual(args_list[0], '/tmp/chromeos')
    self.assertEqual(args_list[1],
                     ('/usr/bin/test_that --autotest_dir '
                      '~/trunk/src/third_party/autotest/files --fast '
                      '--board=lumpy --args=" run_local=False test=octane '
                      'turbostat=True profiler=custom_perf '
                      'profiler_args=\'record -a -e cycles,instructions\'" '
                      'lumpy1.cros telemetry_Crosperf'))
    self.assertEqual(args_dict['cros_sdk_options'],
                     ('--no-ns-pid --chrome_root= '
                      '--chrome_root_mount=/tmp/chrome_root '
                      'FEATURES="-usersandbox" CHROME_ROOT=/tmp/chrome_root'))
    self.assertEqual(args_dict['command_terminator'], self.mock_cmd_term)
    self.assertEqual(len(args_dict), 2)

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def test_skylab_run(self, mock_runcmd):

    def FakeDownloadResult(l, task_id):
      if l and task_id:
        self.assertEqual(task_id, '12345')
        return 0

    mock_runcmd.return_value = \
      (0,
       '"success":true\nCreated Swarming task https://swarming/task?id=12345',
       '')
    self.mock_cmd_exec.RunCommandWOutput = mock_runcmd
    self.mock_label.skylab = True
    self.runner.DownloadResult = FakeDownloadResult
    res = self.runner.Skylab_Run(self.mock_label, self.test_that_bench, '', '')
    ret_tup = (0, '\nResults placed in tmp/swarming-12345\n', '')
    self.assertEqual(res, ret_tup)
    self.assertEqual(mock_runcmd.call_count, 2)

    args_list = mock_runcmd.call_args_list[0][0]
    args_dict = mock_runcmd.call_args_list[0][1]
    self.assertEqual(args_list[0],
                     ('/usr/local/bin/skylab create-test  '
                      '-dim dut_name:lumpy1 -dim dut_name:lumpy.cros2 '
                      '-bb=false -client-test -board=lumpy -image=build '
                      '-pool=DUT_POOL_QUOTA octane'))
    self.assertEqual(args_dict['command_terminator'], self.mock_cmd_term)

    args_list = mock_runcmd.call_args_list[1][0]
    self.assertEqual(args_list[0], ('skylab wait-task -bb=false 12345'))
    self.assertEqual(args_dict['command_terminator'], self.mock_cmd_term)

  @mock.patch.object(time, 'sleep')
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommand')
  def test_download_result(self, mock_runcmd, mock_sleep):
    mock_runcmd.return_value = 0
    mock_sleep.return_value = 0
    self.mock_cmd_exec.RunCommand = mock_runcmd

    self.runner.DownloadResult(self.mock_label, '12345')

    self.assertEqual(mock_runcmd.call_count, 2)
    cmd = mock_runcmd.call_args_list[0][0][0]
    self.assertEqual(cmd,
                     ('/tmp/chromeos/chromium/tools/depot_tools/gsutil.py ls '
                      'gs://chromeos-autotest-results/swarming-12345/'
                      'autoserv_test'))
    cmd = mock_runcmd.call_args_list[1][0][0]
    self.assertEqual(cmd,
                     ('/tmp/chromeos/chromium/tools/depot_tools/gsutil.py -mq '
                      'cp -r gs://chromeos-autotest-results/swarming-12345 '
                      '/tmp/chromeos/chroot/tmp'))


if __name__ == '__main__':
  unittest.main()
