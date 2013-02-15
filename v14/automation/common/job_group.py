
STATUS_NOT_EXECUTED = "STATUS_NOT_EXECUTED"
STATUS_EXECUTING = "STATUS_EXECUTING"
STATUS_SUCCEEDED = "STATUS_SUCCEEDED"
STATUS_FAILED = "STATUS_FAILED"

class JobGroup:
  def __init__(self, label, jobs=[],
               cleanup_on_complete=True, cleanup_on_fail=False, description=""):
    self.id = 0
    self.jobs = jobs
    self.cleanup_on_complete = cleanup_on_complete
    self.cleanup_on_fail = cleanup_on_fail
    self.status = STATUS_NOT_EXECUTED
    for j in self.jobs:
      j.SetGroup(self)
    self.description = description
    self.time_submitted = 0
    self.homedir = None
    self.label = label

  def __str__(self):
    ret = ""
    ret += "Job-Group:\n"
    ret += "ID: " + str(self.id) + "\n"
    for j in self.jobs:
      ret += str(j)
    return ret

  def SetID(self, id):
    self.id = id

  def GetID(self):
    return self.id

  def GetJobs(self):
    return self.jobs

  def CleanupOnCompletion(self):
    return self.cleanup_on_complete

  def CleanupOnFailure(self):
    return self.cleanup_on_fail

  def SetStatus(self, status):
    self.status = status

  def GetStatus(self):
    return self.status

  def GetDescription(self):
    return self.description

  def SetTimeSubmitted(self, time_submitted):
    self.time_submitted = time_submitted

  def GetTimeSubmitted(self):
    return self.time_submitted

  def SetHomeDir(self, homedir):
    self.homedir = homedir

  def GetHomeDir(self):
    return self.homedir
  
  def GetLabel(self):
    return self.label
