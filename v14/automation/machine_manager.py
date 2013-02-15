#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager class definition.

Machine manager manages machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import machine
import machine_filters
import machine_pool
import os
import pools
import sys
from utils import utils


class MachineManager:
  __shared_state = {}
  global_pool = None
  def __init__(self):
    self.__dict__ = self.__shared_state
    if self.global_pool == None:
      self.ConstructGlobalPool()


  def __str__(self):
    return str(self.global_pool)


  def ConstructGlobalPool(self):
    reload(pools)

    # First populate the global pool.
    self.global_pool = machine_pool.MachinePool()
    for key, value in pools.machines.iteritems():
      m = machine.Machine(key,
                          value[0],
                          value[1],
                          value[2])
      self.global_pool.AddMachine(m)

    # Then populate the named pools.
    self.named_pools = []
    for key, value in pools.named_pools.iteritems():
      name_list_filter = machine_filters.NameListFilter(value)
      named_pool = name_list_filter.FilterPool(self.global_pool)
      named_pool.SetName(key)
      self.named_pools.append(named_pool)


  def _GetMachine(self, machine_description):
    filters = machine_description.GetFilters()
    machine_pool = self.global_pool

    filters.append(machine_filters.UnlockedFilter())

    filters.append(machine_filters.LightestLoadFilter())

    for f in filters:
      machine_pool = f.FilterPool(machine_pool)

    if machine_pool.Size() == 0:
      return None

    result = machine_pool.GetMachine(0)
    if machine_description.IsLockRequired() == True:
      result.locked = True
    result.uses += 1

    return result

  def GetMachines(self, machine_descriptions):
    # lock here (re-entrant)
    acquired_machines = []
    for machine_description in machine_descriptions:
      machine = self._GetMachine(machine_description)
      if machine == None:
        # Roll back acquires
        self.ReturnMachines(acquired_machines)
        return None
      acquired_machines.append(machine)

    # unlock here
    return acquired_machines


  def ReturnMachines(self, machines):
    # lock here (re-entrant)
    for machine in machines:
      machine.uses -= 1
      if machine.uses == 0:
        machine.locked = False
    # unlock

