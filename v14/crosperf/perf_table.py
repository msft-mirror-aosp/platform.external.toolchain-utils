#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.
"""Parse perf report data for tabulator."""

import os

from utils import perf_diff

def ParsePerfReport(perf_file):
  """It should return a dict."""

  return {"cycles": {"foo": 10, "bar": 20},
          "cache_miss": {"foo": 20, "bar": 10}}


class PerfTable(object):
  """The class to generate dicts for tabulator."""

  def __init__(self, experiment, label_names):
    self._experiment = experiment
    self._label_names = label_names
    self.perf_data = {}
    self.GenerateData()
    # {benchmark:{perf_event1:[[{func1:number, func2:number},
    #                           {func1: number, func2: number}]], ...},
    #  benchmark2:...}

  def GenerateData(self):
    for label in self._label_names:
      for benchmark in self._experiment.benchmarks:
        for i in range(1, benchmark.iterations+1):
          dir_name = label + benchmark.name + str(i)
          dir_name = filter(str.isalnum, dir_name)
          perf_file = os.path.join(self._experiment.results_directory,
                                   dir_name,
                                   "perf.data.report.0")
          self.ReadPerfReport(perf_file, label, benchmark.name, i - 1)

  def ReadPerfReport(self, perf_file, label, benchmark_name, iteration):
    """Add the data from one run to the dict."""
    if os.path.isfile(perf_file):
      perf_of_run = perf_diff.GetPerfDictFromReport(perf_file)
    else:
      perf_of_run = {}
    if benchmark_name not in self.perf_data:
      self.perf_data[benchmark_name] = {}
      for event in perf_of_run:
        self.perf_data[benchmark_name][event] = []
    ben_data = self.perf_data[benchmark_name]

    label_index = self._label_names.index(label)
    for event in ben_data:
      while len(ben_data[event]) <= label_index:
        ben_data[event].append([])
      data_for_label = ben_data[event][label_index]
      while len(data_for_label) <= iteration:
        data_for_label.append({})
      if perf_of_run:
        data_for_label[iteration] = perf_of_run[event]
      else:
        data_for_label[iteration] = {}
