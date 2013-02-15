#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager class definition.

Machine manager manages machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import csv
import threading
import os.path
from automation.common import machine

DEFAULT_MACHINES_FILE = os.path.join(os.path.dirname(__file__), "test_pool.csv")


class MachineManager(object):
  def __init__(self, machines_file=DEFAULT_MACHINES_FILE):
    self.ConstructMachineList(machines_file)
    self.reenterant_lock = threading.RLock()

  def __str__(self):
    return "%s" % self.global_pool

  def ConstructMachineList(self, machines_file):
    csv_file = csv.reader(open(machines_file, "rb"), delimiter=",",
                          quotechar="\"")
    # Skip header
    csv_file.next()
    # First populate the global pool.
    self.global_pool = [machine.Machine(name, label, cpu, int(cores), os, user)
                        for name, label, cpu, cores, os, user in csv_file]

  def _GetMachine(self, mach_spec):
    output_pool = [m for m in self.global_pool if mach_spec.IsMatch(m)]

    if not output_pool:
      return None

    result = output_pool[0]

    for mach in output_pool:
      if mach.hostname in mach_spec.preferred_machines:
        result = mach
        break
      elif mach.uses < result.uses:
        # get a machine with minimum uses
        result = mach

    if mach_spec.lock_required:
      result.locked = True
    result.uses += 1

    return result

  def GetMachines(self, required_machines):
    self.reenterant_lock.acquire(True)
    acquired_machines = []

    for mach_spec in required_machines:
      mach = self._GetMachine(mach_spec)

      if not mach:
        # Roll back acquires
        self.ReturnMachines(acquired_machines)
        acquired_machines = None
        break

      acquired_machines.append(mach)

    self.reenterant_lock.release()

    return acquired_machines

  def ReturnMachines(self, machines):
    # lock here (re-entrant)
    self.reenterant_lock.acquire(True)
    for mach in machines:
      mach.uses -= 1
      if mach.uses == 0:
        mach.locked = False
    self.reenterant_lock.release()
    # unlock
