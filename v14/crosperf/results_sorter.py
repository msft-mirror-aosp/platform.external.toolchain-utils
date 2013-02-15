#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


class ResultSorter(object):
  def __init__(self, benchmark_runs):
    self.table = {}
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark_name
      label_name = benchmark_run.label_name
      for autotest_key in benchmark_run.results:
        result_tuple = (benchmark_name, autotest_key, label_name)
        if result_tuple not in self.table:
          self.table[result_tuple] = []

        cell = self.table[result_tuple]
        index = benchmark_run.iteration - 1
        while index >= len(cell):
          cell.append(None)

        result_value = benchmark_run.results[autotest_key]
        try:
          result_value = float(result_value)
        except ValueError:
          pass

        cell[index] = result_value

    self.autotest_keys = {}
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark_name
      if benchmark_name not in self.autotest_keys:
        self.autotest_keys[benchmark_name] = {}
      for autotest_key in benchmark_run.results:
        self.autotest_keys[benchmark_name][autotest_key] = True

  def GetAutotestKeys(self, benchmark_name):
    return self.autotest_keys[benchmark_name].keys()

  def GetResults(self, benchmark_name, autotest_key, label_name):
    return self.table[(benchmark_name, autotest_key, label_name)]
