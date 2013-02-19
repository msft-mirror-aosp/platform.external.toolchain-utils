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

  def testPrependMergeEnv(self):
    var = 'USE'
    use_flags = 'hello 123'
    added_use_flags = 'bla bla'
    env_string = '%s=%r' % (var, use_flags)
    new_env_string = misc.MergeEnvStringWithDict(env_string,
                                                 {var: added_use_flags})
    expected_new_env = '%s=%r' % (var, ' '.join([added_use_flags, use_flags]))
    self.assertTrue(new_env_string == ' '.join([env_string, expected_new_env]))

  def testPostpendMergeEnv(self):
    var = 'USE'
    use_flags = 'hello 123'
    added_use_flags = 'bla bla'
    env_string = '%s=%r' % (var, use_flags)
    new_env_string = misc.MergeEnvStringWithDict(env_string,
                                                 {var: added_use_flags},
                                                 False)
    expected_new_env = '%s=%r' % (var, ' '.join([use_flags, added_use_flags]))
    self.assertTrue(new_env_string == ' '.join([env_string, expected_new_env]))

if __name__ == '__main__':
  unittest.main()
