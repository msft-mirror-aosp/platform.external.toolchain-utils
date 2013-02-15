import job

class EchoJob(job.Job):
  def __init__(self, path):
    job.Job.__init__(self)
    self.path = path

  def GetCommand(self):
    return "echo " + self.path

