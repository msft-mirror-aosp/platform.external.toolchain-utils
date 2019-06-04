#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 Google Inc. All Rights Reserved.

"""Clang_Tidy_Warn tests

This is the test file for clang_tidy_warn.py.
It starts with unit testing of individual functions, and then tests the
functionality of the whole file by using artificial log files, and then tests
on the real world examples.
"""

from __future__ import print_function

from csv import writer
import clang_tidy_warn as ct_warn

import unittest
from contextlib import contextmanager
import StringIO


def get_test_vars():
  """create artificial warn_patterns and project names for testing purposes"""

  project_names = ['ProjectA', 'ProjectB']
  warn_patterns = [{
      'severity': 0,
      'projects': {
          'ProjectA': 2,
          'ProjectB': 0
      }
  }, {
      'severity': 1,
      'projects': {
          'ProjectA': 1,
          'ProjectB': 3
      }
  }, {
      'severity': 2,
      'projects': {
          'ProjectA': 0,
          'ProjectB': 6
      }
  }]
  for s in range(9):
    if s >= len(warn_patterns):
      warn_patterns.append({'severity': s, 'projects': {}})
    warn_patterns[s]['members'] = []
    warn_patterns[s]['description'] = ""

  expected_warnings = {
      'ProjectA': {
          0: 2,
          1: 1,
          2: 0,
          3: 0,
          4: 0,
          5: 0,
          6: 0,
          7: 0,
          8: 0
      },
      'ProjectB': {
          0: 0,
          1: 3,
          2: 6,
          3: 0,
          4: 0,
          5: 0,
          6: 0,
          7: 0,
          8: 0
      }
  }
  expected_total_by_project = {'ProjectA': 3, 'ProjectB': 9}
  expected_total_by_severity = {
      0: 2,
      1: 4,
      2: 6,
      3: 0,
      4: 0,
      5: 0,
      6: 0,
      7: 0,
      8: 0
  }
  expected_total_all_projects = 12
  expected_stats_rows = [['ProjectA', 2, 1, 0, 3], ['ProjectB', 0, 3, 6, 9]]
  expected_count_severity_total = {}
  for s, warn_by_severity in enumerate(warn_patterns):
    # for each project, the number of desired warnings
    for project, count in warn_by_severity['projects'].items():
      warn_by_severity['members'] += [project] * count
    expected_count_severity_total[s] = len(warn_by_severity['members'])

  res = {
      'project_names': project_names,
      'warn_patterns': warn_patterns,
      'warnings': expected_warnings,
      'total_by_project': expected_total_by_project,
      'total_by_severity': expected_total_by_severity,
      'total_all_projects': expected_total_all_projects,
      'stats_rows': expected_stats_rows,
      'count_severity_total': expected_count_severity_total
  }

  return res


def put_test_vars():
  # save old warn patterns to reset to following this test
  actual_warn_patterns = ct_warn.warn_patterns
  actual_project_names = ct_warn.project_names

  # run test w specified inputs
  expected = get_test_vars()

  ct_warn.warn_patterns = expected['warn_patterns']
  ct_warn.project_names = expected['project_names']
  return actual_warn_patterns, actual_project_names


def remove_test_vars(actual_warn_patterns, actual_project_names):
  # reset to actual vals
  ct_warn.project_names = actual_project_names
  ct_warn.warn_patterns = actual_warn_patterns


def setup_classify():
  """Run prereqs for calling classify_one_warning

  The module requires an explicit call to compile_patterns to have these created
  and this happens outside of the methods we are testing so explicit setup is
  necessary
  """

  ct_warn.compile_patterns()


@contextmanager
def test_vars():
  actual_warn_patterns, actual_project_names = put_test_vars()
  try:
    yield
  finally:
    remove_test_vars(actual_warn_patterns, actual_project_names)


class Tests(unittest.TestCase):
  """Test Class for Clang-Tidy"""

  def test_initialize_arrays(self):
    names, patterns = ct_warn.initialize_arrays()
    self.assertGreater(len(names), 0)
    self.assertGreater(len(patterns), 0)

    # check that warn_patterns was modified in-place properly
    for w in ct_warn.warn_patterns:
      self.assertIn('members', w)
      self.assertIn('option', w)
      self.assertIn('projects', w)
      self.assertTrue(isinstance(w['projects'], dict))

  def test_create_warnings(self):
    with test_vars():
      expected = get_test_vars()
      self.assertEqual(expected['warnings'], ct_warn.create_warnings())

  def test_get_total_by_project(self):
    with test_vars():
      expected = get_test_vars()
      total_by_project = ct_warn.get_total_by_project(expected['warnings'])
      self.assertEqual(total_by_project, expected['total_by_project'])

  def test_get_total_by_severity(self):
    with test_vars():
      expected = get_test_vars()
      total_by_severity = ct_warn.get_total_by_severity(expected['warnings'])
      self.assertEqual(total_by_severity, expected['total_by_severity'])

  def test_emit_row_counts_per_project(self):
    with test_vars():
      expected = get_test_vars()
      total_all_projects, stats_rows = \
          ct_warn.emit_row_counts_per_project(expected['warnings'],
                                              expected['total_by_project'],
                                              expected['total_by_severity'])
      self.assertEqual(total_all_projects, expected['total_all_projects'])
      self.assertEqual(stats_rows, expected['stats_rows'])

  def test_classify_one_warning(self):
    setup_classify()
    line = ("external/libese/apps/weaver/weaver.c:340:17: "
            "warning: unused variable 'READ_SUCCESS' [-Wunused-variable]")
    results = []

    # find expected result
    expected_index = -1

    for i, w in enumerate(ct_warn.warn_patterns):
      if w['description'] == \
        "Unused function, variable, label, comparison, etc.":
        expected_index = i
        break  # we expect to find a single index
    assert expected_index != -1

    # check that the expected result is in index column of actual results
    ct_warn.classify_one_warning(line, results)
    self.assertIn(expected_index, [result[1] for result in results])

  def test_count_severity(self):
    with test_vars():
      expected = get_test_vars()

      # NOTE: csv writer necessary to call function but not testing that
      # functionality only testing that count_severity returns the correct total
      csvfile = StringIO.StringIO()
      csvwriter = writer(csvfile)
      for total in expected['count_severity_total'].items():
        # total = (severity, count for the severity)
        count_severity_total = ct_warn.count_severity(csvwriter, total[0],
                                                      "testing")
        self.assertEqual(count_severity_total, total[1])


if __name__ == '__main__':
  unittest.main()