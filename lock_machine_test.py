# Copyright 2010 Google Inc. All Rights Reserved.
"""lock_machine.py related unit-tests.

MachineManagerTest tests MachineManager.
"""

__author__ = 'asharif@google.com (Ahmad Sharif)'

from multiprocessing import Process
import time
import unittest

import lock_machine


def LockAndSleep(machine):
  lock_machine.Machine(machine, auto=True).Lock(exclusive=True)
  time.sleep(1)


class MachineTest(unittest.TestCase):

  def setUp(self):
    pass

  def testRepeatedUnlock(self):
    mach = lock_machine.Machine('qqqraymes.mtv')
    for i in range(10):
      self.assertFalse(mach.Unlock())
    mach = lock_machine.Machine('qqqraymes.mtv', auto=True)
    for i in range(10):
      self.assertFalse(mach.Unlock())

  def testLockUnlock(self):
    mach = lock_machine.Machine('otter.mtv', '/tmp')
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=True))
      self.assertTrue(mach.Unlock(exclusive=True))

    mach = lock_machine.Machine('otter.mtv', '/tmp', True)
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=True))
      self.assertTrue(mach.Unlock(exclusive=True))

  def testSharedLock(self):
    mach = lock_machine.Machine('chrotomation.mtv')
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=False))
    for i in range(10):
      self.assertTrue(mach.Unlock(exclusive=False))
    self.assertTrue(mach.Lock(exclusive=True))
    self.assertTrue(mach.Unlock(exclusive=True))

    mach = lock_machine.Machine('chrotomation.mtv', auto=True)
    for i in range(10):
      self.assertTrue(mach.Lock(exclusive=False))
    for i in range(10):
      self.assertTrue(mach.Unlock(exclusive=False))
    self.assertTrue(mach.Lock(exclusive=True))
    self.assertTrue(mach.Unlock(exclusive=True))

  def testExclusiveLock(self):
    mach = lock_machine.Machine('atree.mtv')
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=True))
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

    mach = lock_machine.Machine('atree.mtv', auto=True)
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=True))
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

  def testExclusiveState(self):
    mach = lock_machine.Machine('testExclusiveState')
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

    mach = lock_machine.Machine('testExclusiveState', auto=True)
    self.assertTrue(mach.Lock(exclusive=True))
    for i in range(10):
      self.assertFalse(mach.Lock(exclusive=False))
    self.assertTrue(mach.Unlock(exclusive=True))

  def testAutoLockGone(self):
    mach = lock_machine.Machine('lockgone', auto=True)
    p = Process(target=LockAndSleep, args=('lockgone',))
    p.start()
    time.sleep(1.1)
    p.join()
    self.assertTrue(mach.Lock(exclusive=True))

  def testAutoLockFromOther(self):
    mach = lock_machine.Machine('other_lock', auto=True)
    p = Process(target=LockAndSleep, args=('other_lock',))
    p.start()
    time.sleep(0.5)
    self.assertFalse(mach.Lock(exclusive=True))
    p.join()
    time.sleep(0.6)
    self.assertTrue(mach.Lock(exclusive=True))

  def testUnlockByOthers(self):
    mach = lock_machine.Machine('other_unlock', auto=True)
    p = Process(target=LockAndSleep, args=('other_unlock',))
    p.start()
    time.sleep(0.5)
    self.assertTrue(mach.Unlock(exclusive=True))
    self.assertTrue(mach.Lock(exclusive=True))


if __name__ == '__main__':
  unittest.main()
