#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from table_formatter import TableFormatter


class AutotestGatherer(object):
  def __init__(self):
    self.runs = []
    self.formatter = TableFormatter()

  def GetFormattedMainTable(self, percents_only, fit_string):
    ret = ""
    table = self._GetTableValues()
    ret += self.formatter.GetTableLabels(table)
    ret += self.formatter.GetFormattedTable(table, percents_only=percents_only,
                                            fit_string=fit_string)
    return ret

  def GetFormattedSummaryTable(self, percents_only, fit_string):
    ret = ""
    table = self._GetTableValues()
    summary_table = self.formatter.GetSummaryTableValues(table)
    ret += self.formatter.GetTableLabels(summary_table)
    ret += self.formatter.GetFormattedTable(summary_table,
                                            percents_only=percents_only,
                                            fit_string=fit_string)
    return ret

  def _GetAllBenchmarks(self):
    all_benchmarks = []
    for run in self.runs:
      for key in run.results:
        if key not in all_benchmarks:
          all_benchmarks.append(key)
    all_benchmarks.sort()
    return all_benchmarks

  def _GetTableValues(self):
    table = []
    row = []

    row.append("Benchmark")
    for i in range(len(self.runs)):
      run = self.runs[i]
      label = run.GetLabel()
      label = self.formatter.GetLabelWithIteration(label, run.iteration)
      row.append(label)
    table.append(row)

    all_benchmarks = self._GetAllBenchmarks()
    for benchmark in all_benchmarks:
      row = []
      row.append(benchmark)
      for run in self.runs:
        results = run.results
        if benchmark in results:
          row.append(results[benchmark])
        else:
          row.append("")
      table.append(row)

    return table

