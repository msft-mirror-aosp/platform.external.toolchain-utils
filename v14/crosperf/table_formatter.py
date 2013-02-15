#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import re
import numpy


class TableFormatter(object):
  def __init__(self):
    self.d = "\t"
    self.bad_result = "x"

  def _IsFloat(self, text):
    if text is None:
      return False
    try:
      float(text)
      return True
    except ValueError:
      return False

  def _RemoveTrailingZeros(self, x):
    ret = x
    ret = re.sub("\.0*$", "", ret)
    ret = re.sub("(\.[1-9]*)0+$", "\\1", ret)
    return ret

  def _HumanizeFloat(self, x, n=2):
    if not self._IsFloat(x):
      return x
    digits = re.findall("[0-9.]", str(x))
    decimal_found = False
    ret = ""
    sig_figs = 0
    for digit in digits:
      if digit == ".":
        decimal_found = True
      elif sig_figs != 0 or digit != "0":
        sig_figs += 1
      if decimal_found and sig_figs >= n:
        break
      ret += digit
    return ret

  def _GetNSigFigs(self, x, n=2):
    if not self._IsFloat(x):
      return x
    my_fmt = "%." + str(n - 1) + "e"
    x_string = my_fmt % x
    f = float(x_string)
    return f

  def _GetFormattedPercent(self, baseline, other, bad_result="--"):
    result = "%8s" % self._GetPercent(baseline, other, bad_result)
    return result

  def _GetPercent(self, baseline, other, bad_result="--"):
    result = bad_result
    if self._IsFloat(baseline) and self._IsFloat(other):
      try:
        pct = (float(other) / float(baseline) - 1) * 100
        result = "%+1.1f" % pct
      except ZeroDivisionError:
        pass
    return result

  def _FitString(self, text, length):
    if len(text) == length:
      return text
    elif len(text) > length:
      return text[-length:]
    else:
      fmt = "%%%ds" % length
      return fmt % text

  def _GetTablePercents(self, table):
    # Assumes table is not transposed.
    pct_table = []

    pct_table.append(table[0])
    for i in range(1, len(table)):
      row = []
      row.append(table[i][0])
      for j in range (1, len(table[0])):
        c = table[i][j]
        b = table[i][1]
        p = self._GetPercent(b, c, self.bad_result)
        row.append(p)
      pct_table.append(row)
    return pct_table

  def _FormatFloat(self, c, max_length=8):
    if not self._IsFloat(c):
      return c
    f = float(c)
    ret = self._HumanizeFloat(f, 4)
    ret = self._RemoveTrailingZeros(ret)
    if len(ret) > max_length:
      ret = "%1.1ef" % f
    return ret

  def _TransposeTable(self, table):
    transposed_table = []
    for i in range(len(table[0])):
      row = []
      for j in range(len(table)):
        row.append(table[j][i])
      transposed_table.append(row)
    return transposed_table

  def GetFormattedTable(self, table, transposed=False,
                        first_column_width=30, column_width=14,
                        percents_only=True,
                        fit_string=True):
    o = ""
    pct_table = self._GetTablePercents(table)
    if transposed == True:
      table = self._TransposeTable(table)
      pct_table = self._TransposeTable(table)

    for i in range(0, len(table)):
      for j in range(len(table[0])):
        if j == 0:
          width = first_column_width
        else:
          width = column_width

        c = table[i][j]
        p = pct_table[i][j]

        # Replace labels with numbers: 0... n
        if self._IsFloat(c):
          c = self._FormatFloat(c)

        if self._IsFloat(p) and not percents_only:
          p = "%s%%" % p

        # Print percent values side by side.
        if j != 0:
          if percents_only:
            c = "%s" % p
          else:
            c = "%s (%s)" % (c, p)

        if i == 0 and j != 0:
          c = str(j)

        if fit_string:
          o += self._FitString(c, width) + self.d
        else:
          o += c + self.d
      o += "\n"
    return o

  def _GetGroups(self, table):
    labels = table[0]
    groups = []
    group_dict = {}
    for i in range(1, len(labels)):
      label = labels[i]
      stripped_label = self._GetStrippedLabel(label)
      if stripped_label not in group_dict:
        group_dict[stripped_label] = len(groups)
        groups.append([])
      groups[group_dict[stripped_label]].append(i)
    return groups

  def GetSummaryTableValues(self, table):
    # First get the groups
    groups = self._GetGroups(table)

    summary_table = []

    labels = table[0]

    summary_labels = ["Summary Table"]
    for group in groups:
      label = labels[group[0]]
      stripped_label = self._GetStrippedLabel(label)
      group_label = "%s (%d runs)" % (stripped_label, len(group))
      summary_labels.append(group_label)
    summary_table.append(summary_labels)

    for i in range(1, len(table)):
      row = table[i]
      summary_row = [row[0]]
      for group in groups:
        group_runs = []
        for index in group:
          group_runs.append(row[index])
        group_run = self._AggregateResults(group_runs)
        summary_row.append(group_run)
      summary_table.append(summary_row)

    return summary_table

  # Drop N% slowest and M% fastest numbers, and return arithmean of
  # the remaining.
  def _AverageWithDrops(self, numbers, slow_percent=20, fast_percent=20):
    sorted_numbers = list(numbers)
    sorted_numbers.sort()
    num_slow = int(slow_percent / 100.0 * len(sorted_numbers))
    num_fast = int(fast_percent / 100.0 * len(sorted_numbers))
    sorted_numbers = sorted_numbers[num_slow:]
    if num_fast:
      sorted_numbers = sorted_numbers[:-num_fast]
    return numpy.average(sorted_numbers)

  def _AggregateResults(self, group_results):
    ret = ""
    if not group_results:
      return ret
    all_floats = True
    all_passes = True
    all_fails = True
    for group_result in group_results:
      if not self._IsFloat(group_result):
        all_floats = False
      if group_result != "PASSED":
        all_passes = False
      if group_result != "FAILED":
        all_fails = False
    if all_floats == True:
      float_results = [float(v) for v in group_results]
      ret = "%f" % self._AverageWithDrops(float_results)
      # Add this line for standard deviation.
###      ret += " %f" % numpy.std(float_results)
    elif all_passes == True:
      ret = "ALL_PASS"
    elif all_fails == True:
      ret = "ALL_FAILS"
    return ret

  def _GetStrippedLabel(self, label):
    return re.sub("\s*\S+:\S+\s*", "", label)
###    return re.sub("\s*remote:\S*\s*i:\d+$", "", label)

  def GetLabelWithIteration(self, label, iteration):
    return "%s i:%d" % (label, iteration)

  def GetTableLabels(self, table):
    ret = ""
    header = table[0]
    for i in range(1, len(header)):
      ret += "%d: %s\n" % (i, header[i])
    return ret
