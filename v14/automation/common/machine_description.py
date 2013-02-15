#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

from fnmatch import fnmatch

class MachineSpecification(object):
  """
  If you want to find a machine matching your requirements this is a class you
  want to use to specify them.
  """

  def __init__(self, name="*", os="*", lock_required=False):
    self.name = name
    self.os = os
    self.lock_required = lock_required
    self.preferred_machines = []


  def IsMatch(self, machine):
    if machine.locked:
      return False
    return fnmatch(machine.name, self.name) and fnmatch(machine.os, self.os)


  def AddPreferredMachine(self, name):
    if name not in self.preferred_machines:
      self.preferred_machines.append(name)
