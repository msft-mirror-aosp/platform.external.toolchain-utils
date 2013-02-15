#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"


import os.path
import time
import machine_description
from utils import utils

STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_SETUP = "STATUS_SETUP"
STATUS_COPYING = "STATUS_COPYING"
STATUS_RUNNING = "STATUS_RUNNING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"

LOGS_SUBDIR = "logs"
TEST_RESULTS_DIR = "results"
TEST_RESULTS_FILE = "results.csv"
TEST_REPORT_FILE = "report.html"
TEST_REPORT_SUMMARY_FILE = "summary.txt"

class RequiredFolder(object):
  def __init__(self, job, src, dest, read_only):
    self.job = job
    self.src = src
    self.dest = dest
    self.read_only = read_only


class StatusEvent(object):
  def __init__(self, old_status, new_status):
    self.old_status = old_status
    self.new_status = new_status
    self.event_time = time.time()

  def __str__(self):
    return "%s -> %s: %s" % (self.old_status, self.new_status,
                             time.ctime(self.event_time))

class Job(object):
  """A class representing a job whose commands will be executed."""

  def __init__(self, label, command, baseline=""):
    self._status = STATUS_NOT_EXECUTED
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
    self.group = None
    self.dry_run = None
    self.label = label
    self.baseline = baseline

  def __str__(self):
    res = []
    res.append("%s" % self.id)
    res.append("Children:")
    res.extend(["%s" % child.id for child in self.children])
    res.append("Parents:")
    res.extend(["%s" % parent.id for parent in self.parents])
    res.append("Machines:")
    res.extend(["%s" % machine for machine in self.machines])
    res.append(utils.FormatCommands(self.command))
    res.append(self.status)
    res.append(self.GetTimeline())
    return "\n".join(res)

  def GetTotalTime(self):
    if not self.status_events:
      return ""
    time_diff = time.time() - self.status_events[0].event_time
    time_string = time.strftime("%H:%M:%S", time.gmtime(time_diff))
    return "Total time: %s" % time_string

  def GetTimeline(self):
    total_time = 0
    timeline = []
    timeline.append("Timeline of status events:")

    def time_to_string(t):
      return time.strftime("%H hours %M minutes %S seconds", time.gmtime(t))

    for i in range(len(self.status_events)):
      s = self.status_events[i]
      timeline.append("%s" % s)
      if i != 0:
        old_s = self.status_events[i - 1]
        time_diff = s.event_time - old_s.event_time
        total_time += time_diff
        timeline.append("%s: %s" % (s.old_status, time_to_string(time_diff)))

    if self.status_events and self.status not in [STATUS_SUCCEEDED,
                                                  STATUS_FAILED]:
      time_diff = time.time() - self.status_events[-1].event_time
      total_time += time_diff
      timeline.append("%s - NOW: %s" % (self.status, time_to_string(time_diff)))

    timeline.append("Total time: %s" % time_to_string(total_time))

    return "\n".join(timeline)

  @property
  def status(self):
    return self._status

  @status.setter
  def status(self, status):
    assert status in [STATUS_NOT_EXECUTED, STATUS_SETUP, STATUS_COPYING,
                      STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED]
    status_event = StatusEvent(self.status, status)
    self.status_events.append(status_event)
    self._status = status

  def AddRequiredFolder(self, job, src, dest, read_only=False):
    self.AddChild(job)
    self.required_folders.append(RequiredFolder(job, src, dest, read_only))

  def GetRequiredFolders(self):
    return self.required_folders

  def GetTestResultsDirSrc(self):
    # TODO(kbaclawski): Is it acceptable not to have work_dir?
    if not self.work_dir:
      return ""
    return os.path.join(self.work_dir, TEST_RESULTS_DIR)

  @property
  def test_results_dir(self):
    # TODO(kbaclawski): Is it acceptable not to have home_dir?
    if not self.home_dir:
      return ""
    return os.path.join(self.home_dir, TEST_RESULTS_DIR)

  @property
  def test_report_filename(self):
    return os.path.join(self.test_results_dir, TEST_REPORT_FILE)

  @property
  def test_report_summary_filename(self):
    return os.path.join(self.test_results_dir, TEST_REPORT_SUMMARY_FILE)

  @property
  def test_results_filename(self):
    return os.path.join(self.test_results_dir, TEST_RESULTS_FILE)

  @property
  def logs_dir(self):
    if not self.home_dir:
      return ""
    return os.path.join(self.home_dir, LOGS_SUBDIR)

  @property
  def log_out_filename(self):
    return os.path.join(self.logs_dir, "job-%s.log.out" % self.id)

  @property
  def log_cmd_filename(self):
    return os.path.join(self.logs_dir, "job-%s.log.cmd" % self.id)

  @property
  def log_err_filename(self):
    return os.path.join(self.logs_dir, "job-%s.log.err" % self.id)

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
      if child.status != STATUS_SUCCEEDED:
        return False

    return True

  def GetRequiredMachines(self):
    return self.machine_descriptions

  def AddRequiredMachine(self, name, os, lock, primary=True):
    if primary == True and self._primary_done == True:
      raise RuntimeError("There can only be one primary machine description.")
    desc = machine_description.MachineDescription(name, os, lock)
    if primary:
      self.machine_descriptions.insert(0, desc)
      self._primary_done = True
    else:
      self.machine_descriptions.append(desc)

  @property
  def baseline_filename(self):
    if not self.baseline:
      return ""
    return os.path.join(self.baseline, TEST_RESULTS_FILE)
