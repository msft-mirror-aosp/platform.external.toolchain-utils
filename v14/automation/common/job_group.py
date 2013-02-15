import getpass

STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_EXECUTING = "STATUS_EXECUTING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"

class JobGroup:
  def __init__(self, results_machine=None, results_dir=None, jobs=[],
               cleanup_on_complete=True, cleanup_on_fail=False):
    self.id = 0
    self.jobs = jobs
    self.results_machine = results_machine
    self.results_dir = results_dir
    self.cleanup_on_complete = cleanup_on_complete
    self.cleanup_on_fail = cleanup_on_fail
    self.status = STATUS_NOT_EXECUTED
    for j in self.jobs:
      j.SetGroup(self)

  def SetID(self, id):
    self.id = id

  def GetID(self):
    return self.id

  def GetJobs(self):
    return self.jobs

  def GetResultsMachine(self):
    return self.results_machine

  def GetResultsDir(self):
    return self.results_dir

  def CleanupOnCompletion(self):
    return self.cleanup_on_complete

  def CleanupOnFailure(self):
    return self.cleanup_on_fail

  def SetStatus(self, status):
    self.status = status

  def GetStatus(self):
    return self.status
