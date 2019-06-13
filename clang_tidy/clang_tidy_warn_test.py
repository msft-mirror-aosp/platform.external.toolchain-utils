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
import clang_tidy_warn_patterns as ct_patterns

import unittest
from contextlib import contextmanager
import StringIO

import warnings_pb2  # if missing, run compile_proto.sh to generate it


def get_test_vars():
  """create artificial warn_patterns and project names for testing purposes"""

  project_names = ['ProjectA', 'ProjectB']
  warn_patterns = [{
      'severity': ct_patterns.Severity.FIXMENOW,
      'projects': {
          'ProjectA': 2,
          'ProjectB': 0
      },
      'description': 'Test warning of severity 1 (FIXMENOW)'
  },
                   {
                       'severity': ct_patterns.Severity.HIGH,
                       'projects': {
                           'ProjectA': 1,
                           'ProjectB': 3
                       },
                       'description': 'Test warning of severity 2 (HIGH)'
                   },
                   {
                       'severity': ct_patterns.Severity.MEDIUM,
                       'projects': {
                           'ProjectA': 0,
                           'ProjectB': 6
                       },
                       'description': 'Test warning of severity 3 (MEDIUM)'
                   }]
  # pad warn_patterns with severities we are not using
  for s in sorted(ct_patterns.Severity.levels, key=lambda s: s.value):
    if s.value >= len(warn_patterns):
      warn_patterns.append({'severity': s, 'projects': {}})
      warn_patterns[s.value]['description'] = ""
    warn_patterns[s.value]['members'] = []

  warning_messages = [
      "/ProjectB:1:1: warning: (1) Project B of severity 1",
      "/ProjectB:1:1: warning: (2) Project B of severity 1",
      "/ProjectB:1:1: warning: (3) Project B of severity 1",
      "/ProjectA:22:23: warning: (1) Project A of severity 0",
      "/ProjectA:22:23: warning: (2) Project A of severity 0",
      "/ProjectA:22:23: warning: Project A of severity 1",
      "/ProjectB:1:1: warning: (1) Project B of severity 2",
      "/ProjectB:1:1: warning: (2) Project B of severity 2",
      "/ProjectB:1:1: warning: (3) Project B of severity 2",
      "/ProjectB:1:1: warning: (4) Project B of severity 2",
      "/ProjectB:1:1: warning: (5) Project B of severity 2",
      "/ProjectB:1:1: warning: (6) Project B of severity 2"
  ]
  # [ warn_patterns index, project_names index, warning_messages index
  warning_records = [[1, 1, 0, 0], [1, 1, 1, 0], [1, 1, 2, 0], [0, 0, 3, 0],
                     [0, 0, 4, 0], [1, 0, 5, 0], [2, 1, 6, 0], [2, 1, 7, 0],
                     [2, 1, 8, 0], [2, 1, 9, 0], [2, 1, 10, 0], [2, 1, 11, 0]]

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

  res = {
      'project_names': project_names,
      'warn_patterns': warn_patterns,
      'warnings': expected_warnings,
      'total_by_project': expected_total_by_project,
      'total_by_severity': expected_total_by_severity,
      'total_all_projects': expected_total_all_projects,
      'stats_rows': expected_stats_rows,
      'warning_messages': warning_messages,
      'warning_records': warning_records,
  }

  return res


def put_test_vars():
  # save old warn patterns to reset to following this test
  actual_warn_patterns = ct_warn.warn_patterns
  actual_project_names = ct_warn.project_names
  actual_warning_messages = ct_warn.warning_messages
  actual_warning_records = ct_warn.warning_records

  # run test w specified inputs
  expected = get_test_vars()

  ct_warn.warn_patterns = expected['warn_patterns']
  ct_warn.project_names = expected['project_names']
  ct_warn.warning_messages = expected['warning_messages']
  ct_warn.warning_records = expected['warning_records']
  return (actual_warn_patterns, actual_project_names, actual_warning_messages,
          actual_warning_records)


def remove_test_vars(actual_warn_patterns, actual_project_names,
                     actual_warning_messages, actual_warning_records):
  # reset to actual vals
  ct_warn.project_names = actual_project_names
  ct_warn.warn_patterns = actual_warn_patterns
  ct_warn.warning_messages = actual_warning_messages
  ct_warn.warning_records = actual_warning_records


def setup_classify():
  """Run prereqs for calling classify_one_warning

  The module requires an explicit call to compile_patterns to have these created
  and this happens outside of the methods we are testing so explicit setup is
  necessary
  """

  ct_warn.compile_patterns()


@contextmanager
def test_vars():
  actual_warn_patterns, actual_project_names, actual_warning_messages, \
    actual_warning_records = put_test_vars()
  try:
    yield
  finally:
    remove_test_vars(actual_warn_patterns, actual_project_names,
                     actual_warning_messages, actual_warning_records)


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
    warning = {"line": line, "link": ""}
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
    ct_warn.classify_one_warning(warning, results)
    self.assertIn(expected_index, [result[2] for result in results])

  def test_parse_compiler_output_exception(self):
    with self.assertRaises(ValueError):
      ct_warn.parse_compiler_output("bad compiler output")

  def test_parse_compiler_output(self):
    with test_vars():
      expected = get_test_vars()
      test_message = expected['warning_messages'][4]  # /ProjectA:22:23 <text..>
      file_path, line_number, col_number, warning_message = (
          ct_warn.parse_compiler_output(test_message))
      self.assertEqual(file_path, "/ProjectA")
      self.assertEqual(line_number, 22)
      self.assertEqual(col_number, 23)
      self.assertEqual(warning_message, " warning: (2) Project A of severity 0")

  def test_data_to_protobuf(self):
    with test_vars():
      parsed_warning_messages = []
      for message in ct_warn.warning_messages:
        parsed_warning_messages.append(
            ct_warn.parse_compiler_output(message)[3])

      warnings = ct_warn.generate_protobufs()
      for warning in warnings:  # check that each warning was found
        self.assertIn(warning.matching_compiler_output, parsed_warning_messages)

  def test_remove_prefix_found(self):
    self.assertEqual(
        ct_warn.remove_prefix("googley google code", "gle"), "gle code")

  def test_remove_prefix_not_found(self):
    self.assertEqual(
        ct_warn.remove_prefix("google code", "bugs"), "google code")


if __name__ == '__main__':
  unittest.main()
