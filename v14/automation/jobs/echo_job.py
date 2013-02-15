import job

class EchoJob(job.Job):
  def __init__(self, msg):
    job.Job.__init__(self)
    self.msg = msg

  def GetCommand(self):
    return "echo " + self.msg

