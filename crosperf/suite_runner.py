# -*- coding: utf-8 -*-
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""SuiteRunner defines the interface from crosperf to test script."""

from __future__ import print_function

import os
import re
import shlex
import time

from cros_utils import command_executer

TEST_THAT_PATH = '/usr/bin/test_that'
# TODO: Need to check whether Skylab is installed and set up correctly.
SKYLAB_PATH = '/usr/local/bin/skylab'
GS_UTIL = 'chromium/tools/depot_tools/gsutil.py'
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
    self._ct = cmd_term or command_executer.CommandTerminator()
    self.enable_aslr = enable_aslr
    self.dut_config = dut_config

  def Run(self, machine, label, benchmark, test_args, profiler_args):
    for i in range(0, benchmark.retries + 1):
      if label.skylab:
        # TODO: need to migrate DisableASLR and PinGovernorExecutionFrequencies
        # since in skylab mode, we may not know the DUT until one is assigned
        # to the test. For telemetry_Crosperf run, we can move them into the
        # server test script, for client runs, need to figure out wrapper to do
        # it before running.
        ret_tup = self.Skylab_Run(label, benchmark, test_args, profiler_args)
      else:
        # Unless the user turns on ASLR in the flag, we first disable ASLR
        # before running the benchmarks
        if not self.enable_aslr:
          self.DisableASLR(machine, label.chromeos_root)
        self.PinGovernorExecutionFrequencies(machine, label.chromeos_root)
        self.SetupCpuUsage(machine, label.chromeos_root)
        if benchmark.suite == 'telemetry_Crosperf':
          self.DecreaseWaitTime(machine, label.chromeos_root)
          ret_tup = self.Telemetry_Crosperf_Run(machine, label, benchmark,
                                                test_args, profiler_args)
        else:
          ret_tup = self.Test_That_Run(machine, label, benchmark, test_args,
                                       profiler_args)

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

  def DisableASLR(self, machine_name, chromeos_root):
    disable_aslr = ('set -e && '
                    'stop ui; '
                    'if [[ -e /proc/sys/kernel/randomize_va_space ]]; then '
                    '  echo 0 > /proc/sys/kernel/randomize_va_space; '
                    'fi; '
                    'start ui ')
    self.logger.LogOutput('Disable ASLR for %s' % machine_name)
    self._ce.CrosRunCommand(
        disable_aslr, machine=machine_name, chromeos_root=chromeos_root)

  def PinGovernorExecutionFrequencies(self, machine_name, chromeos_root):
    """Setup Intel CPU frequency.

    Manages the cpu governor and other performance settings.
    Includes support for setting cpu frequency to a static value.
    """
    # pyformat: disable
    set_cpu_freq = (
        # Disable Intel Opportunistic Processor
        # Commented out because wrmsr requires kernel change
        # to enable white-listed write access to msr 0x199.
        # See Intel 64 and IA-32 Archtectures
        # Software Developer's Manual, 14.3.2.2.
        #'awk \'$1 ~ /^processor/ { print $NF }\' /proc/cpuinfo '
        #'   | while read c; do '
        # 'iotools wrmsr $c 0x199 $(printf "0x%x\n" $(( (1 << 32) '
        # '   | $(iotools rdmsr $c 0x199) )));'
        #'done;'
        # Set up intel_pstate governor to performance if enabled.
        'for f in `ls -d /sys/devices/system/cpu/cpu*/cpufreq 2>/dev/null`; do '
        # Skip writing scaling_governor if cpu is not online.
        ' [[ -e ${f/cpufreq/online} ]] && grep -q 0 ${f/cpufreq/online} '
        '   && continue; '
        # The cpu is online, can update.
        ' cd $f; '
        ' if [[ -e scaling_governor ]]; then '
        '  echo performance > scaling_governor; fi; '
        #
        # Uncomment rest of lines to enable setting frequency by crosperf.
        # It sets the cpu to the second highest supported frequency.
        #'val=0; '
        #'if [[ -e scaling_available_frequencies ]]; then '
        # pylint: disable=line-too-long
        #'  val=`cat scaling_available_frequencies | tr " " "\\n" | sort -n -b -r`; '
        #'else '
        #'  val=`cat scaling_max_freq | tr " " "\\n" | sort -n -b -r`; fi ; '
        #'set -- $val; '
        #'highest=$1; '
        #'if [[ $# -gt 1 ]]; then '
        #'  case $highest in *1000) highest=$2;; esac; '
        #'fi ;'
        #'echo $highest > scaling_max_freq; '
        #'echo $highest > scaling_min_freq; '
        'done; '
        # Disable Turbo in Intel pstate driver
        # no_turbo should follow governor setup.
        # Otherwise it can be overwritten.
        'if [[ -e /sys/devices/system/cpu/intel_pstate/no_turbo ]]; then '
        '  if grep -q 0 /sys/devices/system/cpu/intel_pstate/no_turbo;  then '
        '    echo -n 1 > /sys/devices/system/cpu/intel_pstate/no_turbo; '
        '  fi; '
        'fi; ')
    # pyformat: enable
    if self.log_level == 'average':
      self.logger.LogOutput(
          'Pinning governor execution frequencies for %s' % machine_name)
    ret = self._ce.CrosRunCommand(
        set_cpu_freq, machine=machine_name, chromeos_root=chromeos_root)
    self.logger.LogFatalIf(
        ret, 'Could not pin frequencies on machine: %s' % machine_name)

  def SetupCpuUsage(self, machine_name, chromeos_root):
    """Setup CPU usage.

    Based on self.dut_config['cpu_usage'] configure CPU cores
    utilization.
    """

    if (self.dut_config['cpu_usage'] == 'big_only' or
        self.dut_config['cpu_usage'] == 'little_only'):
      ret, arch, _ = self._ce.CrosRunCommandWOutput(
          'uname -m', machine=machine_name, chromeos_root=chromeos_root)
      self.logger.LogFatalIf(
          ret, 'Setup CPU failed. Could not retrieve architecture model.')

      if arch.lower().startswith('arm') or arch.lower().startswith('aarch64'):
        self.SetupArmCores(machine_name, chromeos_root)

  def SetupArmCores(self, machine_name, chromeos_root):
    """Setup ARM big/little cores."""

    # CPU implemeters/part numbers of big/LITTLE CPU.
    # Format: dict(CPU implementer: set(CPU part numbers))
    LITTLE_CORES = {
        '0x41': {
            '0xd01',  # Cortex A32
            '0xd03',  # Cortex A53
            '0xd04',  # Cortex A35
            '0xd05',  # Cortex A55
        },
    }
    BIG_CORES = {
        '0x41': {
            '0xd07',  # Cortex A57
            '0xd08',  # Cortex A72
            '0xd09',  # Cortex A73
            '0xd0a',  # Cortex A75
            '0xd0b',  # Cortex A76
        },
    }

    # Values of CPU Implementer and CPU part number are exposed by cpuinfo.
    # Format:
    # =================
    # processor       : 0
    # model name      : ARMv8 Processor rev 4 (v8l)
    # BogoMIPS        : 48.00
    # Features        : half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
    # CPU implementer : 0x41
    # CPU architecture: 8
    # CPU variant     : 0x0
    # CPU part        : 0xd03
    # CPU revision    : 4

    ret, cpuinfo, _ = self._ce.CrosRunCommandWOutput(
        'cat /proc/cpuinfo', machine=machine_name, chromeos_root=chromeos_root)
    self.logger.LogFatalIf(ret,
                           'Setup ARM CPU failed. Could not retrieve cpuinfo.')

    # List of all CPU cores: 0, 1, ..
    proc_matches = re.findall(r'^processor\s*: (\d+)$', cpuinfo, re.MULTILINE)
    # List of all corresponding CPU implementers
    impl_matches = re.findall(r'^CPU implementer\s*: (0x[\da-f]+)$', cpuinfo,
                              re.MULTILINE)
    # List of all corresponding CPU part numbers
    part_matches = re.findall(r'^CPU part\s*: (0x[\da-f]+)$', cpuinfo,
                              re.MULTILINE)
    assert len(proc_matches) == len(impl_matches)
    assert len(part_matches) == len(impl_matches)

    all_cores = set(proc_matches)
    dut_big_cores = {
        core
        for core, impl, part in zip(proc_matches, impl_matches, part_matches)
        if impl in BIG_CORES and part in BIG_CORES[impl]
    }
    dut_lit_cores = {
        core
        for core, impl, part in zip(proc_matches, impl_matches, part_matches)
        if impl in LITTLE_CORES and part in LITTLE_CORES[impl]
    }

    if self.dut_config['cpu_usage'] == 'big_only':
      cores_to_enable = dut_big_cores
      cores_to_disable = all_cores - dut_big_cores
    elif self.dut_config['cpu_usage'] == 'little_only':
      cores_to_enable = dut_lit_cores
      cores_to_disable = all_cores - dut_lit_cores
    else:
      self.logger.LogError(
          'cpu_usage=%s is not supported on ARM.\n'
          'Ignore ARM CPU setup and continue.' % self.dut_config['cpu_usage'])
      return

    if cores_to_enable:
      cmd_enable_cores = ('echo 1 | tee /sys/devices/system/cpu/cpu{%s}/online'
                          % ','.join(sorted(cores_to_enable)))

      cmd_disable_cores = ''
      if cores_to_disable:
        cmd_disable_cores = (
            'echo 0 | tee /sys/devices/system/cpu/cpu{%s}/online' % ','.join(
                sorted(cores_to_disable)))

      ret = self._ce.CrosRunCommand(
          '; '.join([cmd_enable_cores, cmd_disable_cores]),
          machine=machine_name,
          chromeos_root=chromeos_root)
      self.logger.LogFatalIf(
          ret, 'Setup ARM CPU failed. Could not retrieve cpuinfo.')
    else:
      # If there are no cores enabled by dut_config then configuration
      # is invalid for current platform and should be ignored.
      self.logger.LogError(
          '"cpu_usage" is invalid for targeted platform.\n'
          'dut_config[cpu_usage]=%s\n'
          'dut big cores: %s\n'
          'dut little cores: %s\n'
          'Ignore ARM CPU setup and continue.' % (self.dut_config['cpu_usage'],
                                                  dut_big_cores, dut_lit_cores))

  def DecreaseWaitTime(self, machine_name, chromeos_root):
    """Change the ten seconds wait time for pagecycler to two seconds."""
    FILE = '/usr/local/telemetry/src/tools/perf/page_sets/page_cycler_story.py'
    ret = self._ce.CrosRunCommand(
        'ls ' + FILE, machine=machine_name, chromeos_root=chromeos_root)
    self.logger.LogFatalIf(
        ret, 'Could not find {} on machine: {}'.format(FILE, machine_name))

    if not ret:
      sed_command = 'sed -i "s/_TTI_WAIT_TIME = 10/_TTI_WAIT_TIME = 2/g" '
      ret = self._ce.CrosRunCommand(
          sed_command + FILE, machine=machine_name, chromeos_root=chromeos_root)
      self.logger.LogFatalIf(
          ret, 'Could not modify {} on machine: {}'.format(FILE, machine_name))

  def RestartUI(self, machine_name, chromeos_root):
    command = 'stop ui; sleep 5; start ui'
    self._ce.CrosRunCommand(
        command, machine=machine_name, chromeos_root=chromeos_root)

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

    # We do this because some tests leave the machine in weird states.
    # Rebooting between iterations has proven to help with this.
    # But the beep is anoying, we will try restart ui.
    self.RestartUI(machine, label.chromeos_root)

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
    # after the test. Will try to access this gs location every 60s for 5 mins.
    t = 0
    RETRY_LIMIT = 5
    while t < RETRY_LIMIT:
      self.logger.LogOutput('Downloading test results.')
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
    return status

  def Skylab_Run(self, label, benchmark, test_args, profiler_args):
    """Run the test via skylab.."""
    # Skylab by default uses cros_test_platform to start test.
    # We don't use it for now since we want to directly interact with dut.
    options = '-bb=false'

    if benchmark.suite != 'telemetry_Crosperf':
      options += ' -client-test'
    if label.board:
      options += ' -board=%s' % label.board
    if label.build:
      options += ' -image=%s' % label.build
    # TODO: now only put quota pool here, user need to be able to specify which
    # pool to use. Need to request feature to not use this option at all.
    options += ' -pool=DUT_POOL_QUOTA'
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

    command = (('%s create-test %s %s %s') % \
              (SKYLAB_PATH, dimensions, options, benchmark.test_name))

    if self.log_level != 'verbose':
      self.logger.LogOutput('Starting skylab test.')
      self.logger.LogOutput('CMD: %s' % command)
    ret_tup = self._ce.RunCommandWOutput(command, command_terminator=self._ct)

    if ret_tup[0] != 0:
      self.logger.LogOutput('Skylab test not created successfully.')
      return ret_tup

    # Std output of the command will look like:
    # Created Swarming task https://chromeos-swarming.appspot.com/task?id=12345
    # We want to parse it and get the id number of the task.
    task_id = ret_tup[1].strip().split('id=')[1]

    command = ('skylab wait-task -bb=false %s' % (task_id))
    if self.log_level != 'verbose':
      self.logger.LogOutput('Waiting for skylab test to finish.')
      self.logger.LogOutput('CMD: %s' % command)

    ret_tup = self._ce.RunCommandWOutput(command, command_terminator=self._ct)
    if '"success":true' in ret_tup[1]:
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

    cmd = ('{} {} {} --board={} --args="{} run_local={} test={} '
           'turbostat={} {}" {} telemetry_Crosperf'.format(
               TEST_THAT_PATH, autotest_dir_arg, fast_arg, label.board,
               args_string, benchmark.run_local, benchmark.test_name,
               benchmark.turbostat, profiler_args, machine))

    # Use --no-ns-pid so that cros_sdk does not create a different
    # process namespace and we can kill process created easily by their
    # process group.
    chrome_root_options = ('--no-ns-pid '
                           '--chrome_root={} --chrome_root_mount={} '
                           "FEATURES=\"-usersandbox\" "
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
