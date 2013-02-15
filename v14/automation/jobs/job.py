#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"

STATUS_NOT_EXECUTED = 0
STATUS_EXECUTING = 1
STATUS_COMPLETED = 2


class Job:
  """A class representing a job whose commands will be executed."""

  def __init__(self):
    self.status = STATUS_NOT_EXECUTED
    self.dependencies = []
    self.dependents = []
    self.machine_descriptions = []

  def SetStatus(self, status):
    self.status = status

  def GetStatus(self):
    return self.status

  def AddDependency(self, dep):
    self.dependencies.append(dep)
    dep.dependents.append(self)

  def GetDependencies(self):
    return self.dependencies

  def GetNumDependencies(self):
    return len(self.dependencies)

  def GetDependents(self):
    return self.dependents

  def GetNumDependents(self):
    return len(self.dependents)

  def IsReady(self):
    # Check that all our dependencies have been executed
    for dependency in self.GetDependencies():
      if dependency.GetStatus() != STATUS_COMPLETED:
        return False

    return True

  def GetPrimaryMachineDescription(self):
    return self.machine_descriptions[0]

  def GetSecondaryMachineDescriptions(self):
    return self.machine_descriptions[1:]
