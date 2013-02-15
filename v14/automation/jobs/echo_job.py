import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class EchoJob(job.Job):
  def __init__(self, msg):
    job.Job.__init__(self)
    self.msg = msg

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))

  def GetCommand(self):
    return "echo " + self.msg

