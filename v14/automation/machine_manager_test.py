#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine
import machine_filters
import machine_manager
import machine_pool
import os
import pools
import sys
import unittest
from utils import utils


class MachineManagerTest(unittest.TestCase):
  def setUp(self):
    self.machine_manager = machine_manager.MachineManager()


  def testPrint(self):
    print str(self.machine_manager)


if __name__ == "__main__":
  unittest.main()

