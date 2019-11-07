# -*- coding: utf-8 -*-
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""SuiteRunner defines the interface from crosperf to test script."""

from __future__ import division
from __future__ import print_function

import json
import os
import shlex
import time

from cros_utils import command_executer
from cros_utils.device_setup_utils import DutWrapper

TEST_THAT_PATH = '/usr/bin/test_that'
# TODO: Need to check whether Skylab is installed and set up correctly.
SKYLAB_PATH = '/usr/local/bin/skylab'
GS_UTIL = 'src/chromium/depot_tools/gsutil.py'
AUTOTEST_DIR = '~/trunk/src/third_party/autotest/files'
CHROME_MOUNT_DIR = '/tmp/chrome_root'


def GetProfilerArgs(profiler_args):
  # Remove "--" from in front of profiler args.
  args_list = shlex.split(profiler_args)
  new_list = []
  for arg in args_list:
    if arg[0:2] == '--':
      arg = arg[2:]
    new_list.append(arg)
  args_list = new_list

  # Remove "perf_options=" from middle of profiler args.
  new_list = []
  for arg in args_list:
    idx = arg.find('perf_options=')
    if idx != -1:
      prefix = arg[0:idx]
      suffix = arg[idx + len('perf_options=') + 1:-1]
      new_arg = prefix + "'" + suffix + "'"
      new_list.append(new_arg)
    else:
      new_list.append(arg)
  args_list = new_list

  return ' '.join(args_list)


class SuiteRunner(object):
  """This defines the interface from crosperf to test script."""

  def __init__(self,
               dut_config,
               logger_to_use=None,
               log_level='verbose',
               cmd_exec=None,
               cmd_term=None,
               enable_aslr=False):
    self.logger = logger_to_use
    self.log_level = log_level
    self._ce = cmd_exec or command_executer.GetCommandExecuter(
        self.logger, log_level=self.log_level)
    # DUT command executer.
    # Will be initialized and used within Run.
    self._ct = cmd_term or command_executer.CommandTerminator()
    self.enable_aslr = enable_aslr
    self.dut_config = dut_config

  def Run(self, cros_machine, label, benchmark, test_args, profiler_args):
    machine_name = cros_machine.name
    if not label.skylab:
      # Initialize command executer on DUT.
      run_on_dut = DutWrapper(
          label.chromeos_root,
          machine_name,
          logger=self.logger,
          log_level=self.log_level,
          ce=self._ce,
          dut_config=self.dut_config)
    for i in range(0, benchmark.retries + 1):
      if label.skylab:
        # TODO: need to migrate Device setups to autotest for skylab.
        # Since in skylab mode, we may not know the DUT until one is assigned
        # to the test. For telemetry_Crosperf run, we can move them into the
        # server test script, for client runs, need to figure out wrapper to do
        # it before running.
        ret_tup = self.Skylab_Run(label, benchmark, test_args, profiler_args)
      else:
        self.SetupDevice(run_on_dut, cros_machine)
        if benchmark.suite == 'telemetry_Crosperf':
          run_on_dut.DecreaseWaitTime()
          ret_tup = self.Telemetry_Crosperf_Run(machine_name, label, benchmark,
                                                test_args, profiler_args)
        else:
          ret_tup = self.Test_That_Run(machine_name, label, benchmark,
                                       test_args, profiler_args)

      if ret_tup[0] != 0:
        self.logger.LogOutput('benchmark %s failed. Retries left: %s' %
                              (benchmark.name, benchmark.retries - i))
      elif i > 0:
        self.logger.LogOutput(
            'benchmark %s succeded after %s retries' % (benchmark.name, i))
        break
      else:
        self.logger.LogOutput(
            'benchmark %s succeded on first try' % benchmark.name)
        break
    return ret_tup

  def SetupDevice(self, run_on_dut, cros_machine):
    # Stop UI before configuring the DUT.
    # This will accelerate setup (waiting for cooldown has x10 drop)
    # and help to reset a Chrome state left after the previous test.
    run_on_dut.StopUI()

    # Unless the user turns on ASLR in the flag, we first disable ASLR
    # before running the benchmarks
    if not self.enable_aslr:
      run_on_dut.DisableASLR()

    # CPU usage setup comes first where we enable/disable cores.
    run_on_dut.SetupCpuUsage()
    cpu_online_status = run_on_dut.GetCpuOnline()
    # List of online cores of type int (core number).
    online_cores = [
        core for core, status in cpu_online_status.items() if status
    ]
    if self.dut_config['cooldown_time']:
      # Setup power conservative mode for effective cool down.
      # Set ignore status since powersave may no be available
      # on all platforms and we are going to handle it.
      ret = run_on_dut.SetCpuGovernor('powersave', ignore_status=True)
      if ret:
        # "powersave" is not available, use "ondemand".
        # Still not a fatal error if it fails.
        ret = run_on_dut.SetCpuGovernor('ondemand', ignore_status=True)
      # TODO(denik): Run comparison test for 'powersave' and 'ondemand'
      # on scarlet and kevin64.
      # We might have to consider reducing freq manually to the min
      # if it helps to reduce waiting time.
      wait_time = run_on_dut.WaitCooldown()
      cros_machine.AddCooldownWaitTime(wait_time)

    # Setup CPU governor for the benchmark run.
    # It overwrites the previous governor settings.
    governor = self.dut_config['governor']
    # FIXME(denik): Pass online cores to governor setup.
    run_on_dut.SetCpuGovernor(governor, ignore_status=False)

    # Disable Turbo and Setup CPU freq should ALWAYS proceed governor setup
    # since governor may change:
    # - frequency;
    # - turbo/boost.
    run_on_dut.DisableTurbo()
    run_on_dut.SetupCpuFreq(online_cores)
    # FIXME(denik): Currently we are not recovering the previous cpufreq
    # settings since we do reboot/setup every time anyway.
    # But it may change in the future and then we have to recover the
    # settings.

    # DUT setup is done. Start a fresh new shiny UI.
    run_on_dut.StartUI()

  def Test_That_Run(self, machine, label, benchmark, test_args, profiler_args):
    """Run the test_that test.."""
    options = ''
    if label.board:
      options += ' --board=%s' % label.board
    if test_args:
      options += ' %s' % test_args
    if profiler_args:
      self.logger.LogFatal('test_that does not support profiler.')
    command = 'rm -rf /usr/local/autotest/results/*'
    self._ce.CrosRunCommand(
        command, machine=machine, chromeos_root=label.chromeos_root)

    autotest_dir = AUTOTEST_DIR
    if label.autotest_path != '':
      autotest_dir = label.autotest_path

    autotest_dir_arg = '--autotest_dir %s' % autotest_dir
    # For non-telemetry tests, specify an autotest directory only if the
    # specified directory is different from default (crosbug.com/679001).
    if autotest_dir == AUTOTEST_DIR:
      autotest_dir_arg = ''

    command = (('%s %s --fast '
                '%s %s %s') % (TEST_THAT_PATH, autotest_dir_arg, options,
                               machine, benchmark.test_name))
    if self.log_level != 'verbose':
      self.logger.LogOutput('Running test.')
      self.logger.LogOutput('CMD: %s' % command)
    # Use --no-ns-pid so that cros_sdk does not create a different
    # process namespace and we can kill process created easily by
    # their process group.
    return self._ce.ChrootRunCommandWOutput(
        label.chromeos_root,
        command,
        command_terminator=self._ct,
        cros_sdk_options='--no-ns-pid')

  def DownloadResult(self, label, task_id):
    gsutil_cmd = os.path.join(label.chromeos_root, GS_UTIL)
    result_dir = 'gs://chromeos-autotest-results/swarming-%s' % task_id
    download_path = os.path.join(label.chromeos_root, 'chroot/tmp')
    ls_command = '%s ls %s' % (gsutil_cmd,
                               os.path.join(result_dir, 'autoserv_test'))
    cp_command = '%s -mq cp -r %s %s' % (gsutil_cmd, result_dir, download_path)

    # Server sometimes will not be able to generate the result directory right
    # after the test. Will try to access this gs location every 60s for
    # RETRY_LIMIT mins.
    t = 0
    RETRY_LIMIT = 10
    while t < RETRY_LIMIT:
      t += 1
      status = self._ce.RunCommand(ls_command, print_to_console=False)
      if status == 0:
        break
      if t < RETRY_LIMIT:
        self.logger.LogOutput('Result directory not generated yet, '
                              'retry (%d) in 60s.' % t)
        time.sleep(60)
      else:
        self.logger.LogOutput('No result directory for task %s' % task_id)
        return status

    # Wait for 60s to make sure server finished writing to gs location.
    time.sleep(60)

    status = self._ce.RunCommand(cp_command)
    if status != 0:
      self.logger.LogOutput('Cannot download results from task %s' % task_id)
    else:
      self.logger.LogOutput('Result downloaded for task %s' % task_id)
    return status

  def Skylab_Run(self, label, benchmark, test_args, profiler_args):
    """Run the test via skylab.."""
    options = ''
    if label.board:
      options += '-board=%s' % label.board
    if label.build:
      options += ' -image=%s' % label.build
    # TODO: now only put toolchain pool here, user need to be able to specify
    # which pool to use. Need to request feature to not use this option at all.
    options += ' -pool=toolchain'
    if benchmark.suite == 'telemetry_Crosperf':
      if test_args:
        # Strip double quotes off args (so we can wrap them in single
        # quotes, to pass through to Telemetry).
        if test_args[0] == '"' and test_args[-1] == '"':
          test_args = test_args[1:-1]
      if profiler_args:
        test_args += GetProfilerArgs(profiler_args)
      test_args += ' run_local={} test={}'.format(
          benchmark.run_local,
          benchmark.test_name,
      )
    else:
      if profiler_args:
        self.logger.LogFatal('Client tests do not support profiler.')
    if test_args:
      options += ' -test-args="%s"' % test_args

    dimensions = ''
    for dut in label.remote:
      dimensions += ' -dim dut_name:%s' % dut.rstrip('.cros')

    command = (('%s create-test%s %s %s') % \
              (SKYLAB_PATH, dimensions, options, benchmark.test_name))

    if self.log_level != 'verbose':
      self.logger.LogOutput('Starting skylab test.')
      self.logger.LogOutput('CMD: %s' % command)
    ret_tup = self._ce.RunCommandWOutput(command, command_terminator=self._ct)

    if ret_tup[0] != 0:
      self.logger.LogOutput('Skylab test not created successfully.')
      return ret_tup

    # Std output of the command will look like:
    # Created request at https://ci.chromium.org/../cros_test_platform/b12345
    # We want to parse it and get the id number of the task, which is the
    # number in the very end of the link address.
    task_id = ret_tup[1].strip().split('b')[-1]

    command = ('skylab wait-task %s' % task_id)
    if self.log_level != 'verbose':
      self.logger.LogOutput('Waiting for skylab test to finish.')
      self.logger.LogOutput('CMD: %s' % command)

    ret_tup = self._ce.RunCommandWOutput(command, command_terminator=self._ct)

    # The output of `wait-task` command will be a combination of verbose and a
    # json format result in the end. The json result looks like this:
    # {"task-result":
    #   {"name":"Test Platform Invocation",
    #    "state":"", "failure":false, "success":true,
    #    "task-run-id":"12345",
    #    "task-run-url":"https://ci.chromium.org/.../cros_test_platform/b12345",
    #    "task-logs-url":""
    #    },
    #  "stdout":"",
    #  "child-results":
    #    [{"name":"graphics_WebGLAquarium",
    #      "state":"", "failure":false, "success":true, "task-run-id":"",
    #      "task-run-url":"https://chromeos-swarming.appspot.com/task?id=1234",
    #      "task-logs-url":"https://stainless.corp.google.com/1234/"}
    #    ]
    # }
    # We need the task id of the child-results to download result.
    output = json.loads(ret_tup[1].split('\n')[-1])
    output = output['child-results'][0]
    if output['success']:
      task_id = output['task-run-url'].split('=')[-1]
      if self.DownloadResult(label, task_id) == 0:
        result_dir = '\nResults placed in tmp/swarming-%s\n' % task_id
        return (ret_tup[0], result_dir, ret_tup[2])
    return ret_tup

  def RemoveTelemetryTempFile(self, machine, chromeos_root):
    filename = 'telemetry@%s' % machine
    fullname = os.path.join(chromeos_root, 'chroot', 'tmp', filename)
    if os.path.exists(fullname):
      os.remove(fullname)

  def Telemetry_Crosperf_Run(self, machine, label, benchmark, test_args,
                             profiler_args):
    if not os.path.isdir(label.chrome_src):
      self.logger.LogFatal('Cannot find chrome src dir to'
                           ' run telemetry: %s' % label.chrome_src)

    # Check for and remove temporary file that may have been left by
    # previous telemetry runs (and which might prevent this run from
    # working).
    self.RemoveTelemetryTempFile(machine, label.chromeos_root)

    # For telemetry runs, we can use the autotest copy from the source
    # location. No need to have one under /build/<board>.
    autotest_dir_arg = '--autotest_dir %s' % AUTOTEST_DIR
    if label.autotest_path != '':
      autotest_dir_arg = '--autotest_dir %s' % label.autotest_path

    profiler_args = GetProfilerArgs(profiler_args)
    # --fast avoids unnecessary copies of syslogs.
    fast_arg = '--fast'
    args_string = ''
    if test_args:
      # Strip double quotes off args (so we can wrap them in single
      # quotes, to pass through to Telemetry).
      if test_args[0] == '"' and test_args[-1] == '"':
        test_args = test_args[1:-1]
      args_string = "test_args='%s'" % test_args

    top_interval = self.dut_config['top_interval']
    cmd = ('{} {} {} --board={} --args="{} run_local={} test={} '
           'turbostat={} top_interval={} {}" {} telemetry_Crosperf'.format(
               TEST_THAT_PATH, autotest_dir_arg, fast_arg, label.board,
               args_string, benchmark.run_local, benchmark.test_name,
               benchmark.turbostat, top_interval, profiler_args, machine))

    # Use --no-ns-pid so that cros_sdk does not create a different
    # process namespace and we can kill process created easily by their
    # process group.
    chrome_root_options = ('--no-ns-pid '
                           '--chrome_root={} --chrome_root_mount={} '
                           'FEATURES="-usersandbox" '
                           'CHROME_ROOT={}'.format(label.chrome_src,
                                                   CHROME_MOUNT_DIR,
                                                   CHROME_MOUNT_DIR))
    if self.log_level != 'verbose':
      self.logger.LogOutput('Running test.')
      self.logger.LogOutput('CMD: %s' % cmd)
    return self._ce.ChrootRunCommandWOutput(
        label.chromeos_root,
        cmd,
        command_terminator=self._ct,
        cros_sdk_options=chrome_root_options)

  def CommandTerminator(self):
    return self._ct

  def Terminate(self):
    self._ct.Terminate()


class MockSuiteRunner(object):
  """Mock suite runner for test."""

  def __init__(self):
    self._true = True

  def Run(self, *_args):
    if self._true:
      return [0, '', '']
    else:
      return [0, '', '']
