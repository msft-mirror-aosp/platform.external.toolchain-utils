#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from benchmark_run import BenchmarkRun
from machine_manager import MachineManager


class Experiment(object):
  """Class representing an Experiment to be run."""

  def __init__(self, name, board, remote, rerun_if_failed, working_directory):
    self.name = name
    self.board = board
    self.rerun_if_failed = rerun_if_failed
    self.working_directory = working_directory
    self.remote = remote

    self.labels = []
    self.benchmarks = []
    self.benchmark_runs = []

    self.machine_manager = MachineManager()

    for machine in remote:
      self.machine_manager.AddMachine(machine)

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
                                     label.chromeos_root,
                                     label.chromeos_image,
                                     "",
                                     self.board,
                                     benchmark.iterations,
                                     label.image_checksum,
                                     False,
                                     False,
                                     False)

        self.benchmark_runs.append(benchmark_run)

  def Build(self):
    pass

  def Run(self):
    pass

  def GetTable(self):
    return "<Table>"
