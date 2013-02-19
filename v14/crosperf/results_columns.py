#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math
from utils import stats


class Column(object):
  def __init__(self, name):
    self.name = name

  def _ContainsString(self, results):
    for result in results:
      if isinstance(result, str):
        return True
    return False

  def _StripNone(self, results):
    res = []
    for result in results:
      if result is not None:
        res.append(result)
    return res


class MinColumn(Column):
  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"
    results = self._StripNone(results)
    if not results:
      return "-"
    return min(results)


class MaxColumn(Column):
  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"
    results = self._StripNone(results)
    if not results:
      return "-"
    return max(results)


class MeanColumn(Column):
  def Compute(self, results, baseline_results):
    all_pass = True
    all_fail = True
    if self._ContainsString(results):
      for result in results:
        if result != "PASSED":
          all_pass = False
        if result != "FAILED":
          all_fail = False

      if all_pass:
        return "ALL PASS"
      elif all_fail:
        return "ALL FAIL"
      else:
        return "-"

    results = self._StripNone(results)
    if not results:
      return "-"
    return float(sum(results)) / len(results)


class StandardDeviationColumn(Column):
  def __init__(self, name):
    super(StandardDeviationColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"

    results = self._StripNone(results)
    if not results:
      return "-"
    n = len(results)
    average = sum(results) / n
    total = 0
    for result in results:
      total += (result - average) ** 2

    return math.sqrt(total / n)


class RatioColumn(Column):
  def __init__(self, name):
    super(RatioColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results) or self._ContainsString(baseline_results):
      return "-"

    results = self._StripNone(results)
    baseline_results = self._StripNone(baseline_results)
    if not results or not baseline_results:
      return "-"
    result_mean = sum(results) / len(results)
    baseline_mean = sum(baseline_results) / len(baseline_results)

    if not baseline_mean:
      return "-"

    return result_mean / baseline_mean


class DeltaColumn(Column):
  def __init__(self, name):
    super(DeltaColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results) or self._ContainsString(baseline_results):
      return "-"

    results = self._StripNone(results)
    baseline_results = self._StripNone(baseline_results)
    if not results or not baseline_results:
      return "-"
    result_mean = sum(results) / len(results)
    baseline_mean = sum(baseline_results) / len(baseline_results)

    if not baseline_mean:
      return "-"

    res = 100 * (result_mean - baseline_mean) / baseline_mean
    return res


class IterationsCompleteColumn(Column):
  def __init__(self, name):
    super(IterationsCompleteColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    return len(self._StripNone(results))


class IterationColumn(Column):
  def __init__(self, name, iteration):
    super(IterationColumn, self).__init__(name)
    self.iteration = iteration

  def Compute(self, results, baseline_results):
    if self.iteration > len(results):
      return ""
    res = results[self.iteration - 1]
    if not res:
      return "-"
    return res


class ColorColumn(Column):
  def __init__(self, name):
    super(ColorColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if len(results) or len(baseline_results):
      return ""
    return ""


class SignificantDiffColumn(Column):
  def __init__(self, name):
    super(SignificantDiffColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results) or self._ContainsString(baseline_results):
      return ""

    results = self._StripNone(results)
    baseline_results = self._StripNone(baseline_results)
    if len(results) < 2 or len(baseline_results) < 2:
      return ""
    t, p = stats.lttest_ind(baseline_results, results)
    return p
