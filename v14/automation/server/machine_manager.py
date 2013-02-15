#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager class definition.

Machine manager manages machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import csv
import machine
import machine_pool
import threading
from utils import utils

class MachineManager:
  def __init__(self, machines_file=utils.GetRoot(__file__)[0] + "/test_pool.csv"):
    self.ConstructMachineList(machines_file)
    self.reenterant_lock = threading.RLock()


  def __str__(self):
    return str(self.global_pool)


  def ConstructMachineList(self, machines_file):
    csv_file = csv.reader(open(machines_file, 'rb'),
                          delimiter=",", quotechar="\"")
    machines = []
    # Header
    csv_file.next()
    for line in csv_file:
      machines.append(machine.Machine(line[0], line[1],
                                      int(line[2]), line[3], line[4]))

    # First populate the global pool.
    self.global_pool = machine_pool.MachinePool(machines)

  def _GetMachine(self, machine_description):
    output_pool = machine_pool.MachinePool()

    for m in self.global_pool:
      if machine_description.IsMatch(m):
        output_pool.AddMachine(m)

    if output_pool.Size() == 0:
      return None

    result = output_pool.GetMachine(0)
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

