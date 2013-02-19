#!/usr/bin/python

# Copyright 2012 Google Inc. All Rights Reserved.

"""Unittest for machine_manager."""
import unittest

import label
import machine_manager


class MyMachineManager(machine_manager.MachineManager):

  def __init__(self, chromeos_root):
    super(MyMachineManager, self).__init__(chromeos_root, 0)

  def _TryToLockMachine(self, cros_machine):
    self._machines.append(cros_machine)
    cros_machine.checksum = ""

  def AddMachine(self, machine_name):
    with self._lock:
      for m in self._all_machines:
        assert m.name != machine_name, "Tried to double-add %s" % machine_name
      cm = machine_manager.MockCrosMachine(machine_name, self.chromeos_root)
      assert cm.machine_checksum, ("Could not find checksum for machine %s" %
                                   machine_name)
      self._all_machines.append(cm)

CHROMEOS_ROOT = "/tmp/chromeos-root"
MACHINE_NAMES = ["lumpy1", "lumpy2", "lumpy3", "daisy1", "daisy2"]
LABEL_LUMPY = label.MockLabel("lumpy", "image", CHROMEOS_ROOT, "lumpy",
                              ["lumpy1", "lumpy2", "lumpy3", "lumpy4"], "")
LABEL_MIX = label.MockLabel("mix", "image", CHROMEOS_ROOT, "mix",
                            ["daisy1", "daisy2", "lumpy3", "lumpy4"], "")


class MachineManagerTest(unittest.TestCase):

  def testAreAllMachineSame(self):
    manager = MyMachineManager(CHROMEOS_ROOT)
    for m in MACHINE_NAMES:
      manager.AddMachine(m)
    self.assertEqual(manager.AreAllMachineSame(LABEL_LUMPY), True)
    self.assertEqual(manager.AreAllMachineSame(LABEL_MIX), False)

  def testGetMachines(self):
    manager = MyMachineManager(CHROMEOS_ROOT)
    for m in MACHINE_NAMES:
      manager.AddMachine(m)
    names = [m.name for m in manager.GetMachines(LABEL_LUMPY)]
    self.assertEqual(names, ["lumpy1", "lumpy2", "lumpy3"])

  def testGetAvailableMachines(self):
    manager = MyMachineManager(CHROMEOS_ROOT)
    for m in MACHINE_NAMES:
      manager.AddMachine(m)
    for m in manager._all_machines:
      if int(m.name[-1]) % 2:
        manager._TryToLockMachine(m)
    names = [m.name for m in manager.GetAvailableMachines(LABEL_LUMPY)]
    self.assertEqual(names, ["lumpy1", "lumpy3"])

if __name__ == "__main__":
  unittest.main()
