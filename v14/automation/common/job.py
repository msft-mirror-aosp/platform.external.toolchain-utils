#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"


import time
import machine_description


STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_EXECUTING = "STATUS_EXECUTING"
STATUS_COMPLETED = "STATUS_COMPLETED"
STATUS_FAILED = "STATUS_FAILED"

SUBDIR_WORK = "/work"
SUBDIR_LOGS = "/logs"


class RequiredFolder:
  def __init__(self, job, src, dest, read_only):
    self.job = job
    self.src = src
    self.dest = dest
    self.read_only = read_only


class Job:
  """A class representing a job whose commands will be executed."""

  def __init__(self, command):
    self.status = STATUS_NOT_EXECUTED
    self.children = []
    self.parents = []
    self.machine_descriptions = []
    self.required_folders = []
    self.id = 0
    self.job_dir = ""
    self.machine = None
    self.command = command
    self._primary_done = False
    self.start_time = 0
    self.finish_time = 0

  def __str__(self):
    ret = ""
    ret += str(self.id) + "\n"
    ret += self.command + "\n"
    ret += self.status + "\n"
    ret += ("start_time: %s\nfinish_time: %s\n" %
            (self.start_time, self.finish_time))
    return ret

  def SetID(self, id):
    self.id = id

  def GetID(self):
    return self.id

  def SetMachine(self, machine):
    self.machine = machine

  def GetMachine(self):
    return self.machine

  def SetStatus(self, status):
    if status == STATUS_EXECUTING:
      self.start_time = time.time()
    if (status == STATUS_COMPLETED or
        status == STATUS_FAILED):
      self.finish_time = time.time()
    self.status = status

  def GetStatus(self):
    return self.status

  def AddRequiredFolder(self, job, src, dest, read_only=False):
    if job not in self.children:
      self.children.append(job)
    if self not in job.parents:
      job.parents.append(self)
    self.required_folders.append(RequiredFolder(job, src, dest, read_only))

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

  def AddChild(self, job):
    self.children.append(job)
    job.parents.append(self)

  def GetChildren(self):
    return self.children

  def GetNumChildren(self):
    return len(self.children)

  def GetParents(self):
    return self.parents

  def GetNumParents(self):
    return len(self.parents)

  def IsReady(self):
    # Check that all our dependencies have been executed
    for child in self.children:
      if child.GetStatus() != STATUS_COMPLETED:
        return False

    return True

  def GetRequiredMachines(self):
    return self.machine_descriptions

  def GetCommand(self):
    return self.command

  def SetCommand(self, command):
    self.command = command

  def SetCommands(self, commands):
    self.command = " ; ".join(commands)

  def AddRequiredMachine(self, name, os, lock, primary=True):
    if self._primary_done == True:
      raise Exception("There can only be one primary machine description.")
    desc = machine_description.MachineDescription(name, os, lock)
    if primary == True:
      self.machine_descriptions.insert(0, desc)
      self._primary_done = True
    else:
      self.machine_descriptions.append(desc)

