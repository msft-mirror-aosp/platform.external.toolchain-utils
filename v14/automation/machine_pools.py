#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine pool class definition.

Machine pools can select machines based on filters.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import machine
import sys


class MachinePool:
  def __init__(self):
    self.machine_list = []
    self.name = ""


  def SetName(self, name):
    self.name = name


  def GetName(self, name):
    return self.name


  def AddMachine(self, machine):
    self.machine_list.append(machine)


  def RemoveMachine(self, machine):
    return 0


  def Size(self):
    return len(self.machine_list)


  def GetLightestLoad(self):
    for machine in self.machine_list:
      machine.UpdateDynamicInfo()

    sorted_list = sorted(self.machine_list, key=lambda m: m.load)
    return sorted_list[0]
  

  def __str__(self):
    ret = ""
    for m in self.machine_list:
      ret += str(m)
    return ret


class MachinePoolFilter:
  def FilterPool(self, machine_pool):
    return machine_pool


class ChromeOSFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.os == "chromeos":
        ret.AddMachine(machine)
    return ret


class LinuxFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.os == "linux":
        ret.AddMachine(machine)
    return ret

class UnlockedFilter(MachinePoolFilter):
  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.locked == False:
        ret.AddMachine(machine)
    return ret

class NameFilter(MachinePoolFilter):
  def __init__(self, name):
    self.name = name


  def FilterPool(self, machine_pool):
    ret = MachinePool()
    for machine in machine_pool.machine_list:
      if machine.name == self.name:
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
        index = taken_list.index(machine.name)
        taken_list.remove(machine.name)
        ret.AddMachine(machine)
    if ret.Size() != len(self.names):
      print "Could not find: "
      print taken_list
      raise Exception("Could not find machines")
    return ret

