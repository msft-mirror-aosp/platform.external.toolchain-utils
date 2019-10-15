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
    self.skylab_run_args = []
    self.test_that_args = []
    self.telemetry_run_args = []
    self.telemetry_crosperf_args = []
    self.call_skylab_run = False
    self.call_telemetry_crosperf_run = False
    self.call_disable_aslr = False

  def setUp(self):
    self.runner = suite_runner.SuiteRunner(
        {}, self.mock_logger, 'verbose', self.mock_cmd_exec, self.mock_cmd_term)

  def test_get_profiler_args(self):
    input_str = ("--profiler=custom_perf --profiler_args='perf_options"
                 '="record -a -e cycles,instructions"\'')
    output_str = ("profiler=custom_perf profiler_args='record -a -e "
                  "cycles,instructions'")
    res = suite_runner.GetProfilerArgs(input_str)
    self.assertEqual(res, output_str)

  def test_run(self):

    def reset():
      self.call_test_that_run = False
      self.call_skylab_run = False
      self.call_telemetry_crosperf_run = False
      self.call_disable_aslr = False
      self.skylab_run_args = []
      self.test_that_args = []
      self.telemetry_run_args = []
      self.telemetry_crosperf_args = []

    def FakeDisableASLR(runner):
      # pylint fix for unused variable.
      del runner
      self.call_disable_aslr = True

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

    def FakeRunner(command, ignore_status=False):
      # pylint fix for unused variable.
      del command, ignore_status
      return 0, '', ''

    self.runner.DisableASLR = FakeDisableASLR
    self.runner.Skylab_Run = FakeSkylabRun
    self.runner.Telemetry_Crosperf_Run = FakeTelemetryCrosperfRun
    self.runner.Test_That_Run = FakeTestThatRun
    self.runner.SetupCpuUsage = mock.Mock()
    self.runner.SetupCpuFreq = mock.Mock()
    self.runner.DutWrapper = mock.Mock(return_value=FakeRunner)
    self.runner.DisableTurbo = mock.Mock()
    self.runner.SetCpuGovernor = mock.Mock()
    self.runner.WaitCooldown = mock.Mock(return_value=0)
    self.runner.GetCpuOnline = mock.Mock(return_value={0: 1, 1: 1, 2: 0})
    self.runner.dut_config['cooldown_time'] = 0
    self.runner.dut_config['governor'] = 'fake_governor'
    self.runner.dut_config['cpu_freq_pct'] = 65
    machine = 'fake_machine'
    test_args = ''
    profiler_args = ''

    reset()
    self.mock_label.skylab = True
    self.runner.Run(machine, self.mock_label, self.telemetry_bench, test_args,
                    profiler_args)
    self.assertFalse(self.call_disable_aslr)
    self.assertTrue(self.call_skylab_run)
    self.assertFalse(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(self.skylab_run_args,
                     [self.mock_label, self.telemetry_bench, '', ''])
    self.runner.SetupCpuUsage.assert_not_called()
    self.runner.SetupCpuFreq.assert_not_called()
    self.runner.GetCpuOnline.assert_not_called()
    self.runner.DutWrapper.assert_not_called()
    self.runner.SetCpuGovernor.assert_not_called()
    self.runner.DisableTurbo.assert_not_called()
    self.runner.WaitCooldown.assert_not_called()
    self.mock_label.skylab = False

    reset()
    self.runner.Run(machine, self.mock_label, self.test_that_bench, test_args,
                    profiler_args)
    self.assertTrue(self.call_disable_aslr)
    self.assertTrue(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(
        self.test_that_args,
        ['fake_machine', self.mock_label, self.test_that_bench, '', ''])
    self.runner.SetupCpuUsage.assert_called_once_with(FakeRunner)
    self.runner.SetupCpuFreq.assert_called_once_with(FakeRunner, [0, 1])
    self.runner.GetCpuOnline.assert_called_once_with(FakeRunner)
    self.runner.DutWrapper.assert_called_once_with(
        machine, self.mock_label.chromeos_root)
    self.runner.SetCpuGovernor.assert_called_once_with(
        'fake_governor', FakeRunner, ignore_status=False)
    self.runner.DisableTurbo.assert_called_once_with(FakeRunner)
    self.runner.WaitCooldown.assert_not_called()

    reset()
    self.runner.Run(machine, self.mock_label, self.telemetry_crosperf_bench,
                    test_args, profiler_args)
    self.assertTrue(self.call_disable_aslr)
    self.assertFalse(self.call_test_that_run)
    self.assertTrue(self.call_telemetry_crosperf_run)
    self.assertEqual(self.telemetry_crosperf_args, [
        'fake_machine', self.mock_label, self.telemetry_crosperf_bench, '', ''
    ])
    self.runner.DutWrapper.assert_called_with(machine,
                                              self.mock_label.chromeos_root)

  def test_run_with_cooldown(self):

    def FakeRunner(command, ignore_status=False):
      # pylint fix for unused variable.
      del command, ignore_status
      return 0, '', ''

    self.runner.DisableASLR = mock.Mock()
    self.runner.DutWrapper = mock.Mock(return_value=FakeRunner)
    self.runner.DisableTurbo = mock.Mock()
    self.runner.SetCpuGovernor = mock.Mock()
    self.runner.SetupCpuUsage = mock.Mock()
    self.runner.SetupCpuFreq = mock.Mock()
    self.runner.WaitCooldown = mock.Mock(return_value=0)
    self.runner.GetCpuOnline = mock.Mock(return_value={0: 0, 1: 1})
    self.runner.Telemetry_Crosperf_Run = mock.Mock(return_value=(0, '', ''))
    self.runner.dut_config['cooldown_time'] = 10
    self.runner.dut_config['governor'] = 'fake_governor'
    self.runner.dut_config['cpu_freq_pct'] = 75

    self.runner.Run('fake_machine', self.mock_label,
                    self.telemetry_crosperf_bench, '', '')

    self.runner.WaitCooldown.assert_called_once_with(FakeRunner)
    self.runner.DisableASLR.assert_called_once()
    self.runner.Telemetry_Crosperf_Run.assert_called_once()
    self.runner.DisableTurbo.assert_called_once_with(FakeRunner)
    self.runner.SetupCpuUsage.assert_called_once_with(FakeRunner)
    self.runner.SetupCpuFreq.assert_called_once_with(FakeRunner, [1])
    self.runner.SetCpuGovernor.assert_called()
    self.runner.GetCpuOnline.assert_called_once_with(FakeRunner)
    self.assertGreater(self.runner.SetCpuGovernor.call_count, 1)
    self.assertEqual(
        self.runner.SetCpuGovernor.call_args,
        mock.call('fake_governor', FakeRunner, ignore_status=False))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_dut_wrapper(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd
    mock_cros_runcmd.return_value = (0, '', '')
    run_on_dut = self.runner.DutWrapper('lumpy.cros2', '/tmp/chromeos')
    mock_cros_runcmd.assert_not_called()
    run_on_dut('run command;')
    mock_cros_runcmd.assert_called_once_with(
        'run command;', chromeos_root='/tmp/chromeos', machine='lumpy.cros2')

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_dut_wrapper_fatal_error(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd
    # Command returns error 1.
    mock_cros_runcmd.return_value = (1, '', 'Error!')
    run_on_dut = self.runner.DutWrapper('lumpy.cros2', '/tmp/chromeos')
    mock_cros_runcmd.assert_not_called()
    run_on_dut('run command;')
    mock_cros_runcmd.assert_called_once_with(
        'run command;', chromeos_root='/tmp/chromeos', machine='lumpy.cros2')
    # Error status causes log fatal.
    self.assertEqual(
        self.mock_logger.method_calls[-1],
        mock.call.LogFatal('Command execution on DUT lumpy.cros2 failed.\n'
                           'Failing command: run command;\nreturned 1\n'
                           'Error message: Error!'))

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommandWOutput')
  def test_dut_wrapper_ignore_error(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommandWOutput = mock_cros_runcmd
    # Command returns error 1.
    mock_cros_runcmd.return_value = (1, '', 'Error!')
    run_on_dut = self.runner.DutWrapper('lumpy.cros2', '/tmp/chromeos')
    run_on_dut('run command;', ignore_status=True)
    mock_cros_runcmd.assert_called_once_with(
        'run command;', chromeos_root='/tmp/chromeos', machine='lumpy.cros2')
    # Error status is not fatal. LogError records the error message.
    self.assertEqual(
        self.mock_logger.method_calls[-1],
        mock.call.LogError('Command execution on DUT lumpy.cros2 failed.\n'
                           'Failing command: run command;\nreturned 1\n'
                           'Error message: Error!\n'
                           '(Failure is considered non-fatal. Continue.)'))

  def test_disable_aslr(self):
    run_on_dut = mock.Mock()
    self.runner.DisableASLR(run_on_dut)
    # pyformat: disable
    set_cpu_cmd = ('set -e && '
                   'stop ui; '
                   'if [[ -e /proc/sys/kernel/randomize_va_space ]]; then '
                   '  echo 0 > /proc/sys/kernel/randomize_va_space; '
                   'fi; '
                   'start ui ')
    run_on_dut.assert_called_once_with(set_cpu_cmd)

  def test_set_cpu_governor(self):
    dut_runner = mock.Mock(return_value=(0, '', ''))
    self.runner.SetCpuGovernor('new_governor', dut_runner, ignore_status=False)
    set_cpu_cmd = (
        'for f in `ls -d /sys/devices/system/cpu/cpu*/cpufreq 2>/dev/null`; do '
        # Skip writing scaling_governor if cpu is not online.
        ' [[ -e ${f/cpufreq/online} ]] && grep -q 0 ${f/cpufreq/online} '
        '   && continue; '
        ' cd $f; '
        ' if [[ -e scaling_governor ]]; then '
        '  echo %s > scaling_governor; fi; '
        'done; ')
    dut_runner.assert_called_once_with(
        set_cpu_cmd % 'new_governor', ignore_status=False)

  def test_set_cpu_governor_propagate_error(self):
    dut_runner = mock.Mock(return_value=(1, '', 'Error.'))
    self.runner.SetCpuGovernor('non-exist_governor', dut_runner)
    set_cpu_cmd = (
        'for f in `ls -d /sys/devices/system/cpu/cpu*/cpufreq 2>/dev/null`; do '
        # Skip writing scaling_governor if cpu is not online.
        ' [[ -e ${f/cpufreq/online} ]] && grep -q 0 ${f/cpufreq/online} '
        '   && continue; '
        ' cd $f; '
        ' if [[ -e scaling_governor ]]; then '
        '  echo %s > scaling_governor; fi; '
        'done; ')
    # By default error status is fatal.
    dut_runner.assert_called_once_with(
        set_cpu_cmd % 'non-exist_governor', ignore_status=False)

  def test_set_cpu_governor_ignore_status(self):
    dut_runner = mock.Mock(return_value=(1, '', 'Error.'))
    ret_code = self.runner.SetCpuGovernor(
        'non-exist_governor', dut_runner, ignore_status=True)
    set_cpu_cmd = (
        'for f in `ls -d /sys/devices/system/cpu/cpu*/cpufreq 2>/dev/null`; do '
        # Skip writing scaling_governor if cpu is not online.
        ' [[ -e ${f/cpufreq/online} ]] && grep -q 0 ${f/cpufreq/online} '
        '   && continue; '
        ' cd $f; '
        ' if [[ -e scaling_governor ]]; then '
        '  echo %s > scaling_governor; fi; '
        'done; ')
    dut_runner.assert_called_once_with(
        set_cpu_cmd % 'non-exist_governor', ignore_status=True)
    self.assertEqual(ret_code, 1)

  def test_disable_turbo(self):
    dut_runner = mock.Mock(return_value=(0, '', ''))
    self.runner.DisableTurbo(dut_runner)
    set_cpu_cmd = (
        # Disable Turbo in Intel pstate driver
        'if [[ -e /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then '
        '  if grep -q 0 /sys/devices/system/cpu/intel_pstate/no_turbo;  then '
        '    echo -n 1 > /sys/devices/system/cpu/intel_pstate/no_turbo; '
        '  fi; '
        'fi; ')
    dut_runner.assert_called_once_with(set_cpu_cmd)

  def test_get_cpu_online_two(self):
    """Test one digit CPU #."""
    dut_runner = mock.Mock(
        return_value=(0, '/sys/devices/system/cpu/cpu0/online 0\n'
                      '/sys/devices/system/cpu/cpu1/online 1\n', ''))
    cpu_online = self.runner.GetCpuOnline(dut_runner)
    self.assertEqual(cpu_online, {0: 0, 1: 1})

  def test_get_cpu_online_twelve(self):
    """Test two digit CPU #."""
    dut_runner = mock.Mock(
        return_value=(0, '/sys/devices/system/cpu/cpu0/online 1\n'
                      '/sys/devices/system/cpu/cpu1/online 0\n'
                      '/sys/devices/system/cpu/cpu10/online 1\n'
                      '/sys/devices/system/cpu/cpu11/online 1\n'
                      '/sys/devices/system/cpu/cpu2/online 1\n'
                      '/sys/devices/system/cpu/cpu3/online 0\n'
                      '/sys/devices/system/cpu/cpu4/online 1\n'
                      '/sys/devices/system/cpu/cpu5/online 0\n'
                      '/sys/devices/system/cpu/cpu6/online 1\n'
                      '/sys/devices/system/cpu/cpu7/online 0\n'
                      '/sys/devices/system/cpu/cpu8/online 1\n'
                      '/sys/devices/system/cpu/cpu9/online 0\n', ''))
    cpu_online = self.runner.GetCpuOnline(dut_runner)
    self.assertEqual(cpu_online, {
        0: 1,
        1: 0,
        2: 1,
        3: 0,
        4: 1,
        5: 0,
        6: 1,
        7: 0,
        8: 1,
        9: 0,
        10: 1,
        11: 1
    })

  def test_get_cpu_online_no_output(self):
    """Test error case, no output."""
    dut_runner = mock.Mock(return_value=(0, '', ''))
    with self.assertRaises(AssertionError):
      self.runner.GetCpuOnline(dut_runner)

  def test_get_cpu_online_command_error(self):
    """Test error case, command error."""
    dut_runner = mock.Mock(side_effect=AssertionError)
    with self.assertRaises(AssertionError):
      self.runner.GetCpuOnline(dut_runner)

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  def test_setup_cpu_usage_little_on_arm(self, mock_setup_arm):
    self.runner.SetupArmCores = mock_setup_arm
    dut_runner = mock.Mock(return_value=(0, 'armv7l', ''))
    self.runner.dut_config['cpu_usage'] = 'little_only'
    self.runner.SetupCpuUsage(dut_runner)
    self.runner.SetupArmCores.assert_called_once_with(dut_runner)

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  def test_setup_cpu_usage_big_on_aarch64(self, mock_setup_arm):
    self.runner.SetupArmCores = mock_setup_arm
    dut_runner = mock.Mock(return_value=(0, 'aarch64', ''))
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupCpuUsage(dut_runner)
    self.runner.SetupArmCores.assert_called_once_with(dut_runner)

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  def test_setup_cpu_usage_big_on_intel(self, mock_setup_arm):
    self.runner.SetupArmCores = mock_setup_arm
    dut_runner = mock.Mock(return_value=(0, 'x86_64', ''))
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupCpuUsage(dut_runner)
    # Check that SetupArmCores not called with invalid setup.
    self.runner.SetupArmCores.assert_not_called()

  @mock.patch.object(suite_runner.SuiteRunner, 'SetupArmCores')
  def test_setup_cpu_usage_all_on_intel(self, mock_setup_arm):
    self.runner.SetupArmCores = mock_setup_arm
    dut_runner = mock.Mock(return_value=(0, 'x86_64', ''))
    self.runner.dut_config['cpu_usage'] = 'all'
    self.runner.SetupCpuUsage(dut_runner)
    # Check that SetupArmCores not called in general case.
    self.runner.SetupArmCores.assert_not_called()

  def test_setup_arm_cores_big_on_big_little(self):
    dut_runner = mock.Mock(side_effect=[
        (0, BIG_LITTLE_CPUINFO, ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores(dut_runner)
    dut_runner.assert_called_with(
        'echo 1 | tee /sys/devices/system/cpu/cpu{2}/online; '
        'echo 0 | tee /sys/devices/system/cpu/cpu{0,1}/online')

  def test_setup_arm_cores_little_on_big_little(self):
    dut_runner = mock.Mock(side_effect=[
        (0, BIG_LITTLE_CPUINFO, ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_usage'] = 'little_only'
    self.runner.SetupArmCores(dut_runner)
    dut_runner.assert_called_with(
        'echo 1 | tee /sys/devices/system/cpu/cpu{0,1}/online; '
        'echo 0 | tee /sys/devices/system/cpu/cpu{2}/online')

  def test_setup_arm_cores_invalid_config(self):
    dut_runner = mock.Mock(side_effect=[
        (0, LITTLE_ONLY_CPUINFO, ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores(dut_runner)
    # Check that setup command is not sent when trying
    # to use 'big_only' on a platform with all little cores.
    dut_runner.assert_called_once_with('cat /proc/cpuinfo')

  def test_setup_arm_cores_not_big_little(self):
    dut_runner = mock.Mock(side_effect=[
        (0, NOT_BIG_LITTLE_CPUINFO, ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_usage'] = 'big_only'
    self.runner.SetupArmCores(dut_runner)
    # Check that setup command is not sent when trying
    # to use 'big_only' on a platform w/o support of big/little.
    dut_runner.assert_called_once_with('cat /proc/cpuinfo')

  def test_setup_arm_cores_unsupported_cpu_usage(self):
    dut_runner = mock.Mock(side_effect=[
        (0, BIG_LITTLE_CPUINFO, ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_usage'] = 'exclusive_cores'
    self.runner.SetupArmCores(dut_runner)
    # Check that setup command is not sent when trying to use
    # 'exclusive_cores' on ARM CPU setup.
    dut_runner.assert_called_once_with('cat /proc/cpuinfo')

  def test_setup_cpu_freq_single_full(self):
    online = [0]
    dut_runner = mock.Mock(side_effect=[
        (0,
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies\n',
         ''),
        (0, '1 2 3 4 5 6 7 8 9 10', ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_freq_pct'] = 100
    self.runner.SetupCpuFreq(dut_runner, online)
    self.assertGreaterEqual(dut_runner.call_count, 3)
    self.assertEqual(
        dut_runner.call_args,
        mock.call('echo 10 | tee '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'))

  def test_setup_cpu_freq_middle(self):
    online = [0]
    dut_runner = mock.Mock(side_effect=[
        (0,
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies\n',
         ''),
        (0, '1 2 3 4 5 6 7 8 9 10', ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_freq_pct'] = 60
    self.runner.SetupCpuFreq(dut_runner, online)
    self.assertGreaterEqual(dut_runner.call_count, 2)
    self.assertEqual(
        dut_runner.call_args,
        mock.call('echo 6 | tee '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'))

  def test_setup_cpu_freq_lowest(self):
    online = [0]
    dut_runner = mock.Mock(side_effect=[
        (0,
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies\n',
         ''),
        (0, '1 2 3 4 5 6 7 8 9 10', ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_freq_pct'] = 0
    self.runner.SetupCpuFreq(dut_runner, online)
    self.assertGreaterEqual(dut_runner.call_count, 2)
    self.assertEqual(
        dut_runner.call_args,
        mock.call('echo 1 | tee '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'))

  def test_setup_cpu_freq_multiple_middle(self):
    online = [0, 1]
    dut_runner = mock.Mock(side_effect=[
        (0,
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies\n'
         '/sys/devices/system/cpu/cpu1/cpufreq/scaling_available_frequencies\n',
         ''),
        (0, '1 2 3 4 5 6 7 8 9 10', ''),
        (0, '', ''),
        (0, '1 4 6 8 10 12 14 16 18 20', ''),
        (0, '', ''),
    ])
    self.runner.dut_config['cpu_freq_pct'] = 70
    self.runner.SetupCpuFreq(dut_runner, online)
    self.assertEqual(dut_runner.call_count, 5)
    self.assertEqual(
        dut_runner.call_args_list[2],
        mock.call('echo 7 | tee '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq '
                  '/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq'))
    self.assertEqual(
        dut_runner.call_args_list[4],
        mock.call('echo 14 | tee '
                  '/sys/devices/system/cpu/cpu1/cpufreq/scaling_max_freq '
                  '/sys/devices/system/cpu/cpu1/cpufreq/scaling_min_freq'))

  def test_setup_cpu_freq_no_scaling_available(self):
    online = [0, 1]
    dut_runner = mock.Mock(return_value=(2, '', 'No such file or directory'))
    self.runner.dut_config['cpu_freq_pct'] = 50
    self.runner.SetupCpuFreq(dut_runner, online)
    dut_runner.assert_called_once()
    self.assertNotRegexpMatches(dut_runner.call_args_list[0][0][0],
                                '^echo.*scaling_max_freq$')

  def test_setup_cpu_freq_multiple_no_access(self):
    online = [0, 1]
    dut_runner = mock.Mock(side_effect=[
        (0,
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies\n'
         '/sys/devices/system/cpu/cpu1/cpufreq/scaling_available_frequencies\n',
         ''),
        (0, '1 4 6 8 10 12 14 16 18 20', ''),
        AssertionError(),
    ])
    self.runner.dut_config['cpu_freq_pct'] = 30
    # Error status causes log fatal.
    with self.assertRaises(AssertionError):
      self.runner.SetupCpuFreq(dut_runner, online)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_nowait(self, mock_sleep):
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(return_value=(0, '39000', ''))
    self.runner.dut_config['cooldown_time'] = 10
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    # Send command to DUT only once to check temperature
    # and make sure it does not exceed the threshold.
    dut_runner.assert_called_once()
    mock_sleep.assert_not_called()
    self.assertEqual(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_needwait_once(self, mock_sleep):
    """Wait one iteration for cooldown.

    Set large enough timeout and changing temperature
    output. Make sure it exits when expected value
    received.
    Expect that WaitCooldown check temp twice.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(side_effect=[(0, '41000', ''), (0, '39999', '')])
    self.runner.dut_config['cooldown_time'] = 100
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    dut_runner.assert_called()
    self.assertEqual(dut_runner.call_count, 2)
    mock_sleep.assert_called()
    self.assertGreater(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_needwait(self, mock_sleep):
    """Test exit by timeout.

    Send command to DUT checking the temperature and
    check repeatedly until timeout goes off.
    Output from temperature sensor never changes.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(return_value=(0, '41000', ''))
    self.runner.dut_config['cooldown_time'] = 60
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    dut_runner.assert_called()
    self.assertGreater(dut_runner.call_count, 2)
    mock_sleep.assert_called()
    self.assertGreater(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_needwait_multtemp(self, mock_sleep):
    """Wait until all temps go down.

    Set large enough timeout and changing temperature
    output. Make sure it exits when expected value
    for all temperatures received.
    Expect 3 checks.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(side_effect=[
        (0, '41000\n20000\n30000\n45000', ''),
        (0, '39000\n20000\n30000\n41000', ''),
        (0, '39000\n20000\n30000\n31000', ''),
    ])
    self.runner.dut_config['cooldown_time'] = 100
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    dut_runner.assert_called()
    self.assertEqual(dut_runner.call_count, 3)
    mock_sleep.assert_called()
    self.assertGreater(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_thermal_error(self, mock_sleep):
    """Handle error status.

    Any error should be considered non-fatal.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(side_effect=[
        (1, '39000\n20000\n30000\n41000', 'Thermal error'),
        (1, '39000\n20000\n30000\n31000', 'Thermal error'),
    ])
    self.runner.dut_config['cooldown_time'] = 10
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    # Check that errors are ignored.
    dut_runner.assert_called_with(
        'cat /sys/class/thermal/thermal_zone*/temp', ignore_status=True)
    self.assertEqual(dut_runner.call_count, 2)
    # Check that we are waiting even when an error is returned
    # as soon as data is coming.
    mock_sleep.assert_called()
    self.assertGreater(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_thermal_no_output(self, mock_sleep):
    """Handle no output.

    Check handling of empty stdout.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(side_effect=[(1, '', 'Thermal error')])
    self.runner.dut_config['cooldown_time'] = 10
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    # Check that errors are ignored.
    dut_runner.assert_called_once_with(
        'cat /sys/class/thermal/thermal_zone*/temp', ignore_status=True)
    # No wait.
    mock_sleep.assert_not_called()
    self.assertEqual(wait_time, 0)

  @mock.patch.object(time, 'sleep')
  def test_wait_cooldown_thermal_ws_output(self, mock_sleep):
    """Handle whitespace output.

    Check handling of whitespace only.
    """
    mock_sleep.return_value = 0
    dut_runner = mock.Mock(side_effect=[(1, '\n', 'Thermal error')])
    self.runner.dut_config['cooldown_time'] = 10
    self.runner.dut_config['cooldown_temp'] = 40
    wait_time = self.runner.WaitCooldown(dut_runner)
    # Check that errors are ignored.
    dut_runner.assert_called_once_with(
        'cat /sys/class/thermal/thermal_zone*/temp', ignore_status=True)
    # No wait.
    mock_sleep.assert_not_called()
    self.assertEqual(wait_time, 0)

  @mock.patch.object(command_executer.CommandExecuter, 'CrosRunCommand')
  def test_restart_ui(self, mock_cros_runcmd):
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.RestartUI('lumpy1.cros', '/tmp/chromeos')
    mock_cros_runcmd.assert_called_once_with(
        'stop ui; sleep 5; start ui',
        chromeos_root='/tmp/chromeos',
        machine='lumpy1.cros')

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
    profiler_args = ("--profiler=custom_perf --profiler_args='perf_options"
                     '="record -a -e cycles,instructions"\'')
    self.runner.dut_config['top_interval'] = 3
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
                      'turbostat=True top_interval=3 profiler=custom_perf '
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
                     ('/tmp/chromeos/src/chromium/depot_tools/gsutil.py ls '
                      'gs://chromeos-autotest-results/swarming-12345/'
                      'autoserv_test'))
    cmd = mock_runcmd.call_args_list[1][0][0]
    self.assertEqual(cmd,
                     ('/tmp/chromeos/src/chromium/depot_tools/gsutil.py -mq '
                      'cp -r gs://chromeos-autotest-results/swarming-12345 '
                      '/tmp/chromeos/chroot/tmp'))


if __name__ == '__main__':
  unittest.main()
