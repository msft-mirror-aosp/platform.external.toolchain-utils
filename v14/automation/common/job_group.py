#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

import time

STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_EXECUTING = "STATUS_EXECUTING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"


class JobGroup(object):
  def __init__(self, label, jobs=[], cleanup_on_completion=True,
               cleanup_on_failure=False, description=""):
    self.id = 0
    self.label = label
    self.jobs = []
    self.cleanup_on_completion = cleanup_on_completion
    self.cleanup_on_failure = cleanup_on_failure
    self.description = description
    self._status = STATUS_NOT_EXECUTED
    self.time_submitted = 0
    self.home_dir = None

    for job in jobs:
      self.AddJob(job)

  def __str__(self):
    return "\n".join(["Job-Group:",
                      "ID: %s" % self.id] +
                     [str(job) for job in self.jobs])

  def AddJob(self, job):
    self.jobs.append(job)
    job.group = self

  def Submit(self):
    self.time_submitted = time.time()
    self.status = STATUS_EXECUTING

  @property
  def status(self):
    return self._status

  @status.setter
  def status(self, status):
    assert status in [STATUS_NOT_EXECUTED, STATUS_EXECUTING, STATUS_SUCCEEDED,
                      STATUS_FAILED]
    self._status = status
