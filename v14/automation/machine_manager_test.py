#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine_description
import machine_manager
import unittest


class MachineManagerTest(unittest.TestCase):
  def setUp(self):
    self.machine_manager = machine_manager.MachineManager()


  def testPrint(self):
    print str(self.machine_manager)


  def testGetLinuxBox(self):
    descriptions = []
    description = machine_description.MachineDescription("", "linux", False)
    descriptions.append(description)
    machines = self.machine_manager.GetMachines(descriptions)
    self.assertTrue(len(machines) != 0)
    print machines
    
    
  def testGetChromeOSBox(self):
    descriptions = []
    description = machine_description.MachineDescription("", "linux", False)
    descriptions.append(description)
    machines = self.machine_manager.GetMachines(descriptions)
    self.assertTrue(len(machines) != 0)


if __name__ == "__main__":
  unittest.main()

