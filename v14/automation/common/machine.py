#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

__author__ = "asharif@google.com (Ahmad Sharif)"

from fnmatch import fnmatch


class Machine(object):
  """Stores information related to machine and its state."""

  def __init__(self, name, cpu, num_cores, os, username):
    self.name = name
    self.cpu = cpu
    self.num_cores = num_cores
    self.os = os
    self.username = username
    self.last_updated = 0
    self.load = 0
    self.uses = 0
    self.locked = False

  def __str__(self):
    return "\n".join(["Machine Information:",
                      "Name: %s" % self.name,
                      "CPU: %s" % self.cpu,
                      "NumCores: %d" % self.num_cores,
                      "OS: %s" % self.os,
                      "load: %d" % self.load,
                      "uses: %d" % self.uses])


class MachineSpecification(object):
  """Helper class used to find a machine matching your requirements."""

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
