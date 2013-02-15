#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"


import time
import machine_description


STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_SETUP = "STATUS_SETUP"
STATUS_COPYING = "STATUS_COPYING"
STATUS_RUNNING = "STATUS_RUNNING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"

LOGS_SUBDIR = "/logs"
RESULTS_SUBDIR = "/results"

class RequiredFolder:
  def __init__(self, job, src, dest, read_only):
    self.job = job
    self.src = src
    self.dest = dest
    self.read_only = read_only


class StatusEvent:
  def __init__(self, old_status, new_status):
    self.old_status = old_status
    self.new_status = new_status
    self.event_time = time.time()


class Job:
  """A class representing a job whose commands will be executed."""

  def __init__(self, command):
    self.status = STATUS_NOT_EXECUTED
    self.children = []
    self.parents = []
    self.machine_descriptions = []
    self.required_folders = []
    self.id = 0
    self.work_dir = ""
    self.home_dir = ""
    self.machines = []
    self.command = command
    self._primary_done = False
    self.status_events = []
    self.results_dirs_src = []
    self.results_dest_dir = ""
    self.results_dest_machine = None
    self.group = None

  def __str__(self):
    ret = ""
    ret += str(self.id) + "\n"
    ret += self.command + "\n"
    ret += self.status + "\n"
    ret += "Timeline of status events:\n"
    timeline = ""
    for i in range(len(self.status_events)):
      s = self.status_events[i]
      ret += ("%s -> %s: %s\n" % (s.old_status,
                               s.new_status,
                               time.ctime(s.event_time)))
      if i != 0:
        old_s = self.status_events[i - 1]
        time_diff = s.event_time - old_s.event_time
        time_string = time.strftime("%H hours %M minutes %S seconds",
                                 time.gmtime(time_diff))
        timeline += ("%s: %s\n" % (s.old_status,
                                     time_string))
    ret += timeline

    return ret

  def SetID(self, id):
    self.id = id

  def GetID(self):
    return self.id

  def SetMachines(self, machine):
    self.machines = machine

  def GetMachines(self):
    return self.machines

  def SetStatus(self, status):
    status_event = StatusEvent(self.status, status)
    self.status_events.append(status_event)
    self.status = status

  def GetStatus(self):
    return self.status

  def AddRequiredFolder(self, job, src, dest, read_only=False):
    self.AddChild(job)
    self.required_folders.append(RequiredFolder(job, src, dest, read_only))

  def GetRequiredFolders(self):
    return self.required_folders

  def SetWorkDir(self, work_dir):
    self.work_dir = work_dir

  def GetWorkDir(self):
    return self.work_dir

  def SetHomeDir(self, home_dir):
    self.home_dir = home_dir

  def GetHomeDir(self):
    return self.home_dir

  def GetResultsDir(self):
    return self.home_dir + RESULTS_SUBDIR

  def GetLogsDir(self):
    return self.home_dir + LOGS_SUBDIR

  def AddChild(self, job):
    if job not in self.children:
      self.children.append(job)
    if self not in job.parents:
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
      if child.GetStatus() != STATUS_SUCCEEDED:
        return False

    return True

  def GetRequiredMachines(self):
    return self.machine_descriptions

  def GetGroup(self):
    return self.group

  def SetGroup(self, group):
    self.group = group

  def GetCommand(self):
    return self.command

  def SetCommand(self, command):
    self.command = command

  def SetCommands(self, commands):
    self.command = " ; ".join(commands)

  def AddRequiredMachine(self, name, os, lock, primary=True):
    if primary == True and self._primary_done == True:
      raise Exception("There can only be one primary machine description.")
    desc = machine_description.MachineDescription(name, os, lock)
    if primary == True:
      self.machine_descriptions.insert(0, desc)
      self._primary_done = True
    else:
      self.machine_descriptions.append(desc)

  def AddResultsDir(self, directory):
    self.results_dirs_src.append(directory)

  def GetResultsDirs(self):
    return self.results_dirs_src

