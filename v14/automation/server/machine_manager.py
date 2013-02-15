#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager class definition.

Machine manager manages machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import csv
import machine
import threading
from utils import utils

DEFAULT_MACHINES_FILE = utils.GetRoot(__file__)[0] + "/test_pool.csv"


class MachineManager:
  def __init__(self, machines_file=DEFAULT_MACHINES_FILE):
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
    self.global_pool = machines

  def _GetMachine(self, machine_description):
    output_pool = []

    for m in self.global_pool:
      if machine_description.IsMatch(m):
        output_pool.append(m)

    if len(output_pool) == 0:
      return None

    result = output_pool[0]
    for machine in output_pool:
      if machine.name in machine_description.GetPreferredMachines():
        result = machine
        break
      elif machine.uses < result.uses:
        result = machine

    if machine_description.IsLockRequired() == True:
      result.locked = True
    result.uses += 1

    return result

  def GetMachines(self, required_machines):
    self.reenterant_lock.acquire(True)
    acquired_machines = []

    for machine_description in required_machines:

      machine = self._GetMachine(machine_description)

      if machine == None:
        # Roll back acquires
        self.ReturnMachines(acquired_machines)
        acquired_machines = None
        break

      acquired_machines.append(machine)

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

