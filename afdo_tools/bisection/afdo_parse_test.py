#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for afdo_parse."""

from __future__ import print_function

import StringIO
import unittest

import afdo_parse


class SimpleAfdoParseTest(unittest.TestCase):
  """Test class for AFDO parsing."""

  def test_parse_afdo(self):
    test_data = StringIO.StringIO('deflate_slow:87460059:3\n'
                                  ' 3: 24\n'
                                  ' 14: 54767\n'
                                  ' 15: 664 fill_window:22\n'
                                  ' 16: 661\n'
                                  ' 19: 637\n'
                                  ' 41: 36692 longest_match:36863\n'
                                  ' 44: 36692\n'
                                  ' 44.2: 5861\n'
                                  ' 46: 13942\n'
                                  ' 46.1: 14003\n')
    expected = {
        'deflate_slow': ' 3: 24\n'
                        ' 14: 54767\n'
                        ' 15: 664 fill_window:22\n'
                        ' 16: 661\n'
                        ' 19: 637\n'
                        ' 41: 36692 longest_match:36863\n'
                        ' 44: 36692\n'
                        ' 44.2: 5861\n'
                        ' 46: 13942\n'
                        ' 46.1: 14003\n'
    }
    actual = afdo_parse.parse_afdo(test_data)
    self.assertEqual(actual, expected)
    test_data.close()

  def test_parse_empty_afdo(self):
    expected = {}
    actual = afdo_parse.parse_afdo('')
    self.assertEqual(actual, expected)


if __name__ == '__main__':
  unittest.main()
