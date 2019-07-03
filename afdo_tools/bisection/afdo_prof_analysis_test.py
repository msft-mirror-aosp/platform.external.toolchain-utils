#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for afdo_prof_analysis."""

from __future__ import print_function

import afdo_prof_analysis as analysis

import mock
import random
import unittest


class AfdoProfAnalysisTest(unittest.TestCase):
  """Class for testing AFDO Profile Analysis"""
  bad_items = {'func_a': '1', 'func_b': '3', 'func_c': '5'}
  good_items = {'func_a': '2', 'func_b': '4', 'func_d': '5'}
  random.seed(13)  # 13 is an arbitrary choice. just for consistency
  # add some extra info to make tests more reflective of real scenario
  for num in range(128):
    func_name = 'func_extra_%d' % num
    # 1/3 to both, 1/3 only to good, 1/3 only to bad
    rand_val = random.randint(1, 101)
    if rand_val < 67:
      bad_items[func_name] = 'test_data'
    if rand_val < 34 or rand_val >= 67:
      good_items[func_name] = 'test_data'

  analysis.random.seed(5)  # 5 is an arbitrary choice. For consistent testing

  def test_json_to_text(self):
    example_prof = {'func_a': ':1\ndata\n', 'func_b': ':2\nmore data\n'}
    expected_text = 'func_a:1\ndata\nfunc_b:2\nmore data\n'
    self.assertEqual(analysis.json_to_text(example_prof), expected_text)

  @mock.patch.object(analysis, 'run_external')
  def test_bisect_profiles(self, mock_run_external):

    # mock run of external script with arbitrarily-chosen bad profile vals
    def run_external(prof):
      if '1' in prof['func_a'] or '3' in prof['func_b']:
        return analysis.BAD_STATUS
      return analysis.GOOD_STATUS

    mock_run_external.side_effect = run_external
    results = analysis.bisect_profiles_wrapper(self.good_items, self.bad_items)
    self.assertEqual(results['individuals'], sorted(['func_a', 'func_b']))
    self.assertEqual(results['ranges'], [])

  @mock.patch.object(analysis, 'run_external')
  def test_non_bisecting_search(self, mock_run_external):

    # arbitrarily chosen functions whose values in the bad profile constitute
    # a problematic pair
    def run_external(prof):
      if '1' in prof['func_a'] and '3' in prof['func_b']:
        return analysis.BAD_STATUS
      return analysis.GOOD_STATUS

    mock_run_external.side_effect = run_external

    # put the problematic combination in separate halves of the common funcs
    # so that non-bisecting search is invoked for its actual use case
    common_funcs = [func for func in self.good_items if func in self.bad_items]
    common_funcs.remove('func_a')
    common_funcs.insert(0, 'func_a')
    common_funcs.remove('func_b')
    common_funcs.append('func_b')

    problem_range = analysis.non_bisecting_search(
        self.good_items, self.bad_items, common_funcs, 0, len(common_funcs))

    # we cannot test for the range being exactly these two functions because
    # the output is slightly random and, if unlucky, the range could end up
    # being bigger. But it is guaranteed that the output will at least
    # *contain* the problematic pair created here
    self.assertIn('func_a', problem_range)
    self.assertIn('func_b', problem_range)

  @mock.patch.object(analysis, 'run_external')
  def test_check_good_not_bad(self, mock_run_external):
    func_in_good = 'func_c'

    def run_external(prof):
      if func_in_good in prof:
        return analysis.GOOD_STATUS
      return analysis.BAD_STATUS

    mock_run_external.side_effect = run_external
    self.assertTrue(
        analysis.check_good_not_bad(self.good_items, self.bad_items))

  @mock.patch.object(analysis, 'run_external')
  def test_check_bad_not_good(self, mock_run_external):
    func_in_bad = 'func_d'

    def run_external(prof):
      if func_in_bad in prof:
        return analysis.BAD_STATUS
      return analysis.GOOD_STATUS

    mock_run_external.side_effect = run_external
    self.assertTrue(
        analysis.check_bad_not_good(self.good_items, self.bad_items))


if __name__ == '__main__':
  unittest.main()
