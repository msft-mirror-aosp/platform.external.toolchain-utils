# Copyright 2012 Google Inc. All Rights Reserved.
"""Parse perf report data for tabulator."""

import os

from utils import perf_diff


def ParsePerfReport(perf_file):
  """It should return a dict."""

  return {'cycles': {'foo': 10,
                     'bar': 20},
          'cache_miss': {'foo': 20,
                         'bar': 10}}


class PerfTable(object):
  """The class to generate dicts for tabulator."""

  def __init__(self, experiment, label_names):
    self._experiment = experiment
    self._label_names = label_names
    self.perf_data = {}
    self.GenerateData()

    # {benchmark:{perf_event1:[[{func1:number, func2:number,
    #                             rows_to_show: number}
    #                           {func1: number, func2: number
    #                             rows_to_show: number}]], ...},
    #  benchmark2:...}
    # The rows_to_show is temp data recording how many
    # rows have over 1% running time.
    self.row_info = {}
    self.GetRowsToShow()

  def GenerateData(self):
    for label in self._label_names:
      for benchmark in self._experiment.benchmarks:
        for i in range(1, benchmark.iterations + 1):
          dir_name = label + benchmark.name + str(i)
          dir_name = filter(str.isalnum, dir_name)
          perf_file = os.path.join(self._experiment.results_directory, dir_name,
                                   'perf.data.report.0')
          if os.path.exists(perf_file):
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

  def GetRowsToShow(self):
    for benchmark in self.perf_data:
      if benchmark not in self.row_info:
        self.row_info[benchmark] = {}
      for event in self.perf_data[benchmark]:
        rows = 0
        for run in self.perf_data[benchmark][event]:
          for iteration in run:
            if perf_diff.ROWS_TO_SHOW in iteration:
              rows = max(iteration[perf_diff.ROWS_TO_SHOW], rows)
              # delete the temp data which stores how many rows of
              # the perf data have over 1% running time.
              del iteration[perf_diff.ROWS_TO_SHOW]
        self.row_info[benchmark][event] = rows
