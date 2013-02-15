import threading
import automation.common.job_group
from utils import logger

class JobGroupManager:

  def __init__(self, job_manager):
    self.all_job_groups = []

    self.job_manager = job_manager
    self.job_manager.AddListener(self)

    self.job_group_mapping = {}

    self.job_group_counter = 0
    self.job_condition = threading.Condition()

  def GetAllJobGroups(self):
    self.job_condition.acquire()
    return self.all_job_groups
    self.job_condition.release()

  def AddJobGroup(self, job_group):
    self.job_condition.acquire()
    job_group.SetID(self.job_group_counter)
    job_group.SetStatus(automation.common.job_group.STATUS_EXECUTING)
    self.all_job_groups.append(job_group)
    for job in job_group.GetJobs():
      job.SetResultsDestDir(job_group.GetResultsDir())
      job.SetResultsDestMachine(job_group.GetResultsMachine())
      self.job_manager.AddJob(job)
      self.job_group_mapping[job] = job_group
    self.job_group_counter += 1

    logger.GetLogger().LogOutput("Added JobGroup '%s'."
                                 % str(job_group.GetID()))

    self.job_condition.release()
    return job_group.GetID()

  def KillJobGroup(self, job_group):
    self.job_condition.acquire()
    for job in job_group.GetJobs():
      self.job_manager.KillJob(job)

    # Lets block until the job_group is killed so we know it is completed 
    # when we return.
    while not (job_group.GetStatus() ==
               automation.common.job_group.STATUS_SUCCEEDED or
               job_group.GetStatus() ==
               automation.common.job_group.STATUS_FAILED):
      self.job_condition.wait()
    self.job_condition.release()

  def NotifyJobComplete(self, job):
    self.job_condition.acquire()
    job_group = self.job_group_mapping[job]
    if job_group.GetStatus() == automation.common.job_group.STATUS_FAILED:
      # We have already failed, don't need to do anything
      return
    if job.GetStatus() == automation.common.job.STATUS_FAILED:
      # We have a failed job, abort the job group
      job_group.SetStatus(automation.common.job_group.STATUS_FAILED)
      if job_group.CleanupOnFailure():
        for job in job_group.GetJobs():
          self.job_manager.KillJob(job)
          self.job_manager.CleanUpJob(job)
    else:
      # The job succeeded successfully -- lets check to see if we are done.
      assert job.GetStatus() == automation.common.job.STATUS_SUCCEEDED
      succeeded = True
      for other_job in job_group.GetJobs():
        assert other_job.GetStatus() != automation.common.job.STATUS_FAILED
        if other_job.GetStatus() != automation.common.job.STATUS_SUCCEEDED:
          succeeded = False
          break

      if succeeded:
        job_group.SetStatus(automation.common.job_group.STATUS_SUCCEEDED)
        if job_group.CleanupOnCompletion():
          for job in job_group.GetJobs():
            self.job_manager.CleanUpJob(job)

    self.job_condition.notifyAll()
    self.job_condition.release()
