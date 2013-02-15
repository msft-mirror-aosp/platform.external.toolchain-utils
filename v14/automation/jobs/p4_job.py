import job
from automation.machine_description import MachineDescription
from automation.machine_filters import *

class P4Job(job.Job):
  def __init__(self, p4_port, p4_paths, revision, checkoutdir):
    job.Job.__init__(self)
    self.p4_paths = p4_paths
    self.p4_port = p4_port
    self.revision = revision
    self.checkoutdir = checkoutdir

    self.machine_descriptions.append(MachineDescription([OSFilter("linux")]))


  def _GetP4ClientSpec(self, client_name, p4_paths):
    p4_string = ""
    for p4_path in p4_paths:
      p4_string += " -a \"" + (" //" + client_name + "/").join(p4_path) + "\""

    return p4_string


  def GetCommand(self):
    # TODO: Server must provide an API for getting a system-wide unique string.
    client_name = "p4-automation-" + str(self.GetID())
    command = ""
    command += " export P4CONFIG=.p4config"
    command += " && mkdir -p " + self.checkoutdir
    command += " && cd " + self.checkoutdir
    command += " && cp ${HOME}/.p4config ."
    command += " && chmod u+w .p4config"
    command += " && echo \"P4PORT=" + self.p4_port + "\" >> .p4config"
    command += " && echo \"P4CLIENT=" + client_name + "\" >> .p4config"
    command += (" && g4 client " +
                self._GetP4ClientSpec(client_name, self.p4_paths))
    command += " && g4 sync ..."
    command += " && g4 client -d " + client_name
    return command

