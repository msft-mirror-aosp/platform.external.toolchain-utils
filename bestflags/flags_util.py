# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions to explore the neighbor flags.

Part of the Chrome build flags optimization.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'


import flags
from flags import Flag


def ClimbNext(flags_dict, climb_spec):
  """Get the flags who are different from flags_dict by climb_spec.

  Args:
    flags_dict: The dictionary containing the original flags whose neighbors are
      to be explored.
    climb_spec: The spec in the flags_dict is to be changed.

  Returns:
    A dictionary of neighbor flags.
  """

  result = flags.Search(climb_spec)

  # If the flags do not contain the spec.
  if climb_spec not in flags_dict:
    results = flags_dict.copy()

    if result:
      # Numeric flags.
      results[climb_spec] = Flag(climb_spec, int(result.group('start')))
    else:
      # Boolean flags.
      results[climb_spec] = Flag(climb_spec)

    return [results]

  # The flags contain the spec.
  if not result:
    # Boolean flags.
    results = flags_dict.copy()
    del results[climb_spec]
    return [results]

  # Numeric flags.
  flag = flags_dict[climb_spec]

  # The value of the flag having spec.
  value = flag.GetValue()
  results = []

  if value + 1 < int(result.group('end')):
    # If the value is not the end value, explore the value that is 1 larger than
    # the current value.
    neighbor = flags_dict.copy()
    neighbor[climb_spec] = Flag(climb_spec, value + 1)
    results.append(neighbor)

  if value > int(result.group('start')):
    # If the value is not the start value, explore the value that is 1 lesser
    # than the current value.
    neighbor = flags_dict.copy()
    neighbor[climb_spec] = Flag(climb_spec, value - 1)
    results.append(neighbor)
  else:
    # Delete the value.
    neighbor = flags_dict.copy()
    del neighbor[climb_spec]
    results.append(neighbor)

  return results
