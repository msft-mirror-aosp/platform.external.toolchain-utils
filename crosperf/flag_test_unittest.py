#!/usr/bi/python
#
# Copyright 2014 Google Inc. All Rights Reserved.

import test_flag

import unittest

class FlagTestCase(unittest.TestCase):

  def test_test_flag(self):
    # Verify that test_flag._is_test exists, that it is a list,
    # and that it contains 1 element.
    self.assertTrue(type(test_flag._is_test) is list)
    self.assertEqual(len(test_flag._is_test), 1)


    # Verify that the getting the flag works and that the flag
    # contains False, its starting value.
    save_flag = test_flag.GetTestMode()
    self.assertFalse(save_flag)

    # Verify that setting the flat to True, then getting it, works.
    test_flag.SetTestMode(True)
    self.assertTrue(test_flag.GetTestMode())

    # Verify that setting the flag to False, then getting it, works.
    test_flag.SetTestMode(save_flag)
    self.assertFalse(test_flag.GetTestMode())

    # Verify that test_flag._is_test still exists, that it still is a
    # list, and that it still contains 1 element.
    self.assertTrue(type(test_flag._is_test) is list)
    self.assertEqual(len(test_flag._is_test), 1)


if __name__ == '__main__':
  unittest.main()
