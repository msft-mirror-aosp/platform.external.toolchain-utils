import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class p4Job(job.Job):
  def __init__(self, p4_port, p4_paths, revision, checkoutdir):
    job.Job.__init__(self)
    self.p4_paths = p4_paths
    self.p4_port = p4_port
    self.revision = revision
    self.checkoutdir = checkoutdir

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))

  def GetCommand(self):
    # TODO: Server must provide an API for getting a system-wide unique string.
    client_name = "$(uname -a | cut -d' ' -f2)"
    command = "cd " + self.checkoutdir
    command += " && cp ${HOME}/.p4config ."
    command += " && echo \"P4PORT=" + self.p4_port + "\" >> .p4config"
    command += " && echo \"P4CLIENT=" + client_name + "\" >> .p4config"
    command += " && g4 client -a " + " -a ".join(p4_paths)
    command += " && g4 sync ..."
    command += " && g4 client -d " + client_name
    return  command

