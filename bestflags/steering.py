# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Genetic Algorithm implementation for selecting good flags.

Part of the Chrome build flags optimization.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'


class Steering(object):
  """The steering algorithm that produce the next generation to be run."""

  def __init__(self, steps):
    """Set up the number of steps generations this algorithm should evolve.

    Args:
      steps: number of steps that the feed back loop should perform
    """

    self._steps = steps

  def Run(self, generation):
    """Generate a set of new generations for the next round of execution.

    Args:
      generation: the previous generation.
    """

    pass
