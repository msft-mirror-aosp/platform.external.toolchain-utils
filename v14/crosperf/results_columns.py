#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math


class Column(object):
  def __init__(self, name):
    self.name = name

  def _ContainsString(self, results):
    for result in results:
      if isinstance(result, str):
        return True
      return False

  def _CountValues(self, results):
    count = 0
    for _ in range(len(results)):
      if count is not None:
        count += 1
    return count

  def _Average(self, results):
    total = 0
    for result in results:
      if result is not None:
        total += result
    return total / self._CountValues(results)


class MinColumn(Column):
  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"
    return min(results)


class MaxColumn(Column):
  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"
    return max(results)


class MeanColumn(Column):
  def Compute(self, results, baseline_results):
    all_pass = True
    all_fail = False
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
        return "SOME FAIL"

    return float(sum(results)) / len(results)


class StandardDeviationColumn(Column):
  def __init__(self, name):
    super(StandardDeviationColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results):
      return "-"

    n = self._CountValues(results)
    average = self._Average(results)
    total = 0
    for result in results:
      if not result:
        continue
      total += (result - average) ** 2

    result = math.sqrt(total / n)

    return result


class RatioColumn(Column):
  def __init__(self, name):
    super(RatioColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results) or self._ContainsString(baseline_results):
      return "-"

    result_mean = self._Average(results)
    baseline_mean = self._Average(baseline_results)

    return result_mean / baseline_mean


class DeltaColumn(Column):
  def __init__(self, name):
    super(DeltaColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    if self._ContainsString(results) or self._ContainsString(baseline_results):
      return "-"

    result_mean = self._Average(results)
    baseline_mean = self._Average(baseline_results)

    res = 100 * (result_mean - baseline_mean) / baseline_mean
    return res


class IterationsCompleteColumn(Column):
  def __init__(self, name):
    super(IterationsCompleteColumn, self).__init__(name)

  def Compute(self, results, baseline_results):
    return self._CountValues(results)


class IterationColumn(Column):
  def __init__(self, name, iteration):
    super(IterationColumn, self).__init__(name)
    self.iteration = iteration

  def Compute(self, results, baseline_results):
    if self.iteration > len(results):
      return ""
    res = results[self.iteration - 1]
    if res is None:
      return "-"
    return res
