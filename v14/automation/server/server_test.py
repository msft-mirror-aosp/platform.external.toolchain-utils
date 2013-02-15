#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import sys
import server
import unittest
from utils import utils
import xmlrpclib


class ServerTest(unittest.TestCase):
  def setUp(self):
    pass


  def testGetAllJobs(self):
    s=server.Server("test_pool.csv")
    print s.GetAllJobs()


if __name__ == "__main__":
  unittest.main()

