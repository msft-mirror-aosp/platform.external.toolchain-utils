#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from utils import command_executer

TEST_THAT_PATH = '/usr/bin/test_that'
CHROME_MOUNT_DIR = '/tmp/chrome_root'

def GetProfilerArgs (benchmark):
  if benchmark.perf_args:
    perf_args_list = benchmark.perf_args.split(" ")
    perf_args_list = [perf_args_list[0]] + ["-a"] + perf_args_list[1:]
    perf_args = " ".join(perf_args_list)
    if not perf_args_list[0] in ["record", "stat"]:
      raise Exception("perf_args must start with either record or stat")
    extra_test_args = ["profiler=custom_perf",
                       ("profiler_args=\"'%s'\"" %
                        perf_args)]
    return " ".join(extra_test_args)
  else:
    return ""


class SuiteRunner(object):
  """ This defines the interface from crosperf to test script.
  """

  def __init__(self, logger_to_use=None):
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self._ct = command_executer.CommandTerminator()

  def Run(self, machine, label, benchmark, test_args):
    self.PinGovernorExecutionFrequencies(machine, label.chromeos_root)
    if benchmark.suite == "telemetry":
      return self.Telemetry_Run(machine, label, benchmark)
    elif benchmark.suite == "telemetry_Crosperf":
      return self.Telemetry_Crosperf_Run(machine, label, benchmark)
    elif benchmark.use_test_that:
      return self.Test_That_Run(machine, label, benchmark, test_args)
    else:
      return self.Pyauto_Run(machine, label, benchmark, test_args)

  def GetHighestStaticFrequency(self, machine_name, chromeos_root):
    """ Gets the highest static frequency for the specified machine
    """
    get_avail_freqs = ("cat /sys/devices/system/cpu/cpu0/cpufreq/"
                       "scaling_available_frequencies")
    ret, freqs_str, _ = self._ce.CrosRunCommand(
        get_avail_freqs, return_output=True, machine=machine_name,
        chromeos_root=chromeos_root)
    self._logger.LogFatalIf(ret, "Could not get available frequencies "
                            "from machine: %s" % machine_name)
    freqs = freqs_str.split()
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

  def Pyauto_Run(self, machine, label, benchmark, test_args):
    """Run the run_remote_test."""
    options = ""
    if label.board:
      options += " --board=%s" % label.board
    if test_args:
      options += " %s" % test_args
    command = "rm -rf /usr/local/autotest/results/*"
    self._ce.CrosRunCommand(command, machine=machine, username="root",
                            chromeos_root=label.chromeos_root)

    # We do this because PyAuto tests leave the machine in weird states.
    # Rebooting between iterations has proven to help with this.
    self.RebootMachine(machine, label.chromeos_root)

    command = ("./run_remote_tests.sh --use_emerged --remote=%s %s %s" %
               (machine, options, benchmark.test_name))
    return self._ce.ChrootRunCommand(label.chromeos_root,
                                     command,
                                     True,
                                     self._ct)

  def Test_That_Run(self, machine, label, benchmark, test_args):
    """Run the test_that test.."""
    options = ""
    if label.board:
      options += " --board=%s" % label.board
    if test_args:
      options += " %s" % test_args
    command = "rm -rf /usr/local/autotest/results/*"
    self._ce.CrosRunCommand(command, machine=machine, username="root",
                            chromeos_root=label.chromeos_root)

    # We do this because PyAuto tests leave the machine in weird states.
    # Rebooting between iterations has proven to help with this.
    self.RebootMachine(machine, label.chromeos_root)

    command = ("%s %s %s %s" %
               (TEST_THAT_PATH, options, machine, benchmark.test_name))
    return self._ce.ChrootRunCommand(label.chromeos_root,
                                     command,
                                     True,
                                     self._ct)


  def Telemetry_Crosperf_Run (self, machine, label, benchmark):
    if not os.path.isdir(label.chrome_src):
      self._logger.LogFatal("Cannot find chrome src dir to"
                            " run telemetry.")

    profiler_args = GetProfilerArgs (benchmark)
    chrome_root_options = ""

    # If chrome_src is outside the chroot, mount it when entering the
    # chroot.
    if label.chrome_src.find(label.chromeos_root) == -1:
      chrome_root_options = (" --chrome_root={0} --chrome_root_mount={1} "
                             " FEATURES=\"-usersandbox\" "
                             "CHROME_ROOT={2}".format(label.chrome_src,
                                                      CHROME_MOUNT_DIR,
                                                      CHROME_MOUNT_DIR))

    cmd = ('{0} --board={1} --args="iterations={2} test={3} '
           '{4}" {5} telemetry_Crosperf'.format(TEST_THAT_PATH,
                                                label.board,
                                                benchmark.iterations,
                                                benchmark.test_name,
                                                profiler_args,
                                                machine))
    return self._ce.ChrootRunCommand (label.chromeos_root,
                                      cmd,
                                      return_output=True,
                                      command_terminator=self._ct,
                                      cros_sdk_options=chrome_root_options)


  def Telemetry_Run(self, machine, label, benchmark):
    if not os.path.isdir(label.chrome_src):
      self._logger.LogFatal("Cannot find chrome src dir to"
                                        " run telemetry.")
    rsa_key = os.path.join(label.chromeos_root,
        "src/scripts/mod_for_test_scripts/ssh_keys/testing_rsa")

    cmd = ("cd {0} && "
           "./tools/perf/run_measurement "
           "--browser=cros-chrome "
           "--output-format=csv "
           "--remote={1} "
           "--identity {2} "
           "{3} {4}".format(label.chrome_src, machine,
                            rsa_key,
                            benchmark.test_name,
                            benchmark.test_args))
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
