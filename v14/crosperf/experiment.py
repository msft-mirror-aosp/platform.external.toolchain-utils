#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
import time

from utils import logger

from autotest_runner import AutotestRunner
from benchmark_run import BenchmarkRun
from machine_manager import MachineManager
from machine_manager import MockMachineManager
from results_cache import ResultsCache
from results_report import HTMLResultsReport
import test_flag


class Experiment(object):
  """Class representing an Experiment to be run."""

  def __init__(self, name, remote, rerun_if_failed, working_directory,
               chromeos_root, cache_conditions, labels, benchmarks,
               experiment_file, email_to):
    self.name = name
    self.rerun_if_failed = rerun_if_failed
    self.working_directory = working_directory
    self.remote = remote
    self.chromeos_root = chromeos_root
    self.cache_conditions = cache_conditions
    self.experiment_file = experiment_file
    self.email_to = email_to
    self.results_directory = os.path.join(self.working_directory,
                                          self.name + "_results")

    self.labels = labels
    self.benchmarks = benchmarks
    self.num_complete = 0
    self.num_run_complete = 0

    # We need one chromeos_root to run the benchmarks in, but it doesn't
    # matter where it is, unless the ABIs are different.
    if not chromeos_root:
      for label in self.labels:
        if label.chromeos_root:
          chromeos_root = label.chromeos_root
    if not chromeos_root:
      raise Exception("No chromeos_root given and could not determine one from "
                      "the image path.")

    if test_flag.GetTestMode():
      self.machine_manager = MockMachineManager(chromeos_root)
    else:
      self.machine_manager = MachineManager(chromeos_root)
    self.l = logger.GetLogger()

    for machine in remote:
      self.machine_manager.AddMachine(machine)
    for label in labels:
      self.machine_manager.ComputeCommonCheckSum(label)
      self.machine_manager.ComputeCommonCheckSumString(label)

    self.start_time = None
    self.benchmark_runs = self._GenerateBenchmarkRuns()

  def _GenerateBenchmarkRuns(self):
    """Generate benchmark runs from labels and benchmark defintions."""
    benchmark_runs = []
    for label in self.labels:
      for benchmark in self.benchmarks:
        for iteration in range(1, benchmark.iterations + 1):

          benchmark_run_name = "%s: %s (%s)" % (label.name, benchmark.name,
                                                iteration)
          full_name = "%s_%s_%s" % (label.name, benchmark.name, iteration)
          logger_to_use = logger.Logger(os.path.dirname(__file__),
                                        "run.%s" % (full_name),
                                        True)
          benchmark_run = BenchmarkRun(benchmark_run_name,
                                       benchmark.name,
                                       benchmark.autotest_name,
                                       benchmark.autotest_args,
                                       label,
                                       iteration,
                                       self.cache_conditions,
                                       benchmark.outlier_range,
                                       benchmark.perf_args,
                                       self.machine_manager,
                                       logger_to_use)

          benchmark_runs.append(benchmark_run)
    return benchmark_runs

  def Build(self):
    pass

  def Terminate(self):
    for t in self.benchmark_runs:
      if t.isAlive():
        self.l.LogError("Terminating run: '%s'." % t.name)
        t.Terminate()

  def IsComplete(self):
    if self.active_threads:
      for t in self.active_threads:
        if t.isAlive():
          t.join(0)
        if not t.isAlive():
          self.num_complete += 1
          if not t.cache_hit:
            self.num_run_complete += 1
          self.active_threads.remove(t)
      return False
    return True

  def Run(self):
    self.start_time = time.time()
    self.active_threads = []
    for benchmark_run in self.benchmark_runs:
      # Set threads to daemon so program exits when ctrl-c is pressed.
      benchmark_run.daemon = True
      benchmark_run.start()
      self.active_threads.append(benchmark_run)

  def SetCacheConditions(self, cache_conditions):
    for benchmark_run in self.benchmark_runs:
      benchmark_run.SetCacheConditions(cache_conditions)

  def Cleanup(self):
    self.machine_manager.Cleanup()
