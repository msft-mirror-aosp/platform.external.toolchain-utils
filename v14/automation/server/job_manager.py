#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

import os
import re
import threading

from automation.common import logger
import automation.common.job
from automation.server import job_executer


class IdProducerPolicy(object):
  def __init__(self):
    self._counter = 1

  def Initialize(self, home_prefix, home_pattern):
    harvested_ids = []

    for filename in os.listdir(home_prefix):
      path = os.path.join(home_prefix, filename)

      if os.path.isdir(path):
        match = re.match(home_pattern, filename)

        if match:
          harvested_ids.append(int(match.group('id')))

    self._counter = max(harvested_ids or [0]) + 1

  def GetNextId(self):
    new_id = self._counter
    self._counter += 1
    return new_id


class JobPreparer(object):
  def __init__(self):
    self._home_prefix = '/usr/local/google/tmp/automation'
    self._home_template = 'job-%d'

    self._log_filename_template = 'job-%d.log'

    self._id_producer = IdProducerPolicy()
    self._id_producer.Initialize(self._home_prefix, 'job-(?P<id>\d+)')

  def Prepare(self, job):
    # Set job id
    job.id = self._id_producer.GetNextId()

    home_dir = self._home_template % job.id

    # Set job directories
    job.work_dir = os.path.join(self._home_prefix, home_dir)
    job.home_dir = os.path.join(job.group.home_dir, home_dir)


class JobManager(threading.Thread):
  def __init__(self, machine_manager):
    threading.Thread.__init__(self)
    self.all_jobs = []
    self.ready_jobs = []
    self.job_executer_mapping = {}

    self.machine_manager = machine_manager

    self.job_condition = threading.Condition()

    self.listeners = []
    self.listeners.append(self)

    self._configurator = JobPreparer()

  def StartJobManager(self):
    self.job_condition.acquire()
    self.start()
    self.job_condition.notifyAll()
    self.job_condition.release()

  def StopJobManager(self):
    self.job_condition.acquire()
    for job in self.all_jobs:
      self._KillJob(job.id)

    # Signal to die
    self.ready_jobs.insert(0, None)
    self.job_condition.notifyAll()
    self.job_condition.release()

    # Wait for all job threads to finish
    for executer in self.job_executer_mapping.values():
      executer.join()

  # Does not block until the job is completed.
  def KillJob(self, job_id):
    self.job_condition.acquire()
    self._KillJob(job_id)
    self.job_condition.release()

  def GetJob(self, job_id):
    for job in self.all_jobs:
      if job.id == job_id:
        return job
    return None

  def _KillJob(self, job_id):
    logger.GetLogger().LogOutput("Killing job with ID '%s'." % job_id)
    if job_id in self.job_executer_mapping:
      self.job_executer_mapping[job_id].Kill()
    killed_job = None
    for job in self.ready_jobs:
      if job.id == job_id:
        killed_job = job
        self.ready_jobs.remove(killed_job)
        break

  def AddJob(self, current_job):
    self.job_condition.acquire()

    self._configurator.Prepare(current_job)

    self.all_jobs.append(current_job)
    # Only queue a job as ready if it has no dependencies
    if current_job.is_ready:
      self.ready_jobs.append(current_job)

    self.job_condition.notifyAll()
    self.job_condition.release()

    return current_job.id

  def CleanUpJob(self, job):
    self.job_condition.acquire()
    if job.id in self.job_executer_mapping:
      self.job_executer_mapping[job.id].CleanUpWorkDir()
      del self.job_executer_mapping[job.id]
    # TODO(raymes): remove job from self.all_jobs
    self.job_condition.release()

  def NotifyJobComplete(self, job):
    self.machine_manager.ReturnMachines(job.machines)
    self.job_condition.acquire()
    logger.GetLogger().LogOutput('Job profile:\n%s' % job)
    if job.status == automation.common.job.STATUS_SUCCEEDED:
      for parent in job.parents:
        if parent.is_ready:
          if parent not in self.ready_jobs:
            self.ready_jobs.append(parent)

    self.job_condition.notifyAll()
    self.job_condition.release()

  def AddListener(self, listener):
    self.listeners.append(listener)

  def run(self):
    while True:
      # Get the next ready job, block if there are none
      self.job_condition.acquire()
      self.job_condition.wait()

      while self.ready_jobs:
        ready_job = self.ready_jobs.pop()
        if ready_job is None:
          # Time to die
          self.job_condition.release()
          return

        required_machines = ready_job.machine_dependencies
        for child in ready_job.children:
          required_machines[0].AddPreferredMachine(child.machines[0].hostname)

        machines = self.machine_manager.GetMachines(required_machines)
        if not machines:
          # If we can't get the necessary machines right now, simply wait
          # for some jobs to complete
          self.ready_jobs.insert(0, ready_job)
          break
        else:
          # Mark as executing
          executer = job_executer.JobExecuter(ready_job, machines,
                                              self.listeners)
          executer.start()
          self.job_executer_mapping[ready_job.id] = executer

      self.job_condition.release()
