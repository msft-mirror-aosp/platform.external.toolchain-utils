import job

class LSJob(job.Job):
  def __init__(self, dir):
    job.Job.__init__(self)
    self.dir = dir

  def GetCommand(self):
    return "ls " + self.dir

