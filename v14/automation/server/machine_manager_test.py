#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

__author__ = "asharif@google.com (Ahmad Sharif)"


from automation.common.machine_description import MachineSpecification
import machine_manager
import unittest
from utils import utils


class MachineManagerTest(unittest.TestCase):
  """ Machine manager tests. """

  def setUp(self):
    self.machine_manager = machine_manager.MachineManager()


  def testPrint(self):
    print self.machine_manager


  def testGetLinuxBox(self):
    mach_spec_list = [ MachineSpecification(os="linux") ]
    machines = self.machine_manager.GetMachines(mach_spec_list)
    self.assertTrue(machines)


  def testGetChromeOSBox(self):
    mach_spec_list = [ MachineSpecification(os="chromeos") ]
    machines = self.machine_manager.GetMachines(mach_spec_list)
    self.assertTrue(machines)


if __name__ == "__main__":
  unittest.main()
