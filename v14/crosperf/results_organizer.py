#!/usr/bin/python

# Copyright 2012 Google Inc. All Rights Reserved.


class ResultOrganizer(object):
  """Create a dict from benchmark_runs.

  The structure of the output dict is as follows:
  {"benchmark_1":[
    [{"key1":"v1", "key2":"v2"},{"key1":"v1", "key2","v2"}]
    #one label
    []
    #the other label
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
          self.result[benchmark_name].append([])
      label_index = self.labels.index(benchmark_run.label_name)
      cur_table = self.result[benchmark_name][label_index]
      index = benchmark_run.iteration - 1
      while index >= len(cur_table):
        cur_table.append({})
      cur_dict = cur_table[index]
      if not benchmark_run.result:
        continue
      for autotest_key in benchmark_run.result.keyvals:
        result_value = benchmark_run.result.keyvals[autotest_key]
        cur_dict[autotest_key] = result_value
