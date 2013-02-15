import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class LSJob(job.Job):
  def __init__(self, dir):
    job.Job.__init__(self)
    self.dir = dir

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))

  def GetCommand(self):
    return "ls " + self.dir

