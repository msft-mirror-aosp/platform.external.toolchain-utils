import job

class LSJob(job.Job):
  def __init__(self, text):
    job.Job.__init__(self)
    self.text = text

  def GetCommand(self):
    return "echo " + self.text

