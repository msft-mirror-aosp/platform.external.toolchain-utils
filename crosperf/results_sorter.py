# Copyright 2011 Google Inc. All Rights Reserved.
"""Module to sort the results."""


class ResultSorter(object):
  """Class to sort the results."""

  def __init__(self, benchmark_runs):
    self.table = {}
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark_name
      label_name = benchmark_run.label_name
      if not benchmark_run.result:
        continue
      for autotest_key in benchmark_run.result.keyvals:
        result_tuple = (benchmark_name, autotest_key, label_name)
        if result_tuple not in self.table:
          self.table[result_tuple] = []

        cell = self.table[result_tuple]
        index = benchmark_run.iteration - 1
        while index >= len(cell):
          cell.append(None)

        result_value = benchmark_run.result.keyvals[autotest_key]
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
      if not benchmark_run.result:
        continue
      for autotest_key in benchmark_run.result.keyvals:
        self.autotest_keys[benchmark_name][autotest_key] = True

  def GetAutotestKeys(self, benchmark_name):
    return self.autotest_keys[benchmark_name].keys()

  def GetResults(self, benchmark_name, autotest_key, label_name):
    try:
      return self.table[(benchmark_name, autotest_key, label_name)]
    except KeyError:
      return []
