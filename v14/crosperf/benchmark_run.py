#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import datetime
import os
import re
import threading
import time
import traceback
from results_cache import Result
from utils import logger

STATUS_FAILED = "FAILED"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_IMAGING = "IMAGING"
STATUS_RUNNING = "RUNNING"
STATUS_WAITING = "WAITING"
STATUS_PENDING = "PENDING"


class BenchmarkRun(threading.Thread):
  def __init__(self, name, benchmark_name, autotest_name, autotest_args,
               label_name, chromeos_root, chromeos_image, board, iteration,
               cache_conditions, outlier_range, profile_counters,
               machine_manager, cache, autotest_runner, perf_processor):
    threading.Thread.__init__(self)
    self.name = name
    self.benchmark_name = benchmark_name
    self.autotest_name = autotest_name
    self.autotest_args = autotest_args
    self.label_name = label_name
    self.chromeos_root = chromeos_root
    self.chromeos_image = os.path.expanduser(chromeos_image)
    self.board = board
    self.iteration = iteration
    self.results = {}
    self.terminate = False
    self.retval = None
    self.status = STATUS_PENDING
    self.run_completed = False
    self.outlier_range = outlier_range
    self.profile_counters = profile_counters
    self.machine_manager = machine_manager
    self.cache = cache
    self.autotest_runner = autotest_runner
    self.perf_processor = perf_processor
    self.machine = None
    self.full_name = self.autotest_name
    self.cache_conditions = cache_conditions
    self.runs_complete = 0
    self.cache_hit = False

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

  def _GetResultsDir(self, output):
    mo = re.search("Results placed in (\S+)", output)
    if mo:
      result = mo.group(1)
      return result
    return ""

  def StoreResults(self, results_dir):
    # Store perf_report and autotest output locally.
    self.cache.ReadAutotestOutput(results_dir)
    with open(os.path.join(results_dir, "perf.report"), "wb") as f:
      f.write(self.perf_report)

  def run(self):
    self._logger = logger.Logger(os.path.dirname(__file__),
                                 "%s.%s" % (os.path.basename(__file__),
                                            self.name), True)

    try:
      # Just use the first machine for running the cached version,
      # without locking it.
      self.machine = self.machine_manager.GetMachines()[0]

      self.cache.Init(self.chromeos_image,
                      self.chromeos_root,
                      self.autotest_name,
                      self.iteration,
                      self.autotest_args,
                      self.machine.name,
                      self.board,
                      self.cache_conditions,
                      self._logger)

      result = self.cache.ReadResult()
      self.cache_hit = (result is not None)

      if result:
        self._logger.LogOutput(result.out + "\n" + result.err)
      else:
        self.status = STATUS_WAITING
        # Try to acquire a machine now.
        self.machine = None
        self.machine = self.AcquireMachine()
        self.cache.remote = self.machine.name
        result = self.RunTest(self.machine)

      if not result.retval:
        self.status = STATUS_SUCCEEDED
      else:
        self.status = STATUS_FAILED

      results_dir = self._GetResultsDir(result.out)
      self.full_name = os.path.basename(results_dir)

      self.results = self.ParseResults(result.out)

      if not self.cache_hit:
        self.cache.StoreAutotestOutput(results_dir)

      if self.profile_counters:
        if not self.cache_hit:
          self.perf_report = (self.perf_processor.
                              GeneratePerfReport(results_dir,
                                                 self.chromeos_root,
                                                 self.board))
          self.cache.StorePerfReport(self.perf_report)
        else:
          self.perf_report = self.cache.ReadPerfReport()
      else:
        self.perf_report = ""

      return result.retval
    except Exception, e:
      self._logger.LogError("Benchmark run: '%s' failed: %s." % (self.name, e))
      traceback.print_exc()
      self.status = STATUS_FAILED
    finally:
      if self.machine:
        self._logger.LogOutput("Releasing machine: %s" % self.machine.name)
        self.machine_manager.ReleaseMachine(self.machine)
        self._logger.LogOutput("Released machine: %s" % self.machine.name)

  def AcquireMachine(self):
    while True:
      if self.terminate:
        raise Exception("Thread terminated while trying to acquire machine.")
      machine = self.machine_manager.AcquireMachine(self.chromeos_image)
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
    self.status = STATUS_IMAGING
    self.machine_manager.ImageMachine(machine,
                                      self.chromeos_image,
                                      self.board)
    self.status = "%s %s" % (STATUS_RUNNING, self.autotest_name)
    [retval, out, err] = self.autotest_runner.Run(machine.name,
                                                  self.chromeos_root,
                                                  self.board,
                                                  self.autotest_name,
                                                  self.autotest_args,
                                                  self.profile_counters)
    self.run_completed = True
    result = Result(out, err, retval)

    self.cache.StoreResult(result)
    return result

  def SetCacheConditions(self, cache_conditions):
    self.cache_conditions = cache_conditions
