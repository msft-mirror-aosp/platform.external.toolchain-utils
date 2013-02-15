#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager class definition.

Machine manager manages machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine
import machine_pools
import pools
import sys


class LockInfo:
  def __init__(self):
    self.expires = 0


class MachineManager:
  __shared_state = {}
  global_pool = None
  locks = {}
  def __init__(self):
    self.__dict__ = self.__shared_state
    if self.global_pool == None:
      self.ConstructGlobalPool()
    self.lock_path = "/home/ahmad/"


  def __str__(self):
    return str(self.global_pool)


  def ConstructGlobalPool(self):
    reload(pools)

    # First populate the global pool.
    self.global_pool = machine_pools.MachinePool()
    for key, value in pools.machines.iteritems():
      m = machine.Machine(key,
                          value[0],
                          value[1],
                          value[2])
      self.global_pool.AddMachine(m)

    # Then populate the named pools.
    self.named_pools = []
    for key, value in pools.named_pools.iteritems():
      name_list_filter = machine_pools.NameListFilter(value)
      named_pool = name_list_filter.FilterPool(self.global_pool)
      named_pool.SetName(key)
      self.named_pools.append(named_pool)


  def LockMachine(self, machine, key, timeout):
    command = ("mkdir %s/%s && mkdir %s/%s/%s" % 
               (self.lock_path, machine.name,
                self.lock_path, machine.name, key))
    print command
    self.locks[machine.name] = LockInfo()
    machine.locked = True
    return True


  def UnlockMachine(self, machine, key, timeout):
    key_path = self.lock_path + "/" + machine.name + "/" + key
    if False == os.path.exists(key_path):
      raise Error("Could not unlock machine: %s with key: %s"
                  % (machine.name, key))
    command = "rm -rf " + self.lock_path + "/" + machine.name
    if 0 != RunCommand(command):
      raise Error("Could not execute command: %s" % command)


  def GetMachine(self, filters, lock, key, timeout):
    machine_pool = self.global_pool
    if True == lock:
      unlocked_filter = machine_pools.UnlockedFilter()
      filters.append(unlocked_filter)

    for f in filters:
      machine_pool = f.FilterPool(machine_pool)

    if 0 == machine_pool.Size():
      return None

    machine = machine_pool.GetLightestLoad()

    if True == lock:
      if False == self.LockMachine(machine, key, timeout):
        return None

    return machine

  
  def GetChromeOSMachine(self, lock=False, key="", timeout=200):
    filters = []
    cros_filter = machine_pools.ChromeOSFilter()
    filters.append(cros_filter)

    return self.GetMachine(filters, lock, key, timeout)

  
  def GetLinuxMachine(self, lock=False, key="", timeout=200):
    filters = []
    linux_filter = machine_pools.LinuxFilter()
    filters.append(linux_filter)

    return self.GetMachine(filters, lock, key, timeout)


def Main(argv):
  print "In MachineManager."
  mm = MachineManager()
  print mm
  cros_machine = mm.GetChromeOSMachine()
  print cros_machine.name
  cros_machine = mm.GetChromeOSMachine()
  print cros_machine.name
  cros_machine = mm.GetChromeOSMachine(lock=True, key="123")
  print cros_machine.name
  cros_machine = mm.GetChromeOSMachine(lock=True, key="333")
  print cros_machine.name
  cros_machine = mm.GetChromeOSMachine()
  print cros_machine.name
  cros_machine = mm.GetChromeOSMachine()
  print cros_machine.name
  print mm


if __name__ == "__main__":
  Main(sys.argv)

