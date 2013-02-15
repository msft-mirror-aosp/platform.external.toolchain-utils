import job
from automation.common import machine_description


def _GetP4ClientSpec(client_name, p4_paths):
  p4_string = ""
  for p4_path in p4_paths:
    p4_string += " -a \"" + (" //" + client_name + "/").join(p4_path) + "\""

  return p4_string


def GetP4Command(p4_port, p4_paths, revision, checkoutdir):
  client_name = "p4-automation-$JOB_ID"
  command = ""
  command += " export P4CONFIG=.p4config"
  command += " && mkdir -p " + checkoutdir
  command += " && cd " + checkoutdir
  command += " && cp ${HOME}/.p4config ."
  command += " && chmod u+w .p4config"
  command += " && echo \"P4PORT=" + p4_port + "\" >> .p4config"
  command += " && echo \"P4CLIENT=" + client_name + "\" >> .p4config"
  command += (" && g4 client " +
              _GetP4ClientSpec(client_name, p4_paths))
  command += " && g4 sync ..."
  command += " && g4 client -d " + client_name
  return command

def CreateP4Job(p4_port, p4_paths, revision, checkoutdir):
  to_return = job.Job(GetP4Command(p4_port, p4_paths, revision, checkoutdir))
  return to_return

def CreateSetupChromeOSJob(chromeos_version):
  to_return = job.Job("v14/setup_chromeos.py --dir=chromeos --version=%s"
            % (chromeos_version))

  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  p4_revision = 1
  p4_checkoutdir = "perforce2"

  p4_job = CreateP4Job(p4_port, p4_paths, p4_revision,
                                  p4_checkoutdir)
  to_return.AddChild(p4_job)
  to_return.AddRequiredFolder(p4_job, "perforce2/gcctools/chromeos/v14", "v14")

  return to_return

