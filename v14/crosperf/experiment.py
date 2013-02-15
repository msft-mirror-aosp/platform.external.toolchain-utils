#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import threading
import time
from autotest_runner import AutotestRunner
from autotest_gatherer import AutotestGatherer
from benchmark_run import BenchmarkRun
from machine_manager import MachineManager
from perf_processor import PerfProcessor
from results_cache import ResultsCache
from utils import logger


class Experiment(threading.Thread):
  """Class representing an Experiment to be run."""

  def __init__(self, name, board, remote, rerun_if_failed, working_directory,
               parallel):
    threading.Thread.__init__(self)
    self.name = name
    self.board = board
    self.rerun_if_failed = rerun_if_failed
    self.working_directory = working_directory
    self.remote = remote
    self.parallel = parallel
    self.complete = False
    self.success = False

    self.labels = []
    self.benchmarks = []
    self.benchmark_runs = []
    self.num_complete = 0

    self.machine_manager = MachineManager()

    for machine in remote:
      self.machine_manager.AddMachine(machine)

    self.start_time = None

  def AddBenchmark(self, benchmark):
    self.benchmarks.append(benchmark)

  def AddLabel(self, label):
    self.labels.append(label)

  def GenerateBenchmarkRuns(self):
    """Generate benchmark runs from labels and benchmark defintions."""
    self.benchmark_runs = []
    for label in self.labels:
      for benchmark in self.benchmarks:
        benchmark_run = BenchmarkRun(benchmark.autotest_name,
                                     benchmark.autotest_args,
                                     label.chromeos_root,
                                     label.chromeos_image,
                                     self.board,
                                     benchmark.iterations,
                                     label.image_checksum,
                                     False,
                                     False,
                                     False,
                                     benchmark.outlier_range,
                                     self.machine_manager,
                                     ResultsCache(), AutotestRunner(),
                                     PerfProcessor())

        self.benchmark_runs.append(benchmark_run)

  def Build(self):
    pass

  def RunAutotestRunsInParallel(self):
    active_threads = []
    for benchmark_run in self.benchmark_runs:
      # Set threads to daemon so program exits when ctrl-c is pressed.
      benchmark_run.daemon = True
      benchmark_run.start()
      active_threads.append(benchmark_run)

    while active_threads:
      try:
        for t in active_threads:
          if t.isAlive():
            t.join(1)
          if not t.isAlive():
            self.num_complete += 1
      except KeyboardInterrupt:
        self.logger.LogError("C-c received... cleaning up threads.")
        for t in active_threads:
          t.terminate = True
        self.complete = True
        self.success = False
        return
    self.success = True
    self.complete = True

  def RunAutotestRunsSerially(self):
    for benchmark_run in self.benchmark_runs:
      retval = benchmark_run.run()
      self.num_complete += 1
      if retval:
        return retval

  def run(self):
    self.start_time = time.time()
    self.RunAutotestRunsInParallel()
    self.GenerateTable()

  def GenerateTable(self):
    ags_dict = {}
    for benchmark_run in self.benchmark_runs:
      name = benchmark_run.full_name
      if name not in ags_dict:
        ags_dict[name] = AutotestGatherer()
      ags_dict[name].runs.append(benchmark_run)
      output = ""
    for b, ag in ags_dict.items():
      output += "Benchmark: %s\n" % b
      output += ag.GetFormattedMainTable(percents_only=False,
                                         fit_string=False)
      output += "\n"

    summary = ""
    for b, ag in ags_dict.items():
      summary += "Benchmark Summary Table: %s\n" % b
      summary += ag.GetFormattedSummaryTable(percents_only=False,
                                             fit_string=False)
      summary += "\n"

    output += summary
    output += ("Number of re-images performed: %s" %
               self.machine_manager.num_reimages)

    self.table = output
