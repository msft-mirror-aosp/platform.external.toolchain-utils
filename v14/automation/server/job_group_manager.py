#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

import copy
import os
import threading

from automation.common import command_executer
from automation.common import logger
from automation.common import command as cmd
import automation.common.job_group
from automation.server import job_manager


class JobGroupPreparer(object):
  def __init__(self):
    username = os.getlogin()

    self._home_prefix = os.path.join("/home", username, "www", "automation")
    self._home_template = "job-group-%d"
    self._home_pattern = "job-group-(?P<id>\d+)"

    self._id_producer = job_manager.IdProducerPolicy()
    self._id_producer.Initialize(self._home_prefix, "job-(?P<id>\d+)")

  def Prepare(self, job_group):
    job_group.id = self._id_producer.GetNextId()
    job_group.home_dir = os.path.join(
        self._home_prefix, self._home_template % job_group.id)


class JobGroupManager(object):
  def __init__(self, _job_manager):
    self.all_job_groups = []

    self.job_manager = _job_manager
    self.job_manager.AddListener(self)

    self.job_condition = threading.Condition()

    self._configurator = JobGroupPreparer()

  def GetJobGroup(self, job_group_id):
    for job_group in self.all_job_groups:
      if job_group.id == job_group_id:
        return job_group

    return None

  def GetAllJobGroups(self):
    self.job_condition.acquire()
    res = copy.deepcopy(self.all_job_groups)
    self.job_condition.release()
    return res

  def AddJobGroup(self, job_group):
    self.job_condition.acquire()

    self._configurator.Prepare(job_group)

    # Re/Create home directory for logs, etc.
    command_executer.GetCommandExecuter().RunCommand(
        cmd.Chain(cmd.RmTree(job_group.home_dir),
                  cmd.MakeDir(job_group.home_dir)))

    self.all_job_groups.append(job_group)

    for job in job_group.jobs:
      self.job_manager.AddJob(job)

    logger.GetLogger().LogOutput("Added JobGroup '%s'." % job_group.id)

    job_group.Submit()

    self.job_condition.release()
    return job_group.id

  def KillJobGroup(self, job_group):
    self.job_condition.acquire()
    for job in job_group.jobs:
      self.job_manager.KillJob(job)

    # Lets block until the job_group is killed so we know it is completed
    # when we return.
    while job_group.status not in [automation.common.job_group.STATUS_SUCCEEDED,
                                   automation.common.job_group.STATUS_FAILED]:
      self.job_condition.wait()
    self.job_condition.release()

  def NotifyJobComplete(self, job):
    self.job_condition.acquire()
    job_group = job.group
    if job_group.status == automation.common.job_group.STATUS_FAILED:
      # We have already failed, don't need to do anything
      self.job_condition.notifyAll()
      self.job_condition.release()
      return
    if job.status == automation.common.job.STATUS_FAILED:
      # We have a failed job, abort the job group
      job_group.status = automation.common.job_group.STATUS_FAILED
      if job_group.cleanup_on_failure:
        for job in job_group.jobs:
          # TODO(bjanakiraman): We should probably only kill dependent jobs
          # instead of the whole job group.
          self.job_manager.KillJob(job)
          self.job_manager.CleanUpJob(job)
    else:
      # The job succeeded successfully -- lets check to see if we are done.
      assert job.status == automation.common.job.STATUS_SUCCEEDED
      finished = True
      for other_job in job_group.jobs:
        assert other_job.status != automation.common.job.STATUS_FAILED
        if other_job.status != automation.common.job.STATUS_SUCCEEDED:
          finished = False
          break

      if finished:
        job_group.status = automation.common.job_group.STATUS_SUCCEEDED
        if job_group.cleanup_on_completion:
          for job in job_group.jobs:
            self.job_manager.CleanUpJob(job)

    self.job_condition.notifyAll()
    self.job_condition.release()
