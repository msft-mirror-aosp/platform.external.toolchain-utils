import threading
import automation.common.job_group
from utils import command_executer
from utils import logger
import getpass
import time
import copy
import report_generator
import summarize_results

HOMEDIR_PREFIX = "/home/" + getpass.getuser() + "/www/automation"

class JobGroupManager:

  def __init__(self, job_manager):
    self.all_job_groups = []

    self.job_manager = job_manager
    self.job_manager.AddListener(self)


    self.job_group_counter = 0
    self.job_condition = threading.Condition()

  def GetAllJobGroups(self):
    self.job_condition.acquire()
    res = copy.deepcopy(self.all_job_groups)
    self.job_condition.release()
    return res

  def AddJobGroup(self, job_group):
    self.job_condition.acquire()
    job_group.SetID(self.job_group_counter)
    job_group.SetHomeDir(HOMEDIR_PREFIX + "/job-group-" +
                         str(self.job_group_counter))
    # Create home directory for logs, etc.
    command_executer.GetCommandExecuter().RunCommand("mkdir -p " +
                                                     job_group.GetHomeDir())
    # Copy baseline csv
    if job_group.GetBaselineFileSrc() is not None:
      (command_executer.GetCommandExecuter().
       CopyFiles(job_group.GetBaselineFileSrc(),
                 job_group.GetBaselineFileDest(), recursive=False))

    job_group.SetTimeSubmitted(time.time())
    job_group.SetStatus(automation.common.job_group.STATUS_EXECUTING)
    self.all_job_groups.append(job_group)
    for job in job_group.GetJobs():
      self.job_manager.AddJob(job)
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
    job_group = job.GetGroup()
    if job_group.GetStatus() == automation.common.job_group.STATUS_FAILED:
      # We have already failed, don't need to do anything
      self.job_condition.notifyAll()
      self.job_condition.release()
      return
    if job.GetStatus() == automation.common.job.STATUS_FAILED:
      # We have a failed job, abort the job group
      job_group.SetStatus(automation.common.job_group.STATUS_FAILED)
      if job_group.CleanupOnFailure():
        for job in job_group.GetJobs():
          self.job_manager.KillJob(job)
          self.job_manager.CleanUpJob(job)
      self.FinishedJobGroup(job_group)
    else:
      # The job succeeded successfully -- lets check to see if we are done.
      assert job.GetStatus() == automation.common.job.STATUS_SUCCEEDED
      finished = True
      for other_job in job_group.GetJobs():
        assert other_job.GetStatus() != automation.common.job.STATUS_FAILED
        if other_job.GetStatus() != automation.common.job.STATUS_SUCCEEDED:
          finished = False
          break

      if finished:
        job_group.SetStatus(automation.common.job_group.STATUS_SUCCEEDED)
        if job_group.CleanupOnCompletion():
          for job in job_group.GetJobs():
            self.job_manager.CleanUpJob(job)
        self.FinishedJobGroup(job_group)

    self.job_condition.notifyAll()
    self.job_condition.release()

  def FinishedJobGroup(self, job_group):
    # Read all results files and compress into a single csv that can be used
    # as the next baseline.
    summary_file = open(job_group.GetResultsFileDest(), 'w')
    for job in job_group.GetJobs():
      for lowlevel_log in job.GetLowLevelLogsSrc():
        filename = lowlevel_log.split("/")[-1]
        path = job.GetLowLevelLogsDest() + "/" + filename
        try:
          summary_file.write(summarize_results.SummarizeFile(path).strip() +
                             "\n")
        except IOError, e:
          logger.GetLogger().LogWarning(e)
    summary_file.close()
    try:
      report_file = open(job_group.GetReportDest(), 'w')
      report = report_generator.GenerateResultsReport(job_group.GetBaselineFileDest(),
                                                      [job_group.GetResultsFileDest()])
      report_file.write(report)
      report_file.close
    except IOError, e:
      logger.GetLogger().LogWarning(e)



