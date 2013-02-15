#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine
import unittest


class MachineTest(unittest.TestCase):
  def setUp(self):
    pass


  def testPrintMachine(self):
    m = machine.Machine("ahmad.mtv", "core2duo", 4, "linux", "asharif")
    machine_string = str(m)
    self.assertTrue("ahmad.mtv" in machine_string)


if __name__ == "__main__":
  unittest.main()

