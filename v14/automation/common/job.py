#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""A module for a job in the infrastructure."""


__author__ = "raymes@google.com (Raymes Khoury)"


import os.path
import time
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


class FolderDependency(object):
  def __init__(self, job, src, dest=None):
    if not dest:
      dest = src

    # TODO(kbaclawski): rename to producer
    self.job = job
    self.src = src
    self.dest = dest
    self.read_only = dest != src


class StatusEvent(object):
  def __init__(self, old_status, new_status):
    self.old_status = old_status
    self.new_status = new_status
    self.event_time = time.time()

  def __str__(self):
    return "%s -> %s: %s" % (self.old_status, self.new_status,
                             time.ctime(self.event_time))


class JobFailure(Exception):
  def __init__(self, message, exit_code):
    Exception.__init__(self, message)
    self.exit_code = exit_code


class Job(object):
  """A class representing a job whose commands will be executed."""

  def __init__(self, label, command, baseline=""):
    self._status = STATUS_NOT_EXECUTED
    self.children = []
    self.parents = []
    self.machine_dependencies = []
    self.folder_dependencies = []
    self.id = 0
    self.work_dir = ""
    self.home_dir = ""
    self.machines = []
    self.command = command
    self._has_primary_machine_spec = False
    self.status_events = []
    self.group = None
    self.dry_run = None
    self.label = label
    self.baseline = baseline

  def __str__(self):
    res = []
    res.append("%d" % self.id)
    res.append("Children:")
    res.extend(["%d" % child.id for child in self.children])
    res.append("Parents:")
    res.extend(["%d" % parent.id for parent in self.parents])
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

    def TimeToString(t):
      return time.strftime("%H hours %M minutes %S seconds", time.gmtime(t))

    for i in range(len(self.status_events)):
      s = self.status_events[i]
      timeline.append("%s" % s)
      if i != 0:
        old_s = self.status_events[i - 1]
        time_diff = s.event_time - old_s.event_time
        total_time += time_diff
        timeline.append("%s: %s" % (s.old_status, TimeToString(time_diff)))

    if self.status_events and self.status not in [STATUS_SUCCEEDED,
                                                  STATUS_FAILED]:
      time_diff = time.time() - self.status_events[-1].event_time
      total_time += time_diff
      timeline.append("%s - NOW: %s" % (self.status, TimeToString(time_diff)))

    timeline.append("Total time: %s" % TimeToString(total_time))

    return "\n".join(timeline)

  @property
  def status(self):
    return self._status

  @status.setter
  def status(self, status):
    assert status in [STATUS_NOT_EXECUTED, STATUS_SETUP, STATUS_COPYING,
                      STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED]
    self.status_events.append(StatusEvent(self.status, status))
    self._status = status

  def DependsOnFolder(self, dependency):
    self.folder_dependencies.append(dependency)
    self.DependsOn(dependency.job)

  @property
  def test_results_dir_src(self):
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

  def DependsOn(self, job):
    """Specifies Jobs to be finished before this job can be launched."""
    if job not in self.children:
      self.children.append(job)
    if self not in job.parents:
      job.parents.append(self)

  @property
  def is_ready(self):
    """Check that all our dependencies have been executed."""
    return all(child.status == STATUS_SUCCEEDED for child in self.children)

  def DependsOnMachine(self, machine_spec, primary=True):
    """ Job will run on arbitrarily chosen machine specified by
    MachineSpecification class instances passed to this method. """
    if primary:
      if self._has_primary_machine_spec:
        raise RuntimeError("Only one primary machine specification allowed.")
      self._has_primary_machine_spec = True
      self.machine_dependencies.insert(0, machine_spec)
    else:
      self.machine_dependencies.append(machine_spec)

  @property
  def baseline_filename(self):
    if not self.baseline:
      return ""
    return os.path.join(self.baseline, TEST_RESULTS_FILE)
