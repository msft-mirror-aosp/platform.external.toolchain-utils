#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_EXECUTING = "STATUS_EXECUTING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"

class JobGroup(object):

  def __init__(self, label, jobs=[], cleanup_on_completion=True,
               cleanup_on_failure=False, description=""):
    self.id = 0
    self.label = label
    self.jobs = jobs
    for job in self.jobs:
      job.group = self
    self.cleanup_on_completion = cleanup_on_completion
    self.cleanup_on_failure = cleanup_on_failure
    self.description = description
    self._status = STATUS_NOT_EXECUTED
    self.time_submitted = 0
    self.home_dir = None


  def __str__(self):
    res = []
    res.append("Job-Group:")
    res.append("ID: %s" % self.id)
    res.extend(["%s" % job for job in self.jobs])
    return "\n".join(res)


  @property
  def status(self):
    return self._status


  @status.setter
  def status(self, status):
    assert status in [STATUS_NOT_EXECUTED, STATUS_EXECUTING, STATUS_SUCCEEDED,
                      STATUS_FAILED]
    self._status = status
