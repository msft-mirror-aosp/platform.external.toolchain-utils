#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

from machine_pool import MachinePool

class MachinePoolFilter:
  def FilterPool(self, machine_pool):
    return machine_pool


class LightestLoadFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    
    if machine_pool.Size() == 0:
      return ret

    for machine in machine_pool:
      machine.UpdateDynamicInfo()

    sorted_list = sorted(machine_pool, key=lambda m: m.load)
    ret.AddMachine(sorted_list[0])
    return ret


class OSFilter(MachinePoolFilter):
  def __init__(self, os_name):
    self.os_name = os_name

  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.os.lower() == self.os_name.lower():
        ret.AddMachine(machine)
    return ret


class UnlockedFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      ret.AddMachine(machine)
    return ret

class NameFilter(MachinePoolFilter):
  def __init__(self, name):
    self.name = name


  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.name.lower() == self.name.lower():
        ret.AddMachine(machine)
    return ret


class NameListFilter(MachinePoolFilter):
  def __init__(self, names):
    self.names = []
    for name in names:
      self.names.append(name)

  def FilterPool(self, machine_pool):
    taken_list = self.names[:]
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.name in self.names:
        taken_list.remove(machine.name)
        ret.AddMachine(machine)
    if ret.Size() != len(self.names):
      print "Could not find: "
      print taken_list
      raise Exception("Could not find machines")
    return ret
