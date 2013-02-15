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
import pools
import threading


class MachineManager:
  __shared_state = {}
  global_pool = None
  reenterant_lock = None
  def __init__(self):
    self.__dict__ = self.__shared_state
    if self.global_pool == None:
      self.ConstructGlobalPool()
    if self.reenterant_lock == None:
      self.reenterant_lock = threading.RLock()


  def __str__(self):
    return str(self.global_pool)


  def ConstructGlobalPool(self):
    reload(pools)

    # First populate the global pool.
    self.global_pool = machine_pool.MachinePool(pools.machines)

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
    if self.reenterant_lock.acquire(False) == False:
      return []
    acquired_machines = []
    for machine_description in machine_descriptions:
      machine = self._GetMachine(machine_description)
      if machine == None:
        # Roll back acquires
        self.ReturnMachines(acquired_machines)
        self.reenterant_lock.release()
        return None
      acquired_machines.append(machine)

    # unlock here
    self.reenterant_lock.release()
    return acquired_machines


  def ReturnMachines(self, machines):
    # lock here (re-entrant)
    self.reenterant_lock.acquire(True)
    for machine in machines:
      machine.uses -= 1
      if machine.uses == 0:
        machine.locked = False
    self.reenterant_lock.release()
    # unlock

