#!/usr/bin/python

# Copyright 2012 Google Inc. All Rights Reserved.


class ResultOrganizer(object):
  """Create a dict from benchmark_runs.

  The structure of the output dict is as follows:
  {"benchmark_1":
    [
     {"autotest_key1":[v1, v2, v3,,,],
      "autotest_key2":[v1, v2, v3,,,]}
     #label_1

     {...}
     #lable_2
    ]
   "benchmark_2":
    [
    ]}.
  """

  def __init__(self, benchmark_runs, labels):
    self.result = {}
    self.labels = []
    for label in labels:
      self.labels.append(label.name)
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark_name
      if benchmark_name not in self.result:
        self.result[benchmark_name] = []
        while len(self.result[benchmark_name]) < len(labels):
          self.result[benchmark_name].append({})
      cur_table = self.result[benchmark_name]
      label_name = benchmark_run.label_name
      label_index = self.labels.index(label_name)
      cur_dict = cur_table[label_index]
      if not benchmark_run.result:
        continue
      for autotest_key in benchmark_run.result.keyvals:
        if autotest_key not in cur_dict:
          cur_dict[autotest_key] = []
        cell = cur_dict[autotest_key]
        index = benchmark_run.iteration - 1
        while index >= len(cell):
          cell.append(None)

        result_value = benchmark_run.result.keyvals[autotest_key]
        try:
          result_value = float(result_value)
        except ValueError:
          pass

        cell[index] = result_value
