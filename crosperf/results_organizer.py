# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Parse data from benchmark_runs for tabulator."""

from __future__ import print_function

import json
import os
import re
import sys

from cros_utils import misc

TELEMETRY_RESULT_DEFAULTS_FILE = 'default-telemetry-results.json'


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

  def __init__(self,
               benchmark_runs,
               labels,
               benchmarks=None,
               json_report=False):
    self.result = {}
    self.labels = []
    self.prog = re.compile(r'(\w+)\{(\d+)\}')
    self.benchmarks = benchmarks
    if not self.benchmarks:
      self.benchmarks = []
    for label in labels:
      self.labels.append(label.name)
    for benchmark_run in benchmark_runs:
      benchmark_name = benchmark_run.benchmark.name
      if json_report:
        show_all_results = True
      else:
        show_all_results = benchmark_run.benchmark.show_all_results
      if benchmark_name not in self.result:
        self.result[benchmark_name] = []
        while len(self.result[benchmark_name]) < len(labels):
          self.result[benchmark_name].append([])
      label_index = self.labels.index(benchmark_run.label.name)
      cur_table = self.result[benchmark_name][label_index]
      index = benchmark_run.iteration - 1
      while index >= len(cur_table):
        cur_table.append({})
      cur_dict = cur_table[index]
      if not benchmark_run.result:
        continue
      benchmark = benchmark_run.benchmark
      if not show_all_results:
        summary_list = self._GetSummaryResults(benchmark.test_name)
        if len(summary_list) > 0:
          summary_list.append('retval')
        else:
          # Did not find test_name in json file; therefore show everything.
          show_all_results = True
      for test_key in benchmark_run.result.keyvals:
        if not show_all_results and not test_key in summary_list:
          continue
        cur_dict[test_key] = benchmark_run.result.keyvals[test_key]
      # Occasionally Telemetry tests will not fail but they will not return a
      # result, either.  Look for those cases, and force them to be a fail.
      # (This can happen if, for example, the test has been disabled.)
      if len(cur_dict) == 1 and cur_dict['retval'] == 0:
        cur_dict['retval'] = 1
        # TODO: This output should be sent via logger.
        print("WARNING: Test '%s' appears to have succeeded but returned"
              ' no results.' % benchmark_name,
              file=sys.stderr)
      if json_report and benchmark_run.machine:
        cur_dict['machine'] = benchmark_run.machine.name
        cur_dict['machine_checksum'] = benchmark_run.machine.checksum
        cur_dict['machine_string'] = benchmark_run.machine.checksum_string
    self._DuplicatePass()

  def _GetSummaryResults(self, test_name):
    dirname, _ = misc.GetRoot(sys.argv[0])
    fullname = os.path.join(dirname, TELEMETRY_RESULT_DEFAULTS_FILE)
    if os.path.exists(fullname):
      # Slurp the file into a dictionary.  The keys in the dictionary are
      # the benchmark names.  The value for a key is a list containing the
      # names of all the result fields that should be returned in a 'default'
      # report.
      result_defaults = json.load(open(fullname))
      # Check to see if the current benchmark test actually has an entry in
      # the dictionary.
      if test_name in result_defaults:
        return result_defaults[test_name]
      else:
        return []

  def _DuplicatePass(self):
    for bench, data in self.result.items():
      max_dup = self._GetMaxDup(data)
      if not max_dup:
        continue
      for label in data:
        index = data.index(label)
        data[index] = self._GetNonDupLabel(max_dup, label)
      self._AdjustIteration(max_dup, bench)

  def _GetMaxDup(self, data):
    """Find the maximum i inside ABCD{i}."""
    max_dup = 0
    for label in data:
      for run in label:
        for key in run:
          if re.match(self.prog, key):
            max_dup = max(max_dup, int(re.search(self.prog, key).group(2)))
    return max_dup

  def _GetNonDupLabel(self, max_dup, label):
    """Create new list for the runs of the same label."""
    new_label = []
    for run in label:
      start_index = len(new_label)
      new_label.append(dict(run))
      for _ in range(max_dup):
        new_label.append({})
      new_run = new_label[start_index]
      for key, value in new_run.items():
        if re.match(self.prog, key):
          new_key = re.search(self.prog, key).group(1)
          index = int(re.search(self.prog, key).group(2))
          new_label[start_index + index][new_key] = str(value)
          del new_run[key]
    return new_label

  def _AdjustIteration(self, max_dup, bench):
    """Adjust the interation numbers if the have keys like ABCD{i}."""
    for benchmark in self.benchmarks:
      if benchmark.name == bench:
        if not benchmark.iteration_adjusted:
          benchmark.iteration_adjusted = True
          benchmark.iterations *= (max_dup + 1)
