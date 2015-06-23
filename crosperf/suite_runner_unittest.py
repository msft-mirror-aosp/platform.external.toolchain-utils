#!/usr/bin/python
#
# Copyright 2014 Google Inc. All Rights Reserved.

"""Unittest for machine_manager."""
import os.path
import time
import hashlib

import mock
import unittest

import suite_runner
import machine_manager
import image_checksummer
import label

from benchmark import Benchmark
from benchmark_run import MockBenchmarkRun

from utils import command_executer
from utils import logger


class SuiteRunnerTest(unittest.TestCase):

  real_logger = logger.GetLogger()

  mock_cmd_exec = mock.Mock(spec=command_executer.CommandExecuter)
  mock_cmd_term = mock.Mock(spec=command_executer.CommandTerminator)
  mock_logger = mock.Mock(spec=logger.Logger)
  mock_label = label.MockLabel("lumpy", "lumpy_chromeos_image", "/tmp/chromeos",
                               "lumpy", [ "lumpy1.cros", "lumpy.cros2" ],
                               "", "", False, "")
  telemetry_crosperf_bench = Benchmark("b1_test", # name
                                       "octane",  # test_name
                                       "",        # test_args
                                       3,         # iterations
                                       False,     # rm_chroot_tmp
                                       "record -e cycles",   # perf_args
                                       "telemetry_Crosperf", # suite
                                       True)      # show_all_results

  test_that_bench = Benchmark("b2_test", # name
                              "octane",  # test_name
                              "",        # test_args
                              3,         # iterations
                              False,     # rm_chroot_tmp
                              "record -e cycles")   # perf_args

  telemetry_bench = Benchmark("b3_test", # name
                              "octane",  # test_name
                              "",        # test_args
                              3,         # iterations
                              False,     # rm_chroot_tmp
                              "record -e cycles",   # perf_args
                              "telemetry", # suite
                              False)     # show_all_results

  def setUp(self):
    self.runner = suite_runner.SuiteRunner(self.mock_logger, "verbose",
                                           self.mock_cmd_exec, self.mock_cmd_term)


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
      self.call_test_that_run = False
      self.call_telemetry_run = False
      self.call_telemetry_crosperf_run = False
      self.pin_governor_args = []
      self.test_that_args = []
      self.telemetry_run_args = []
      self.telemetry_crosperf_args    = []


    def FakePinGovernor(machine, chroot):
      self.call_pin_governor = True
      self.pin_governor_args = [machine, chroot]


    def FakeTelemetryRun(machine, label, benchmark, profiler_args):
      self.telemetry_run_args = [machine, label, benchmark, profiler_args]
      self.call_telemetry_run = True
      return "Ran FakeTelemetryRun"


    def FakeTelemetryCrosperfRun(machine, label, benchmark, test_args,
                                 profiler_args):
      self.telemetry_crosperf_args = [machine, label, benchmark, test_args,
                                      profiler_args]
      self.call_telemetry_crosperf_run = True
      return "Ran FakeTelemetryCrosperfRun"


    def FakeTestThatRun(machine, label, benchmark, test_args, profiler_args):
      self.test_that_args = [machine, label, benchmark, test_args, profiler_args]
      self.call_test_that_run = True
      return "Ran FakeTestThatRun"

    self.runner.PinGovernorExecutionFrequencies = FakePinGovernor
    self.runner.Telemetry_Run = FakeTelemetryRun
    self.runner.Telemetry_Crosperf_Run = FakeTelemetryCrosperfRun
    self.runner.Test_That_Run = FakeTestThatRun

    machine = 'fake_machine'
    test_args = ''
    profiler_args = ''
    reset()
    res = self.runner.Run(machine, self.mock_label, self.telemetry_bench,
                          test_args, profiler_args)
    self.assertTrue(self.call_pin_governor)
    self.assertTrue(self.call_telemetry_run)
    self.assertFalse(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(self.telemetry_run_args,
                     ['fake_machine', self.mock_label, self.telemetry_bench, ''])

    reset()
    res = self.runner.Run(machine, self.mock_label, self.test_that_bench,
                          test_args, profiler_args)
    self.assertTrue(self.call_pin_governor)
    self.assertFalse(self.call_telemetry_run)
    self.assertTrue(self.call_test_that_run)
    self.assertFalse(self.call_telemetry_crosperf_run)
    self.assertEqual(self.test_that_args,
                     ['fake_machine', self.mock_label, self.test_that_bench, '',
                      ''])

    reset()
    res = self.runner.Run(machine, self.mock_label, self.telemetry_crosperf_bench,
                          test_args, profiler_args)
    self.assertTrue(self.call_pin_governor)
    self.assertFalse(self.call_telemetry_run)
    self.assertFalse(self.call_test_that_run)
    self.assertTrue(self.call_telemetry_crosperf_run)
    self.assertEqual(self.telemetry_crosperf_args,
                     ['fake_machine', self.mock_label,
                      self.telemetry_crosperf_bench, '', ''])



  @mock.patch.object (command_executer.CommandExecuter, 'CrosRunCommand')
  def test_get_highest_static_frequency(self, mock_cros_runcmd):

    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    mock_cros_runcmd.return_value = [ 0, '1666000 1333000 1000000', '']
    freq = self.runner.GetHighestStaticFrequency ('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(freq, '1666000')

    mock_cros_runcmd.return_value = [ 0, '1333000', '']
    freq = self.runner.GetHighestStaticFrequency ('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(freq, '1333000')

    mock_cros_runcmd.return_value = [ 0, '1661000 1333000 1000000', '']
    freq = self.runner.GetHighestStaticFrequency ('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(freq, '1333000')



  @mock.patch.object (command_executer.CommandExecuter, 'CrosRunCommand')
  def test_pin_governor_execution_frequencies(self, mock_cros_runcmd):

    def FakeGetHighestFreq(machine_name, chromeos_root):
      return '1666000'

    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.GetHighestStaticFrequency = FakeGetHighestFreq
    self.runner.PinGovernorExecutionFrequencies('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    cmd = mock_cros_runcmd.call_args_list[0][0]
    self.assertEqual (cmd, ('set -e  && for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq; do echo 1666000 > $f; done && for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do echo 1666000 > $f; done && for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $f; done',))


  @mock.patch.object (time, 'sleep')
  @mock.patch.object (command_executer.CommandExecuter, 'CrosRunCommand')
  def test_reboot_machine(self, mock_cros_runcmd, mock_sleep):

    def FakePinGovernor(machine_name, chromeos_root):
      pass

    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    self.runner.PinGovernorExecutionFrequencies = FakePinGovernor
    self.runner.RebootMachine('lumpy1.cros', '/tmp/chromeos')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0], ('reboot && exit',))
    self.assertEqual(mock_sleep.call_count, 1)
    self.assertEqual(mock_sleep.call_args_list[0][0], (60,))


  @mock.patch.object (command_executer.CommandExecuter, 'CrosRunCommand')
  @mock.patch.object (command_executer.CommandExecuter, 'ChrootRunCommand')
  def test_test_that_run(self, mock_chroot_runcmd, mock_cros_runcmd):

    def FakeRebootMachine (machine, chroot):
      pass

    def FakeLogMsg (fd, termfd, msg, flush):
      pass

    save_log_msg = self.real_logger._LogMsg
    self.real_logger._LogMsg = FakeLogMsg
    self.runner._logger = self.real_logger
    self.runner.RebootMachine = FakeRebootMachine

    raised_exception = False
    try:
      self.runner.Test_That_Run('lumpy1.cros', self.mock_label,
                                self.test_that_bench, '', 'record -a -e cycles')
    except:
      raised_exception = True
    self.assertTrue(raised_exception)

    mock_chroot_runcmd.return_value = 0
    self.mock_cmd_exec.ChrootRunCommand = mock_chroot_runcmd
    self.mock_cmd_exec.CrosRunCommand = mock_cros_runcmd
    res = self.runner.Test_That_Run ('lumpy1.cros', self.mock_label,
                                     self.test_that_bench, '--iterations=2', '')
    self.assertEqual(mock_cros_runcmd.call_count, 1)
    self.assertEqual(mock_chroot_runcmd.call_count, 1)
    self.assertEqual(res, 0)
    self.assertEqual(mock_cros_runcmd.call_args_list[0][0],
                     ('rm -rf /usr/local/autotest/results/*',))
    args_list = mock_chroot_runcmd.call_args_list[0][0]
    self.assertEqual(len(args_list), 4)
    self.assertEqual(args_list[0], '/tmp/chromeos')
    self.assertEqual(args_list[1], ('/usr/bin/test_that  --board=lumpy '
                                    '--iterations=2 lumpy1.cros octane'))
    self.assertTrue(args_list[2])
    self.assertEqual(args_list[3], self.mock_cmd_term)

    self.real_logger._LogMsg = save_log_msg


  @mock.patch.object (os.path, 'isdir')
  @mock.patch.object (command_executer.CommandExecuter, 'ChrootRunCommand')
  def test_telemetry_crosperf_run(self, mock_chroot_runcmd, mock_isdir):

    mock_isdir.return_value = True
    mock_chroot_runcmd.return_value = 0
    self.mock_cmd_exec.ChrootRunCommand = mock_chroot_runcmd
    profiler_args = ('--profiler=custom_perf --profiler_args=\'perf_options'
                     '="record -a -e cycles,instructions"\'')
    res = self.runner.Telemetry_Crosperf_Run ('lumpy1.cros', self.mock_label,
                                              self.telemetry_crosperf_bench,
                                              '', profiler_args)
    self.assertEqual(res, 0)
    self.assertEqual(mock_chroot_runcmd.call_count, 1)
    args_list = mock_chroot_runcmd.call_args_list[0][0]
    args_dict = mock_chroot_runcmd.call_args_list[0][1]
    self.assertEqual(args_list[0], '/tmp/chromeos')
    self.assertEqual(args_list[1],
                     ('/usr/bin/test_that --autotest_dir '
                      '~/trunk/src/third_party/autotest/files '
                      ' --board=lumpy --args=" test=octane '
                      'profiler=custom_perf profiler_args=\'record -a -e '
                      'cycles,instructions\'" lumpy1.cros telemetry_Crosperf'))
    self.assertEqual(args_dict['cros_sdk_options'],
                     (' --chrome_root= --chrome_root_mount=/tmp/chrome_root  '
                      'FEATURES="-usersandbox" CHROME_ROOT=/tmp/chrome_root'))
    self.assertEqual(args_dict['command_terminator'], self.mock_cmd_term)
    self.assertTrue(args_dict['return_output'])
    self.assertEqual(len(args_dict), 3)


  @mock.patch.object (os.path, 'isdir')
  @mock.patch.object (os.path, 'exists')
  @mock.patch.object (command_executer.CommandExecuter, 'RunCommand')
  def test_telemetry_run(self, mock_runcmd, mock_exists, mock_isdir):

    def FakeLogMsg (fd, termfd, msg, flush):
      pass

    save_log_msg = self.real_logger._LogMsg
    self.real_logger._LogMsg = FakeLogMsg
    mock_runcmd.return_value = 0

    self.mock_cmd_exec.RunCommand = mock_runcmd
    self.runner._logger = self.real_logger

    profiler_args = ('--profiler=custom_perf --profiler_args=\'perf_options'
                     '="record -a -e cycles,instructions"\'')

    raises_exception = False
    mock_isdir.return_value = False
    try:
      self.runner.Telemetry_Run('lumpy1.cros', self.mock_label,
                                self.telemetry_bench, '')
    except:
      raises_exception = True
    self.assertTrue(raises_exception)

    raises_exception = False
    mock_isdir.return_value = True
    mock_exists.return_value = False
    try:
      self.runner.Telemetry_Run('lumpy1.cros', self.mock_label,
                                self.telemetry_bench, '')
    except:
      raises_exception = True
    self.assertTrue(raises_exception)

    raises_exception = False
    mock_isdir.return_value = True
    mock_exists.return_value = True
    try:
      self.runner.Telemetry_Run('lumpy1.cros', self.mock_label,
                                self.telemetry_bench, profiler_args)
    except:
      raises_exception = True
    self.assertTrue(raises_exception)

    res = self.runner.Telemetry_Run('lumpy1.cros', self.mock_label,
                                    self.telemetry_bench, '')
    self.assertEqual(res, 0)
    self.assertEqual(mock_runcmd.call_count, 1)
    self.assertEqual(mock_runcmd.call_args_list[0][0],
                     (('cd src/tools/perf && ./run_measurement '
                       '--browser=cros-chrome --output-format=csv '
                       '--remote=lumpy1.cros --identity /tmp/chromeos/src/scripts'
                       '/mod_for_test_scripts/ssh_keys/testing_rsa octane '),))

    self.real_logger._LogMsg = save_log_msg

if __name__ == "__main__":
  unittest.main()
