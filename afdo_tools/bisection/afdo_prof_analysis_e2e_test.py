#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""End-to-end test for afdo_prof_analysis."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from datetime import date

import afdo_prof_analysis as analysis

import json
import shutil
import tempfile
import os
import unittest


class AfdoProfAnalysisE2ETest(unittest.TestCase):
  """Class for end-to-end testing of AFDO Profile Analysis"""

  # nothing significant about the values, just easier to remember even vs odd
  good_prof = {
      'func_a': ':1\n 1: 3\n 3: 5\n 5: 7\n',
      'func_b': ':3\n 3: 5\n 5: 7\n 7: 9\n',
      'func_c': ':5\n 5: 7\n 7: 9\n 9: 11\n',
      'func_d': ':7\n 7: 9\n 9: 11\n 11: 13\n',
      'good_func_a': ':11\n',
      'good_func_b': ':13\n'
  }

  bad_prof = {
      'func_a': ':2\n 2: 4\n 4: 6\n 6: 8\n',
      'func_b': ':4\n 4: 6\n 6: 8\n 8: 10\n',
      'func_c': ':6\n 6: 8\n 8: 10\n 10: 12\n',
      'func_d': ':8\n 8: 10\n 10: 12\n 12: 14\n',
      'bad_func_a': ':12\n',
      'bad_func_b': ':14\n'
  }

  expected = {
      'good_only_functions': False,
      'bad_only_functions': True,
      'bisect_results': {
          'ranges': [],
          'individuals': ['func_a']
      }
  }

  def test_afdo_prof_analysis(self):
    # Individual issues take precedence by nature of our algos
    # so first, that should be caught
    good = self.good_prof.copy()
    bad = self.bad_prof.copy()
    self.run_check(good, bad, self.expected)

    # Now remove individuals and exclusively BAD, and check that range is caught
    bad['func_a'] = good['func_a']
    bad.pop('bad_func_a')
    bad.pop('bad_func_b')

    expected_cp = self.expected.copy()
    expected_cp['bad_only_functions'] = False
    expected_cp['bisect_results'] = {
        'individuals': [],
        'ranges': [['func_b', 'func_c', 'func_d']]
    }

    self.run_check(good, bad, expected_cp)

  def test_afdo_prof_state(self):
    """Verifies that saved state is correct replication."""
    temp_dir = tempfile.mkdtemp()
    self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)

    good = self.good_prof.copy()
    bad = self.bad_prof.copy()
    # add more functions to data
    for x in range(400):
      good['func_%d' % x] = ''
      bad['func_%d' % x] = ''

    fd_first, first_result = tempfile.mkstemp(dir=temp_dir)
    os.close(fd_first)
    fd_state, state_file = tempfile.mkstemp(dir=temp_dir)
    os.close(fd_state)
    self.run_check(
        self.good_prof,
        self.bad_prof,
        self.expected,
        state_file=state_file,
        out_file=first_result)

    fd_second, second_result = tempfile.mkstemp(dir=temp_dir)
    os.close(fd_second)
    completed_state_file = '%s.completed.%s' % (state_file, str(date.today()))
    self.run_check(
        self.good_prof,
        self.bad_prof,
        self.expected,
        state_file=completed_state_file,
        no_resume=False,
        out_file=second_result)

    with open(first_result) as f:
      initial_run = json.load(f)
    with open(second_result) as f:
      loaded_run = json.load(f)
    self.assertEqual(initial_run, loaded_run)

  def run_check(self,
                good_prof,
                bad_prof,
                expected,
                state_file=None,
                no_resume=True,
                out_file=None):
    temp_dir = tempfile.mkdtemp()
    self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)

    good_prof_file = '%s/%s' % (temp_dir, 'good_prof.txt')
    bad_prof_file = '%s/%s' % (temp_dir, 'bad_prof.txt')
    good_prof_text = analysis.json_to_text(good_prof)
    bad_prof_text = analysis.json_to_text(bad_prof)
    with open(good_prof_file, 'w') as f:
      f.write(good_prof_text)
    with open(bad_prof_file, 'w') as f:
      f.write(bad_prof_text)

    analysis.FLAGS.good_prof = good_prof_file
    analysis.FLAGS.bad_prof = bad_prof_file
    if state_file:
      analysis.FLAGS.state_file = state_file
    analysis.FLAGS.no_resume = no_resume
    analysis.FLAGS.analysis_output_file = out_file or '/dev/null'

    dir_path = os.path.dirname(os.path.realpath(__file__))  # dir of this file
    external_script = '%s/e2e_external.sh' % (dir_path)
    analysis.FLAGS.external_decider = external_script

    actual = analysis.main(None)
    actual.pop('seed')  # nothing to check
    self.assertEqual(actual, expected)


if __name__ == '__main__':
  unittest.main()
