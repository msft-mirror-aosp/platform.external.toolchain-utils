import job
from automation.common import machine_description

p4_checkout_dir = "perforce2"
chromeos_root = "chromeos"
scripts_dir = "gcctools/chromeos/v14/"
install_dir = "output/install"
p4_scripts_dir = p4_checkout_dir + "/" + scripts_dir
p4_install_dir = p4_checkout_dir + "/" + scripts_dir + "/" + install_dir

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
  command += " && cd -"
  return command

def CreateLinuxJob(command):
  to_return = job.Job(command)
  to_return.AddRequiredMachine("", "linux", False)
  return to_return

def CreateP4Job(p4_port, p4_paths, revision, checkoutdir):
  to_return = CreateLinuxJob(GetP4Command(p4_port, p4_paths,
                             revision, checkoutdir))
  return to_return

def CreateP4ToolchainJob():
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                   "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
  p4_revision = 1
  
  p4_job = CreateP4Job(p4_port, p4_paths, p4_revision, p4_checkout_dir)
  return p4_job

def GetWeeklyChromeOSLocation():
  return "/usr/local/google/home/chromeos"

def GetQuarterlyChromeOSLocation():
  return "/usr/local/google/home/chromeos"

def CreateBuildTCJob():
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                   "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
  p4_revision = 1

  command = ""
  command += GetP4Command(p4_port, p4_paths, p4_revision, p4_checkout_dir)

  command += " ; sudo cp -rp " + GetWeeklyChromeOSLocation() + " chromeos"

  command += (" ; " + p4_scripts_dir + "/build_tc.py" +
                      " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
                      " --chromeos_root=" + chromeos_root +
                      " -f")
  tc_job = CreateLinuxJob(command)
  return tc_job

def CreateBuildChromeOSJob(p4_job):
  command = ""
  command += " sudo cp -rp " + GetWeeklyChromeOSLocation() + " chromeos"
  command += (" ; " + p4_scripts_dir + "/build_tc.py" +
                      " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
                      " --chromeos_root=" + chromeos_root +
                      " -B")
  command += (" ; " + p4_scripts_dir + "/build_chromeos.py" +
              " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
              " --chromeos_root=" + chromeos_root +
              " --board=x86-generic")
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(p4_job, p4_install_dir, p4_install_dir)
  return to_return

def CreateSetupChromeOSJob(p4_job):
  to_return = CreateLinuxJob("v14/setup_chromeos.py --dir=chromeos --version=%s"
            % (chromeos_version))

  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  p4_revision = 1

  p4_job = CreateP4Job(p4_port, p4_paths, p4_revision,
                                  p4_checkout_dir)
  to_return.AddChild(p4_job)
  to_return.AddRequiredFolder(p4_job, p4_scripts_dir, p4_scripts_dir)

  return to_return

def CreateCPChromeOSJob(path):
  command = "mv chromeos chromeos.old"
  command += "; sudo cp -r " + path + " chromeos"
  to_return = CreateLinuxJob(command)
  return to_return

def CreateTestJob(p4_job, hostname):
  command = ("./run_remote_tests.sh --remote=" + hostname + " BuildVerify")
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(p4_job, p4_scripts_dir, p4_scripts_dir)
  return to_return

