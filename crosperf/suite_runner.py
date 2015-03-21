#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time
import shlex

from utils import command_executer

TEST_THAT_PATH = '/usr/bin/test_that'
CHROME_MOUNT_DIR = '/tmp/chrome_root'

def GetProfilerArgs (profiler_args):
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
    idx = arg.find("perf_options=")
    if idx != -1:
      prefix = arg[0:idx]
      suffix = arg[idx + len("perf_options=") + 1 : -1]
      new_arg = prefix + "'" + suffix + "'"
      new_list.append(new_arg)
    else:
      new_list.append(arg)
  args_list = new_list

  return " ".join(args_list)


class SuiteRunner(object):
  """ This defines the interface from crosperf to test script.
  """

  def __init__(self, logger_to_use=None, log_level="verbose", cmd_exec=None,
               cmd_term=None):
    self._logger = logger_to_use
    self.log_level = log_level
    self._ce = cmd_exec or command_executer.GetCommandExecuter(self._logger,
                                                   log_level=self.log_level)
    self._ct = cmd_term or command_executer.CommandTerminator()

  def Run(self, machine, label, benchmark, test_args, profiler_args):
    self.PinGovernorExecutionFrequencies(machine, label.chromeos_root)
    if benchmark.suite == "telemetry":
      return self.Telemetry_Run(machine, label, benchmark, profiler_args)
    elif benchmark.suite == "telemetry_Crosperf":
      return self.Telemetry_Crosperf_Run(machine, label, benchmark,
                                         test_args, profiler_args)
    else:
      return self.Test_That_Run(machine, label, benchmark, test_args,
                                profiler_args)

  def GetHighestStaticFrequency(self, machine_name, chromeos_root):
    """ Gets the highest static frequency for the specified machine
    """
    get_avail_freqs = ("cd /sys/devices/system/cpu/cpu0/cpufreq/; "
                       "if [[ -e scaling_available_frequencies ]]; then "
                       "  cat scaling_available_frequencies; "
                       "else "
                       "  cat scaling_max_freq ; "
                       "fi")
    ret, freqs_str, _ = self._ce.CrosRunCommand(
        get_avail_freqs, return_output=True, machine=machine_name,
        chromeos_root=chromeos_root)
    self._logger.LogFatalIf(ret, "Could not get available frequencies "
                            "from machine: %s" % machine_name)
    freqs = freqs_str.split()
    ## When there is no scaling_available_frequencies file,
    ## we have only 1 choice.
    if len(freqs) == 1:
      return freqs[0]
    # The dynamic frequency ends with a "1000". So, ignore it if found.
    if freqs[0].endswith("1000"):
      return freqs[1]
    else:
      return freqs[0]

  def PinGovernorExecutionFrequencies(self, machine_name, chromeos_root):
    """ Set min and max frequencies to max static frequency
    """
    highest_freq = self.GetHighestStaticFrequency(machine_name, chromeos_root)
    BASH_FOR = "for f in {list}; do {body}; done"
    CPUFREQ_DIRS = "/sys/devices/system/cpu/cpu*/cpufreq/"
    change_max_freq = BASH_FOR.format(list=CPUFREQ_DIRS + "scaling_max_freq",
                                      body="echo %s > $f" % highest_freq)
    change_min_freq = BASH_FOR.format(list=CPUFREQ_DIRS + "scaling_min_freq",
                                      body="echo %s > $f" % highest_freq)
    change_perf_gov = BASH_FOR.format(list=CPUFREQ_DIRS + "scaling_governor",
                                      body="echo performance > $f")
    if self.log_level == "average":
      self._logger.LogOutput("Pinning governor execution frequencies for %s"
                           % machine_name)
    ret = self._ce.CrosRunCommand(" && ".join(("set -e ",
                                               change_max_freq,
                                               change_min_freq,
                                               change_perf_gov)),
                                  machine=machine_name,
                                  chromeos_root=chromeos_root)
    self._logger.LogFatalIf(ret, "Could not pin frequencies on machine: %s"
                            % machine_name)

  def RebootMachine(self, machine_name, chromeos_root):
    command = "reboot && exit"
    self._ce.CrosRunCommand(command, machine=machine_name,
                      chromeos_root=chromeos_root)
    time.sleep(60)
    # Whenever we reboot the machine, we need to restore the governor settings.
    self.PinGovernorExecutionFrequencies(machine_name, chromeos_root)

  def Test_That_Run(self, machine, label, benchmark, test_args, profiler_args):
    """Run the test_that test.."""
    options = ""
    if label.board:
      options += " --board=%s" % label.board
    if test_args:
      options += " %s" % test_args
    if profiler_args:
      self._logger.LogFatal("test_that does not support profiler.")
    command = "rm -rf /usr/local/autotest/results/*"
    self._ce.CrosRunCommand(command, machine=machine, username="root",
                            chromeos_root=label.chromeos_root)

    # We do this because some tests leave the machine in weird states.
    # Rebooting between iterations has proven to help with this.
    self.RebootMachine(machine, label.chromeos_root)

    command = ("%s %s %s %s" %
               (TEST_THAT_PATH, options, machine, benchmark.test_name))
    if self.log_level != "verbose":
      self._logger.LogOutput("Running test.")
      self._logger.LogOutput("CMD: %s" % command)
    return self._ce.ChrootRunCommand(label.chromeos_root,
                                     command,
                                     True,
                                     self._ct)


  def Telemetry_Crosperf_Run (self, machine, label, benchmark, test_args,
                              profiler_args):
    if not os.path.isdir(label.chrome_src):
      self._logger.LogFatal("Cannot find chrome src dir to"
                            " run telemetry: %s" % label.chrome_src)

    profiler_args = GetProfilerArgs (profiler_args)
    fast_arg = ""
    if not profiler_args:
      # --fast works unless we are doing profiling (autotest limitation).
      # --fast avoids unnecessary copies of syslogs.
      fast_arg = "--fast"
    args_string = ""
    if test_args:
      # Strip double quotes off args (so we can wrap them in single
      # quotes, to pass through to Telemetry).
      if test_args[0] == '"' and test_args[-1] == '"':
        test_args = test_args[1:-1]
      args_string = "test_args='%s'" % test_args
    cmd = ('{} {} --board={} --args="{} test={} '
           '{}" {} telemetry_Crosperf'.format(TEST_THAT_PATH,
                                              fast_arg,
                                              label.board,
                                              args_string,
                                              benchmark.test_name,
                                              profiler_args,
                                              machine))

    chrome_root_options = ""
    chrome_root_options = (" --chrome_root={} --chrome_root_mount={} "
                           " FEATURES=\"-usersandbox\" "
                           "CHROME_ROOT={}".format(label.chrome_src,
                                                    CHROME_MOUNT_DIR,
                                                    CHROME_MOUNT_DIR))
    if self.log_level != "verbose":
      self._logger.LogOutput("Running test.")
      self._logger.LogOutput("CMD: %s" % cmd)
    return self._ce.ChrootRunCommand (label.chromeos_root,
                                      cmd,
                                      return_output=True,
                                      command_terminator=self._ct,
                                      cros_sdk_options=chrome_root_options)


  def Telemetry_Run(self, machine, label, benchmark, profiler_args):
    telemetry_run_path = ""
    if not os.path.isdir(label.chrome_src):
      self._logger.LogFatal("Cannot find chrome src dir to"
                            " run telemetry.")
    else:
      telemetry_run_path = os.path.join(label.chrome_src, "src/tools/perf")
      if not os.path.exists(telemetry_run_path):
        self._logger.LogFatal("Cannot find %s directory." % telemetry_run_path)

    if profiler_args:
      self._logger.LogFatal("Telemetry does not support the perf profiler.")

    rsa_key = os.path.join(label.chromeos_root,
        "src/scripts/mod_for_test_scripts/ssh_keys/testing_rsa")

    cmd = ("cd {0} && "
           "./run_measurement "
           "--browser=cros-chrome "
           "--output-format=csv "
           "--remote={1} "
           "--identity {2} "
           "{3} {4}".format(telemetry_run_path, machine,
                            rsa_key,
                            benchmark.test_name,
                            benchmark.test_args))
    if self.log_level != "verbose":
      self._logger.LogOutput("Running test.")
      self._logger.LogOutput("CMD: %s" % cmd)
    return self._ce.RunCommand(cmd, return_output=True,
                               print_to_console=False)

  def Terminate(self):
    self._ct.Terminate()


class MockSuiteRunner(object):
  def __init__(self):
    self._true = True

  def Run(self, *_args):
    if self._true:
      return ["", "", 0]
    else:
      return ["", "", 0]
