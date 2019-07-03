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
with three main techniques: bisecting search, non-bisecting search, and rough
diff-ing.
"""

from __future__ import print_function

from absl import app
from absl import flags
from tempfile import mkstemp

from afdo_parse import parse_afdo

import json
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
flags.DEFINE_integer('seed', None, 'Integer specifying seed for randomness')
FLAGS = flags.FLAGS

GOOD_STATUS = 0
BAD_STATUS = 1
SKIP_STATUS = 125
PROBLEM_STATUS = 127

# Variables for non_bisecting search
# for how many times non-bisecting search should run its algo
_NUM_RUNS = 20
# for how many new functions it should add at once
# note that this will be unnecessary once non_bisecting_search TODO addressed
_FUNC_STEP = 5


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


def run_external(prof):
  """Run the external deciding script on the given profile."""
  filename = prof_to_tmp(prof)

  try:
    child = subprocess.Popen([FLAGS.external_decider, filename])
    child.communicate()
  except:
    raise  # the error of try block
  finally:
    os.remove(filename)

  return_code = child.returncode
  if return_code in (GOOD_STATUS, BAD_STATUS, SKIP_STATUS, PROBLEM_STATUS):
    return return_code
  raise ValueError(
      'Provided external script had unexpected return code %d' % return_code)


def bisect_profiles(good, bad, common_funcs, lo, hi):
  """Recursive function which bisects good and bad profiles.

  Args:
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
    results['individuals'].append(common_funcs[lo])
    return results

  mid = (lo + hi) / 2
  lo_mid_prof = good.copy()  # covers bad from lo:mid
  mid_hi_prof = good.copy()  # covers bad from mid:hi
  for func in common_funcs[lo:mid]:
    lo_mid_prof[func] = bad[func]
  for func in common_funcs[mid:hi]:
    mid_hi_prof[func] = bad[func]

  lo_mid_verdict = run_external(lo_mid_prof)
  mid_hi_verdict = run_external(mid_hi_prof)

  if lo_mid_verdict == BAD_STATUS:
    result = bisect_profiles(good, bad, common_funcs, lo, mid)
    results['individuals'].extend(result['individuals'])
    results['ranges'].extend(result['ranges'])
  if mid_hi_verdict == BAD_STATUS:
    result = bisect_profiles(good, bad, common_funcs, mid, hi)
    results['individuals'].extend(result['individuals'])
    results['ranges'].extend(result['ranges'])

  # neither half is bad -> the issue is caused by several things occuring
  # in conjunction, and this combination crosses 'mid'
  if lo_mid_verdict == mid_hi_verdict == GOOD_STATUS:
    problem_range = non_bisecting_search(good, bad, common_funcs, lo, hi)
    if problem_range:
      results['ranges'].append(problem_range)

  return results


def bisect_profiles_wrapper(good, bad, perform_check=True):
  """Wrapper for recursive profile bisection."""

  # Validate good and bad profiles are such, otherwise bisection reports noise
  # Note that while run_external is a random mock, these assertions may fail.
  if perform_check:
    if run_external(good) != GOOD_STATUS:
      raise ValueError("Supplied good profile is not actually GOOD")
    if run_external(bad) != BAD_STATUS:
      raise ValueError("Supplied bad profile is not actually BAD")

  common_funcs = sorted(func for func in good if func in bad)
  if not common_funcs:
    return {'ranges': [], 'individuals': []}

  # shuffle because the results of our analysis can be quite order-dependent
  # but this list has no inherent ordering. By shuffling each time, the chances
  # of finding new, potentially interesting results are increased each time
  # the program is run
  random.shuffle(common_funcs)
  results = bisect_profiles(good, bad, common_funcs, 0, len(common_funcs))
  results['ranges'].sort()
  results['individuals'].sort()
  return results


