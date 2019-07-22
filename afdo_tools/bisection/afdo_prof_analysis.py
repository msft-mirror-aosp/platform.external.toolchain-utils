#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""AFDO Profile analysis tool.

This script takes a good AFDO profile, a bad AFDO profile, and an external
script which deems particular AFDO profiles as GOOD/BAD/SKIP, and an output
file as arguments. Given these pieces of information, it analyzes the profiles
to try and determine what exactly is bad about the bad profile. It does this
with three main techniques: bisecting search, range search, and rough diff-ing.
"""

from __future__ import print_function

from absl import app
from absl import flags
from datetime import date
from enum import IntEnum
from tempfile import mkstemp

from afdo_parse import parse_afdo

import json
# Pylint recommends we use "from chromite.lib import cros_logging as logging".
# Chromite specific policy message, we want to keep using the standard logging
# pylint: disable=cros-logging-import
import logging
import os
import random
import subprocess
import sys
import time

flags.DEFINE_string('good_prof', None, 'Text-based "Good" profile for'
                    'analysis')
flags.DEFINE_string('bad_prof', None, 'Text-based "Bad" profile for' 'analysis')
flags.DEFINE_string(
    'external_decider', None, 'External script that, given an'
    'AFDO profile, returns GOOD/BAD/SKIP')
flags.DEFINE_string('analysis_output_file', None,
                    'File to output JSON results to')
flags.DEFINE_string(
    'state_file', '%s/afdo_analysis_state.json' % os.getcwd(),
    'File path containing state to load from initially, and '
    'will be overwritten with new state on each iteration')
flags.DEFINE_boolean(
    'no_resume', False, 'If enabled, no initial state will be '
    'loaded and the program will run from the beginning')
flags.DEFINE_boolean(
    'remove_state_on_completion', False, 'If enabled, state '
    'file will be removed once profile analysis is completed')
flags.DEFINE_float('seed', None, 'Float specifying seed for randomness')
FLAGS = flags.FLAGS


class StatusEnum(IntEnum):
  """Enum of valid statuses returned by profile decider."""
  GOOD_STATUS = 0
  BAD_STATUS = 1
  SKIP_STATUS = 125
  PROBLEM_STATUS = 127


statuses = StatusEnum.__members__.values()

_NUM_RUNS_RANGE_SEARCH = 20  # how many times range search should run its algo


def json_to_text(json_prof):
  text_profile = []
  for func in json_prof:
    text_profile.append(func)
    text_profile.append(json_prof[func])
  return ''.join(text_profile)


def prof_to_tmp(prof):
  """Creates (and returns) temp filename for given JSON-based AFDO profile."""
  fd, temp_path = mkstemp()
  text_profile = json_to_text(prof)
  with open(temp_path, 'w') as f:
    f.write(text_profile)
  os.close(fd)
  return temp_path


class DeciderState(object):
  """Class for the external decider."""

  def __init__(self, state_file):
    self.accumulated_results = []  # over this run of the script
    self.saved_results = []  # imported from a previous run of this script
    self.state_file = state_file
    self.seed = FLAGS.seed or time.time()

  def load_state(self):
    if not os.path.exists(self.state_file):
      logging.info('State file %s is empty, starting from beginning',
                   self.state_file)
      return

    with open(self.state_file) as f:
      try:
        data = json.load(f)
      except:
        raise ValueError('Provided state file %s to resume from does not'
                         ' contain a valid JSON.' % self.state_file)

    if 'seed' not in data or 'accumulated_results' not in data:
      raise ValueError('Provided state file %s to resume from does not contain'
                       ' the correct information' % self.state_file)

    self.seed = data['seed']
    self.saved_results = data['accumulated_results']
    logging.info('Restored state from %s...', self.state_file)

  def save_state(self):
    state = {'seed': self.seed, 'accumulated_results': self.accumulated_results}
    fd, tmp_file = mkstemp()
    os.close(fd)
    with open(tmp_file, 'w') as f:
      json.dump(state, f, indent=2)
    os.rename(tmp_file, self.state_file)
    logging.info('Logged state to %s...', self.state_file)

  def run(self, prof, save_run=True):
    """Run the external deciding script on the given profile."""
    if self.saved_results and save_run:
      result = self.saved_results.pop(0)
      self.accumulated_results.append(result)
      self.save_state()
      return StatusEnum(result)

    filename = prof_to_tmp(prof)

    try:
      return_code = subprocess.call([FLAGS.external_decider, filename])
    finally:
      os.remove(filename)

    if return_code in statuses:
      status = StatusEnum(return_code)
      if status == StatusEnum.PROBLEM_STATUS:
        prof_file = prof_to_tmp(prof)
        raise RuntimeError('Provided decider script returned PROBLEM_STATUS '
                           'when run on profile stored at %s. AFDO Profile '
                           'analysis aborting' % prof_file)
      if save_run:
        self.accumulated_results.append(status.value)
      logging.info('Run %d of external script %s returned %s',
                   len(self.accumulated_results), FLAGS.external_decider,
                   status.name)
      self.save_state()
      return status
    raise ValueError(
        'Provided external script had unexpected return code %d' % return_code)


def bisect_profiles(decider, good, bad, common_funcs, lo, hi):
  """Recursive function which bisects good and bad profiles.

  Args:
    decider: function which, given a JSON-based AFDO profile, returns an
      element of 'statuses' based on the status of the profile
    good: JSON-based good AFDO profile
    bad: JSON-based bad AFDO profile
    common_funcs: the list of functions which have top-level profiles in both
      'good' and 'bad'
    lo: lower bound of range being bisected on
    hi: upper bound of range being bisected on

  Returns a dictionary with two keys: 'individuals' and 'ranges'.
  'individuals': a list of individual functions found to make the profile BAD
  'ranges': a list of lists of function names. Each list of functions is a list
    such that including all of those from the bad profile makes the good
    profile BAD. It may not be the smallest problematic combination, but
    definitely contains a problematic combination of profiles.
  """

  results = {'individuals': [], 'ranges': []}
  if hi - lo <= 1:
    logging.info('Found %s as a problematic function profile', common_funcs[lo])
    results['individuals'].append(common_funcs[lo])
    return results

  mid = (lo + hi) / 2
  lo_mid_prof = good.copy()  # covers bad from lo:mid
  mid_hi_prof = good.copy()  # covers bad from mid:hi
  for func in common_funcs[lo:mid]:
    lo_mid_prof[func] = bad[func]
  for func in common_funcs[mid:hi]:
    mid_hi_prof[func] = bad[func]

  lo_mid_verdict = decider.run(lo_mid_prof)
  mid_hi_verdict = decider.run(mid_hi_prof)

  if lo_mid_verdict == StatusEnum.BAD_STATUS:
    result = bisect_profiles(decider, good, bad, common_funcs, lo, mid)
    results['individuals'].extend(result['individuals'])
    results['ranges'].extend(result['ranges'])
  if mid_hi_verdict == StatusEnum.BAD_STATUS:
    result = bisect_profiles(decider, good, bad, common_funcs, mid, hi)
    results['individuals'].extend(result['individuals'])
    results['ranges'].extend(result['ranges'])

  # neither half is bad -> the issue is caused by several things occuring
  # in conjunction, and this combination crosses 'mid'
  if lo_mid_verdict == mid_hi_verdict == StatusEnum.GOOD_STATUS:
    problem_range = range_search(decider, good, bad, common_funcs, lo, hi)
    if problem_range:
      logging.info('Found %s as a problematic combination of profiles',
                   str(problem_range))
      results['ranges'].append(problem_range)

  return results


def bisect_profiles_wrapper(decider, good, bad, perform_check=True):
  """Wrapper for recursive profile bisection."""

  # Validate good and bad profiles are such, otherwise bisection reports noise
  # Note that while decider is a random mock, these assertions may fail.
  if perform_check:
    if decider.run(good, save_run=False) != StatusEnum.GOOD_STATUS:
      raise ValueError("Supplied good profile is not actually GOOD")
    if decider.run(bad, save_run=False) != StatusEnum.BAD_STATUS:
      raise ValueError("Supplied bad profile is not actually BAD")

  common_funcs = sorted(func for func in good if func in bad)
  if not common_funcs:
    return {'ranges': [], 'individuals': []}

  # shuffle because the results of our analysis can be quite order-dependent
  # but this list has no inherent ordering. By shuffling each time, the chances
  # of finding new, potentially interesting results are increased each time
  # the program is run
  random.shuffle(common_funcs)
  results = bisect_profiles(decider, good, bad, common_funcs, 0,
                            len(common_funcs))
  results['ranges'].sort()
  results['individuals'].sort()
  return results


def range_search(decider, good, bad, common_funcs, lo, hi):
  """Searches for problematic range crossing mid border.

  The main inner algorithm is the following, which looks for the smallest
  possible ranges with problematic combinations. It starts the upper bound at
  the midpoint, and increments in halves until it gets a BAD profile.
  Then, it increments the lower bound (in halves) until the resultant profile
  is GOOD, and then we have a range that causes 'BAD'ness.

  It does this _NUM_RUNS_RANGE_SEARCH times, and shuffles the functions being
  looked at uniquely each time to try and get the smallest possible range
  of functions in a reasonable timeframe.
  """

  average = lambda x, y: int(round((x + y) / 2.0))

  def find_upper_border(good_copy, funcs, lo, hi, last_bad_val=None):
    """Finds the upper border of problematic range."""
    mid = average(lo, hi)
    if mid == lo or mid == hi:
      return last_bad_val or hi

    for func in funcs[lo:mid]:
      good_copy[func] = bad[func]
    verdict = decider.run(good_copy)

    # reset for next iteration
    for func in funcs:
      good_copy[func] = good[func]

    if verdict == StatusEnum.BAD_STATUS:
      return find_upper_border(good_copy, funcs, lo, mid, mid)
    return find_upper_border(good_copy, funcs, mid, hi, last_bad_val)

  def find_lower_border(good_copy, funcs, lo, hi, last_bad_val=None):
    """Finds the lower border of problematic range."""
    mid = average(lo, hi)
    if mid == lo or mid == hi:
      return last_bad_val or lo

    for func in funcs[lo:mid]:
      good_copy[func] = good[func]
    verdict = decider.run(good_copy)

    # reset for next iteration
    for func in funcs:
      good_copy[func] = bad[func]

    if verdict == StatusEnum.BAD_STATUS:
      return find_lower_border(good_copy, funcs, mid, hi, lo)
    return find_lower_border(good_copy, funcs, lo, mid, last_bad_val)

  lo_mid_funcs = []
  mid_hi_funcs = []
  min_range_funcs = []
  for _ in range(_NUM_RUNS_RANGE_SEARCH):

    if min_range_funcs:  # only examine range we've already narrowed to
      random.shuffle(lo_mid_funcs)
      random.shuffle(mid_hi_funcs)
    else:  # consider lo-mid and mid-hi separately bc must cross border
      mid = (lo + hi) / 2
      lo_mid_funcs = common_funcs[lo:mid]
      mid_hi_funcs = common_funcs[mid:hi]

    funcs = lo_mid_funcs + mid_hi_funcs
    hi = len(funcs)
    mid = len(lo_mid_funcs)
    lo = 0

    # because we need the problematic pair to pop up before we can narrow it
    prof = good.copy()
    for func in lo_mid_funcs:
      prof[func] = bad[func]

    upper_border = find_upper_border(prof, funcs, mid, hi)
    for func in lo_mid_funcs + funcs[mid:upper_border]:
      prof[func] = bad[func]

    lower_border = find_lower_border(prof, funcs, lo, mid)
    curr_range_funcs = funcs[lower_border:upper_border]

    if not min_range_funcs or len(curr_range_funcs) < len(min_range_funcs):
      min_range_funcs = curr_range_funcs
      lo_mid_funcs = lo_mid_funcs[lo_mid_funcs.index(min_range_funcs[0]):]
      mid_hi_funcs = mid_hi_funcs[:mid_hi_funcs.index(min_range_funcs[-1]) + 1]
      if len(min_range_funcs) == 2:
        min_range_funcs.sort()
        return min_range_funcs  # can't get any smaller

  min_range_funcs.sort()
  return min_range_funcs


def check_good_not_bad(decider, good, bad):
  """Check if bad prof becomes GOOD by adding funcs it lacks from good prof"""
  bad_copy = bad.copy()
  for func in good:
    if func not in bad:
      bad_copy[func] = good[func]
  return decider.run(bad_copy) == StatusEnum.GOOD_STATUS


def check_bad_not_good(decider, good, bad):
  """Check if good prof BAD after adding funcs bad prof has that good doesnt"""
  good_copy = good.copy()
  for func in bad:
    if func not in good:
      good_copy[func] = bad[func]
  return decider.run(good_copy) == StatusEnum.BAD_STATUS


def main(_):

  if not FLAGS.no_resume and FLAGS.seed:  # conflicting seeds
    raise RuntimeError('Ambiguous seed value; do not resume from existing '
                       'state and also specify seed by command line flag')

  decider = DeciderState(FLAGS.state_file)
  if not FLAGS.no_resume:
    decider.load_state()
  random.seed(decider.seed)

  with open(FLAGS.good_prof) as good_f:
    good_items = parse_afdo(good_f)
  with open(FLAGS.bad_prof) as bad_f:
    bad_items = parse_afdo(bad_f)

  bisect_results = bisect_profiles_wrapper(decider, good_items, bad_items)
  gnb_result = check_good_not_bad(decider, good_items, bad_items)
  bng_result = check_bad_not_good(decider, good_items, bad_items)

  results = {
      'seed': decider.seed,
      'bisect_results': bisect_results,
      'good_only_functions': gnb_result,
      'bad_only_functions': bng_result
  }
  with open(FLAGS.analysis_output_file, 'wb') as f:
    json.dump(results, f, indent=2)
  if FLAGS.remove_state_on_completion:
    os.remove(FLAGS.state_file)
    logging.info('Removed state file %s following completion of script...',
                 FLAGS.state_file)
  else:
    completed_state_file = '%s.completed.%s' % (FLAGS.state_file,
                                                str(date.today()))
    os.rename(FLAGS.state_file, completed_state_file)
    logging.info('Stored completed state file as %s...', completed_state_file)
  return results


if __name__ == '__main__':
  flags.mark_flag_as_required('good_prof')
  flags.mark_flag_as_required('bad_prof')
  flags.mark_flag_as_required('external_decider')
  flags.mark_flag_as_required('analysis_output_file')
  app.run(main)
else:
  FLAGS(sys.argv)
