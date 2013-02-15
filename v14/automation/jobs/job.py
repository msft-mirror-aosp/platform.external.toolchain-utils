#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"

STATUS_NOT_EXECUTED = 0
STATUS_EXECUTING = 1
STATUS_COMPLETED = 2

SUBDIR_WORK = "/work"
SUBDIR_LOGS = "/logs"


class RequiredFolder:
  def __init__(self, job, folder):
    self.job = job
    self.folder = folder

class Job:
  """A class representing a job whose commands will be executed."""

  def __init__(self):
    self.status = STATUS_NOT_EXECUTED
    self.dependencies = []
    self.dependents = []
    self.machine_descriptions = []
    self.required_folders = []
    self.id = 0
    self.job_dir = ""
    self.machine = None

  def SetID(self, id):
    self.id = id

  def GetID(self):
    return self.id

  def SetMachine(self, machine):
    self.machine = machine

  def GetMachine(self):
    return self.machine

  def SetStatus(self, status):
    self.status = status

  def GetStatus(self):
    return self.status

  def AddRequiredFolder(self, job, folder):
    self.required_folders.append(RequiredFolder(job, folder))

  def GetRequiredFolders(self):
    return self.required_folders

  def SetJobDir(self, job_dir):
    self.job_dir = job_dir

  def GetJobDir(self):
    return self.job_dir

  def GetWorkDir(self):
    return self.job_dir + SUBDIR_WORK

  def GetLogsDir(self):
    return self.job_dir + SUBDIR_LOGS

  def AddDependency(self, job):
    self.dependencies.append(job)
    job.dependents.append(self)

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

  def GetMachineDescriptions(self):
    return self.machine_descriptions