# TODO(emmavukelj): make this O(logn) instead of O(n) by halving the searched
# range instead of linearly incrementing. And also search from middle of range
def non_bisecting_search(good, bad, common_funcs, lo, hi):
  """Searches for problematic range without bisecting.

  The main inner algorithm is the following, which looks for the smallest
  possible ranges with problematic combinations. It starts the upper bound at
  the midpoint, and increments this until it gets a BAD profile.
  Then, it increments the lower bound until the resultant profile is GOOD, and
  then we have a range that causes 'BAD'ness.

  It does this _NUM_NONBISECT_RUNS times, and shuffles the functions being
  looked at uniquely each time to try and get the smallest possible range
  of functions but in a reasonable timeframe.
  """

  lo_mid_funcs = []
  mid_hi_funcs = []
  min_range_funcs = []
  for _ in range(_NUM_RUNS):

    if min_range_funcs:  # only examine range we've already narrowed to
      lo_mid_funcs = lo_mid_funcs[lo_mid_funcs.index(min_range_funcs[0]):]
      mid_hi_funcs = mid_hi_funcs[:mid_hi_funcs.index(min_range_funcs[-1]) + 1]
      # shuffle to hopefully find smaller problem range
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
    good_copy = good.copy()
    for func in lo_mid_funcs:
      good_copy[func] = bad[func]

    for upper in range(mid, hi):  # find upper border of bad combination
      upper_func = funcs[upper]
      good_copy[upper_func] = bad[upper_func]
      if ((upper % _FUNC_STEP == 0 or upper == hi - 1) and
          run_external(good_copy) == BAD_STATUS):

        # find lower border of bad combination
        for lower in range(mid):
          lower_func = funcs[lower]
          good_copy[lower_func] = good[lower_func]
          if ((lower % _FUNC_STEP == 0 or lower == mid - 1) and
              run_external(good_copy) == GOOD_STATUS):

            lower = max(0, lower - _FUNC_STEP + 1)  # +1 b/c current included
            if not min_range_funcs or (upper - lower) < len(min_range_funcs):
              # b/c upper func included
              min_range_funcs = funcs[lower:upper + 1]
              if len(min_range_funcs) == 2:
                min_range_funcs.sort()
                return min_range_funcs  # can't get any smaller
              break

  min_range_funcs.sort()
  return min_range_funcs


def check_good_not_bad(good, bad):
  """Check if bad prof becomes GOOD by adding funcs it lacks from good prof"""
  bad_copy = bad.copy()
  for func in good:
    if func not in bad:
      bad_copy[func] = good[func]
  return run_external(bad_copy) == GOOD_STATUS


def check_bad_not_good(good, bad):
  """Check if good prof BAD after adding funcs bad prof has that good doesnt"""
  good_copy = good.copy()
  for func in bad:
    if func not in good:
      good_copy[func] = bad[func]
  return run_external(good_copy) == BAD_STATUS


def main(_):
  with open(FLAGS.good_prof) as good_f:
    good_items = parse_afdo(good_f)
  with open(FLAGS.bad_prof) as bad_f:
    bad_items = parse_afdo(bad_f)

  seed = FLAGS.seed
  if not FLAGS.seed:
    seed = time.time()
  random.seed(seed)

  bisect_results = bisect_profiles_wrapper(good_items, bad_items)
  gnb_result = check_good_not_bad(good_items, bad_items)
  bng_result = check_bad_not_good(good_items, bad_items)

  results = {
      'seed': seed,
      'bisect_results': bisect_results,
      'good_only_functions': gnb_result,
      'bad_only_functions': bng_result
  }
  with open(FLAGS.analysis_output_file, 'wb') as f:
    json.dump(results, f, indent=2)
  return results


if __name__ == '__main__':
  flags.mark_flag_as_required('good_prof')
  flags.mark_flag_as_required('bad_prof')
  flags.mark_flag_as_required('external_decider')
  flags.mark_flag_as_required('analysis_output_file')
  app.run(main)
else:
  FLAGS(sys.argv)
