import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class GenericJob(job.Job):
  def __init__(self, commands):
    job.Job.__init__(self)
    self.commands = commands

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))


  def GetCommand(self):
    return " && ".join(self.commands)

