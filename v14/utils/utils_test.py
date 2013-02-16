# Copyright 2012 Google Inc. All Rights Reserved.

"""Tests for utils."""

__author__ = 'asharif@google.com (Ahmad Sharif)'

import re
import unittest
import utils


class UtilsTest(unittest.TestCase):
  def testGetFilenameFromString(self):
    string = 'a /b=c"d'
    filename = utils.GetFilenameFromString(string)
    self.assertTrue(filename == 'a___bcd')

if __name__ == '__main__':
  unittest.main()
