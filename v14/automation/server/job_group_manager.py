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


  def AddJobGroup(self, job_group):
    self.job_condition.acquire()
    job_group.SetID(self.job_group_counter)
    job_group.SetStatus(automation.common.job_group.STATUS_EXECUTING)
    self.all_job_groups.append(job_group)
    for job in job_group.GetJobs():
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

    while not (job_group.GetStatus() ==
               automation.common.job_group.STATUS_COMPLETED or
               job_group.GetStatus() ==
               automation.common.job_group.STATUS_FAILED):
      self.job_condition.wait()
    self.job_condition.release()


  def NotifyJobComplete(self, job, status):
    self.job_condition.acquire()
    job_group = self.job_group_mapping[job]
    completed = True
    success = True
    for job in job_group.GetJobs():
      if (job.GetStatus() != automation.common.job.STATUS_COMPLETED and
          job.GetStatus() != automation.common.job.STATUS_FAILED):
        completed = False
      if (job.GetStatus() != automation.common.job.STATUS_COMPLETED):
        success = False

    if completed:
      if success:
        job_group.SetStatus(automation.common.job_group.STATUS_COMPLETED)
        if job_group.CleanupOnCompletion():
          for job in job_group.GetJobs():
            self.job_manager.CleanUpJob(job)
      else:
        job_group.SetStatus(automation.common.job_group.STATUS_FAILED)
        if job_group.CleanupOnFailure():
          for job in job_group.GetJobs():
            self.job_manager.CleanUpJob(job)

    self.job_condition.notifyAll()
    self.job_condition.release()
