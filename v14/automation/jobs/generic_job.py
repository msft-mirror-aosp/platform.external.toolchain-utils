import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class GenericJob(job.Job):
  def __init__(self, commands, dep_dirs):
    job.Job.__init__(self)
    self.commands = commands
    self.dep_dirs = dep_dirs

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))


  def GetCommand(self):
    return " && ".join(self.commands)

