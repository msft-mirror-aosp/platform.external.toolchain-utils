import job
from automation import MachineDescription
from automation import MachineFilters

class EchoJob(job.Job):
  def __init__(self, msg):
    job.Job.__init__(self)
    self.msg = msg

    self.machine_descriptions.append(MachineDescription([]))

  def GetCommand(self):
    return "echo " + self.msg

