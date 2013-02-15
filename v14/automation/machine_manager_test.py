#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine_description
import machine_filters
import machine_manager
import machine_pool
import unittest


class MachineManagerTest(unittest.TestCase):
  def setUp(self):
    self.machine_manager = machine_manager.MachineManager()


  def testPrint(self):
    print str(self.machine_manager)


  def testGetLinuxBox(self):
    descriptions = []
    
    filters = []
    filters.append(machine_filters.OSFilter("linux"))
    description = machine_description.MachineDescription(filters)
    descriptions.append(description)
    machines = self.machine_manager.GetMachines(descriptions)
    print machines
    
    
  def testGetChromeOSBox(self):
    descriptions = []
    filters = []
    filters.append(machine_filters.OSFilter("cHrOmEOS"))
    description = machine_description.MachineDescription(filters)
    descriptions.append(description)
    machines = self.machine_manager.GetMachines(descriptions)
    self.assertTrue(len(machines) != 0)
    
    pool = machine_pool.MachinePool(machines)
    print pool


if __name__ == "__main__":
  unittest.main()

