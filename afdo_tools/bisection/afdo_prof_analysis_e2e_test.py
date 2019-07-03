#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""End-to-end test for afdo_prof_analysis."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import afdo_prof_analysis as analysis

import shutil
import tempfile
import os
import unittest


class AfdoProfAnalysisE2ETest(unittest.TestCase):
  """Class for end-to-end testing of AFDO Profile Analysis"""

  def test_afdo_prof_analysis(self):
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

    # Individual issues take precedence by nature of our algos
    # so first, that should be caught
    expected = {
        'good_only_functions': False,
        'bad_only_functions': True,
        'bisect_results': {
            'ranges': [],
            'individuals': ['func_a']
        }
    }
    self.run_check(good_prof, bad_prof, expected)

    # Now remove individuals and exclusively BAD, and check that range is caught
    bad_prof['func_a'] = good_prof['func_a']
    bad_prof.pop('bad_func_a')
    bad_prof.pop('bad_func_b')
    expected['bad_only_functions'] = False
    expected['bisect_results'] = {
        'individuals': [],
        'ranges': [['func_b', 'func_c', 'func_d']]
    }

    # Since the range is so small, we want to finetune func interval
    # to confirm algo runs as expected
    # pylint:disable=protected-access
    analysis._FUNC_STEP = 1
    self.run_check(good_prof, bad_prof, expected)

  def run_check(self, good_prof, bad_prof, expected):
    temp_dir = tempfile.mkdtemp()

    def cleanup():
      shutil.rmtree(temp_dir, ignore_errors=True)

    self.addCleanup(cleanup)

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

    dir_path = os.path.dirname(os.path.realpath(__file__))  # dir of this file
    external_script = '%s/e2e_external.sh' % (dir_path)
    analysis.FLAGS.external_decider = external_script
    analysis.FLAGS.analysis_output_file = '/dev/null'

    actual = analysis.main(None)
    actual.pop('seed')  # nothing to check
    self.assertEqual(actual, expected)


if __name__ == '__main__':
  unittest.main()
