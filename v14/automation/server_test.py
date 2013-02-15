#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import server
import unittest
from utils import utils
import xmlrpclib


class ServerTest(unittest.TestCase):
  def setUp(self):
    self.server = server.Server()


  def testGetAllJobs(self):
    print server.GetAllJobs()


if __name__ == "__main__":
  unittest.main()

