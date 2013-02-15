#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
import threading
import time
from autotest_runner import AutotestRunner
from benchmark_run import BenchmarkRun
from machine_manager import MachineManager
from perf_processor import PerfProcessor
from results_cache import ResultsCache
from results_report import HTMLResultsReport
from utils import logger
from utils.file_utils import FileUtils


class Experiment(threading.Thread):
  """Class representing an Experiment to be run."""

  def __init__(self, name, remote, rerun_if_failed, working_directory,
               parallel, chromeos_root, cache_conditions, labels, benchmarks,
               experiment_file):
    threading.Thread.__init__(self)
    self.name = name
    self.rerun_if_failed = rerun_if_failed
    self.working_directory = working_directory
    self.remote = remote
    self.chromeos_root = chromeos_root
    self.cache_conditions = cache_conditions
    self.parallel = parallel
    self.complete = False
    self.terminate = False
    self.experiment_file = experiment_file
    self.results_directory = os.path.join(self.working_directory,
                                          self.name + "_results")

    self.labels = labels
    self.benchmarks = benchmarks
    self.num_complete = 0

    # We need one chromeos_root to run the benchmarks in, but it doesn't
    # matter where it is, unless the ABIs are different.
    if not chromeos_root:
      for label in self.labels:
        if label.chromeos_root:
          chromeos_root = label.chromeos_root
    if not chromeos_root:
      raise Exception("No chromeos_root given and could not determine one from "
                      "the image path.")

    self.machine_manager = MachineManager(chromeos_root)
    self.l = logger.GetLogger()

    for machine in remote:
      self.machine_manager.AddMachine(machine)

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
          benchmark_run = BenchmarkRun(benchmark_run_name,
                                       benchmark.name,
                                       benchmark.autotest_name,
                                       benchmark.autotest_args,
                                       label.name,
                                       label.chromeos_root,
                                       label.chromeos_image,
                                       label.board,
                                       iteration,
                                       self.cache_conditions,
                                       benchmark.outlier_range,
                                       benchmark.profile_counters,
                                       self.machine_manager,
                                       ResultsCache(),
                                       AutotestRunner(),
                                       PerfProcessor())

          benchmark_runs.append(benchmark_run)
    return benchmark_runs

  def Build(self):
    pass

  def Terminate(self):
    for t in self.benchmark_runs:
      if t.isAlive():
        self.l.LogError("Terminating run: '%s'." % t.name)
        t.terminate = True

  def RunAutotestRunsInParallel(self):
    active_threads = []
    for benchmark_run in self.benchmark_runs:
      # Set threads to daemon so program exits when ctrl-c is pressed.
      benchmark_run.daemon = True
      benchmark_run.start()
      active_threads.append(benchmark_run)

    try:
      while active_threads:
        if self.terminate:
          self.Terminate()
          return

        for t in active_threads:
          if t.isAlive():
            t.join(1)
          if not t.isAlive():
            self.num_complete += 1
            active_threads.remove(t)
    except KeyboardInterrupt:
      self.Terminate()
      return
    finally:
      self.complete = True

    self.l.LogOutput("Benchmark runs complete. Final status:")
    for benchmark_run in self.benchmark_runs:
      self.l.LogOutput("'%s'\t\t%s" % (benchmark_run.name,
                                       benchmark_run.status))

  def run(self):
    self.start_time = time.time()
    self.RunAutotestRunsInParallel()

  def StoreResults(self):
    FileUtils().RmDir(self.results_directory)
    FileUtils().MkDirP(self.results_directory)
    experiment_file_path = os.path.join(self.results_directory,
                                        "experiment.exp")
    with open(experiment_file_path, "wb") as f:
      f.write(self.experiment_file)

    results_table_path = os.path.join(self.results_directory, "results.html")
    report = HTMLResultsReport(self).GetReport()
    with open(results_table_path, "wb") as f:
      f.write(report)

    for benchmark_run in self.benchmark_runs:
      benchmark_run_name = filter(str.isalnum, benchmark_run.name)
      benchmark_run_path = os.path.join(self.results_directory,
                                        benchmark_run_name)
      FileUtils().MkDirP(benchmark_run_path)
      benchmark_run.StoreResults(benchmark_run_path)

  def SetCacheConditions(self, cache_conditions):
    for benchmark_run in self.benchmark_runs:
      benchmark_run.SetCacheConditions(cache_conditions)

  def Cleanup(self):
    self.machine_manager.Cleanup()
