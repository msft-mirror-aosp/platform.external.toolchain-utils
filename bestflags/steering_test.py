# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Steering stage unittest.

Part of the Chrome build flags optimization.
"""

__author__ = 'yuhenglong@google.com (Yuheng Long)'

import unittest

import steering


class SteeringTest(unittest.TestCase):
  """This class test the Steering class.

  This steering algorithm should stop either it has generated a certain number
  of generations or the generation has no further improvement.
  """

  def setUp(self):
    pass

  def testGeneration(self):
    """"Test proper termination for a number of generations."""
    pass

  def testImprove(self):
    """"Test proper termination for no improvement between generations."""
    pass

if __name__ == '__main__':
  unittest.main()
