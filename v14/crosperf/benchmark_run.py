#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import datetime
import os
import re
import threading
import time
from results_cache import Result
from utils import command_executer
from utils import logger


class BenchmarkRun(threading.Thread):
  def __init__(self, autotest_name, autotest_args, chromeos_root,
               chromeos_image, board, iteration, image_checksum,
               exact_remote, rerun, rerun_if_failed,
               outlier_range, machine_manager, cache, autotest_runner,
               perf_processor):
    self.autotest_name = autotest_name
    self.autotest_args = autotest_args
    self.chromeos_root = chromeos_root
    self.chromeos_image = chromeos_image
    self.board = board
    self.iteration = iteration
    if not image_checksum:
      raise Exception("Checksum shouldn't be None")
    self.image_checksum = image_checksum
    self.results = {}
    threading.Thread.__init__(self)
    self.terminate = False
    self.retval = None
    self.status = "PENDING"
    self.run_completed = False
    self.exact_remote = exact_remote
    self.rerun = rerun
    self.rerun_if_failed = rerun_if_failed
    self.outlier_range = outlier_range
    self.machine_manager = machine_manager
    self.cache = cache
    self.autotest_runner = autotest_runner
    self.perf_processor = perf_processor

  def MeanExcludingOutliers(self, array, outlier_range):
    """Return the arithmetic mean excluding outliers."""
    mean = sum(array) / len(array)
    array2 = []

    for v in array:
      if mean != 0 and abs(v - mean) / mean < outlier_range:
        array2.append(v)

    if array2:
      return sum(array2) / len(array2)
    else:
      return mean

  def ParseResults(self, output):
    p = re.compile("^-+.*?^-+", re.DOTALL | re.MULTILINE)
    matches = p.findall(output)
    for i in range(len(matches)):
      results = matches[i]
      results_dict = {}
      for line in results.splitlines()[1:-1]:
        mo = re.match("(.*\S)\s+\[\s+(PASSED|FAILED)\s+\]", line)
        if mo:
          results_dict[mo.group(1)] = mo.group(2)
          continue
        mo = re.match("(.*\S)\s+(.*)", line)
        if mo:
          results_dict[mo.group(1)] = mo.group(2)

      return results_dict
    return {}

  def GetLabel(self):
    ret = "%s %s remote:%s" % (self.chromeos_image, self.autotest_name,
                               self.remote)
    return ret

  def RunCached(self):
    if self.rerun:
      self._logger.LogOutput("rerun set. Not using cached results.")
      return None

    result = self.cache.Read()

    if not result:
      self._logger.LogOutput("Cache miss. AM going to run: %s for: %s" %
                             (self.autotest_name, self.chromeos_image))
      return None

    self._logger.LogOutput(result.out)

    if self.rerun_if_failed and result.retval:
      self._logger.LogOutput("rerun_if_failed set and existing test "
                             "failed. Rerunning...")
    return result

  def _GetResultsDir(self, output, chromeos_root):
    mo = re.search("Results placed in (\S+)", output)
    if mo:
      result = mo.group(1)
      return os.path.join(chromeos_root, "chroot",
                          result.lstrip("/"))
    return ""

  def run(self):
    self._logger = logger.Logger(os.path.dirname(__file__),
                                 "%s.%s" % (os.path.basename(__file__),
                                            self.name), True)

    machine = None
    try:
      machine = self.AcquireMachine()
      if not machine:
        raise Exception("Could not acquire machine.")
      self.remote = machine.name

      self.cache.Init(self.image_checksum, self.autotest_name,
                      self.iteration, self.autotest_args,
                      machine.name, self.exact_remote, self._logger)

      self.status = "WAITING"

      result = self.RunCached()
      if not result:
        result = self.RunTest(machine)
        cache_hit = False
      else:
        cache_hit = True

      if not result.retval:
        self.status = "SUCCEEDED"
      else:
        self.status = "FAILED"

      results_dir = self._GetResultsDir(result.out, self.chromeos_root)
      self.full_name = os.path.basename(results_dir)

      self.results = self.ParseResults(result.out)

      self.perf_processor.StorePerf(self.cache.GetCacheDir(), cache_hit, result,
                                    self.autotest_args, self.chromeos_root,
                                    self.board, results_dir)

      return result.retval
    finally:
      if machine:
        self._logger.LogOutput("Releasing machine: %s" % machine.name)
        self.machine_manager.ReleaseMachine(machine)
        self._logger.LogOutput("Released machine: %s" % machine.name)

  def AcquireMachine(self):
    while True:
      if self.terminate:
        return None
      machine = self.machine_manager.AcquireMachine(self.image_checksum)
      if machine:
        self._logger.LogOutput("%s: Machine %s acquired at %s" %
                               (self.name,
                                machine.name,
                                datetime.datetime.now()))
        break
      else:
        sleep_duration = 10
        time.sleep(sleep_duration)
    return machine

  def RunTest(self, machine):
    if machine.checksum != self.image_checksum:
      self.status = "IMAGING"
      retval = self.machine_manager.ImageMachine(machine.name,
                                                 self.chromeos_root,
                                                 self.chromeos_image,
                                                 self.board)
      if retval:
        raise Exception("Could not image machine: '%s'." % machine.name)
      machine.checksum = self.image_checksum
      machine.image = self.chromeos_image
    self.status = "RUNNING: %s" % self.autotest_name
    [retval, out, err] = self.autotest_runner.Run(machine.name,
                                                  self.chromeos_root,
                                                  self.board,
                                                  self.autotest_name,
                                                  self.autotest_args)
    self.run_completed = True
    result = Result(out, err, retval)

    self.cache.Store(result)
    return result

