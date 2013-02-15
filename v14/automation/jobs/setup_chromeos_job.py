import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class SetupChromeOSJob(job.Job):
  def __init__(self, p4job, chromeos_version):
    job.Job.__init__(self)
    self.p4job = p4job
    self.chromeos_version = chromeos_version

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))
    self.AddDependency(p4job)
    self.AddRequiredFolder(p4job, "perforce2/gcctools/chromeos/v14", "v14")

  def GetCommand(self):
    return ("v14/setup_chromeos.py --dir=chromeos --version=%s"
            % (self.chromeos_version))

