#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""lock_machine.py related unit-tests.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import lock_machine
import unittest


class MachineTest(unittest.TestCase):
  def setUp(self):
    pass


  def testRepeatedUnlock(self):
    mach = lock_machine.Machine("qqqraymes.mtv")
    for i in range(10):
      self.assertFalse(mach.Unlock())

  def testLockUnlock(self):
    mach = lock_machine.Machine("otter.mtv", "/tmp")
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=True))
      self.assertTrue(mach.Unlock(exclusive=True))

  def testSharedLock(self):
    mach = lock_machine.Machine("chrotomation.mtv")
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=False))
    for i in range(10):
      self.assertTrue(mach.Unlock(exclusive=False))
    self.assertTrue(mach.Lock(exclusive=True))
    self.assertTrue(mach.Unlock(exclusive=True))

  def testExclusiveLock(self):
    mach = lock_machine.Machine("atree.mtv")
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=True))
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

  def testExclusiveState(self):
    mach = lock_machine.Machine("testExclusiveState")
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

if __name__ == "__main__":
  unittest.main()
