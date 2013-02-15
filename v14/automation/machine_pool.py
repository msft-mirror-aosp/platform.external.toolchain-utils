#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine pool class definition.

Machine pools can select machines based on filters.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import machine


class MachinePool:
  def __init__(self, initial_list=[]):
    self.machine_list = initial_list
    self.name = ""


  def SetName(self, name):
    self.name = name


  def GetName(self, name):
    return self.name


  def AddMachine(self, machine):
    self.machine_list.append(machine)


  def RemoveMachine(self, machine):
    self.machine_list.remove(machine)


  def GetMachine(self, index):
    return self.machine_list[index]


  def Size(self):
    return len(self.machine_list)


  def __str__(self):
    ret = ""
    for m in self.machine_list:
      ret += str(m)
    return ret


  def __iter__(self):
    current = 0
    while current < self.Size():
      yield self.machine_list[current]
      current += 1



