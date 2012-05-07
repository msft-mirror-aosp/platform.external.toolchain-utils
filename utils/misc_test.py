# Copyright 2012 Google Inc. All Rights Reserved.

"""Tests for misc."""

__author__ = 'asharif@google.com (Ahmad Sharif)'

# System modules
import re
import unittest

# Local modules
import misc


class UtilsTest(unittest.TestCase):
  def testGetFilenameFromString(self):
    string = 'a /b=c"d'
    filename = misc.GetFilenameFromString(string)
    self.assertTrue(filename == 'a___bcd')

if __name__ == '__main__':
  unittest.main()
