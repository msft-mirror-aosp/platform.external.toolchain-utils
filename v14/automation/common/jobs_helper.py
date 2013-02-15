import getpass
import job
from automation.common import machine_description
import os
import re
import sys
import time
from utils import utils

p4_checkout_dir = "perforce2"
version_dir = "/gcctools/chromeos/v14/"
install_dir = "/output/install"
objects_dir = "/output/objects"
pkgs_dir = "/output/pkgs"
p4_version_dir = p4_checkout_dir + version_dir
p4_install_dir = p4_checkout_dir + version_dir + install_dir
p4_objects_dir = p4_checkout_dir + version_dir + objects_dir
p4_pkgs_dir = p4_checkout_dir + version_dir + pkgs_dir

chromeos_root = "chromeos"
scripts_dir = "src/scripts"
chromeos_scripts_dir = chromeos_root + "/" + scripts_dir

def _GetP4ClientSpec(client_name, p4_paths):
  p4_string = ""
  for p4_path in p4_paths:
    p4_string += " -a \"" + (" //" + client_name + "/").join(p4_path) + "\""

  return p4_string


def GetP4Command(p4_port, p4_paths, revision, checkoutdir, p4_snapshot=""):
  command = ""

  if p4_snapshot:
    command += "mkdir -p " + checkoutdir
    for p4_path in p4_paths:
      real_path = p4_path[1]
      if real_path.endswith("..."):
        real_path = real_path.replace("/...", "")
        command += ("; mkdir -p " + checkoutdir + "/" +
                    os.path.dirname(real_path))
        command += ("&& rsync -lr " + p4_snapshot + "/" + real_path +
                  " " + checkoutdir + "/" + os.path.dirname(real_path))
    return command

  client_name = "p4-automation-$JOB_ID"
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

def GetWeeklyChromeOSLocation():
  return "/home/" + getpass.getuser() + "/www/chromeos_checkout/weekly"

def GetQuarterlyChromeOSLocation():
  return "/home/" + getpass.getuser() + "/www/chromeos_checkout/quarterly"

def GetInitialCommand():
  return "pwd && uname -a"

def GetCopyTreeCommand(source, dest):
  command = ""
  command += "mkdir -p " + dest
  command += "&& cp -pr " + source + "/* " + dest
  return command

def GetP4VersionDirCommand(p4_snapshot=""):
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  p4_revision = 1
  command = GetP4Command(p4_port, p4_paths, p4_revision, p4_checkout_dir, p4_snapshot)
  return command


def CreateBuildTCJob(chromeos_version="top",
                     board="x86-generic",
                     p4_snapshot="",
                     toolchain="trunk"):
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  if toolchain == "trunk":
    toolchain_root = p4_checkout_dir + "/gcctools"
    p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                     "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
    p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/binutils/binutils-2.20.1-mobile/...",
                     "gcctools/google_vendor_src_branch/binutils/binutils-2.20.1-mobile/..."))
    p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/binutils/binutils-20100303/...",
                     "gcctools/google_vendor_src_branch/binutils/binutils-20100303/..."))
  elif toolchain == "branch":
    toolchain_root = p4_checkout_dir + "/branches/chromeos_toolchain_v1_release_branch/gcctools"
    p4_paths.append(("//depot2/branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                     "branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
    p4_paths.append(("//depot2/branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/binutils/binutils-2.20.1-mobile/...",
                     "branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/binutils/binutils-2.20.1-mobile/..."))
    p4_paths.append(("//depot2/branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/binutils/binutils-20100303/...",
                     "branches/chromeos_toolchain_v1_release_branch/gcctools/google_vendor_src_branch/binutils/binutils-20100303/..."))
  p4_revision = 1

  command = GetInitialCommand()
  command += "; " + GetP4Command(p4_port, p4_paths,
                                 p4_revision, p4_checkout_dir, p4_snapshot)

  if chromeos_version == "weekly":
    command += "; cp -rp " + GetWeeklyChromeOSLocation() + " chromeos"
  elif chromeos_version == "quarterly":
    command += " ; cp -rp " + GetQuarterlyChromeOSLocation() + " chromeos"
  elif (chromeos_version == "top" or chromeos_version == "latest" or
        re.match("^\d\.\d\.\d\.\d$", chromeos_version)):
    command += ("; " + p4_version_dir + "/setup_chromeos.py" +
                " --dir=" + chromeos_root +
                " --version=" + chromeos_version +
                " --minilayout")
  else:
    command += "; cp -rp " + chromeos_version + " chromeos"


  command += ("; " + p4_version_dir + "/build_tc.py" +
                      " --toolchain_root=" + toolchain_root +
                      " --chromeos_root=" + chromeos_root +
                      " --board=" + board +
                      " -f")
  tc_job = CreateLinuxJob(command)
  return tc_job

def CreateDejaGNUJob(tc_job, board="x86-generic", p4_snapshot=""):
  command = GetInitialCommand()
  command += "; " + GetP4VersionDirCommand(p4_snapshot)
  command += ("&& " + p4_version_dir + "/run_dejagnu.py" +
              " --chromeos_root=chromeos"
              " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
              " --remote=$SECONDARY_MACHINES[0]" +
              " --board=" + board)
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(tc_job, p4_objects_dir, p4_objects_dir)
  to_return.AddRequiredMachine("", "chromeos", False, False)
  return to_return

def CreateBuildAndTestChromeOSJob(tc_job, chromeos_version="latest",
                                  board="x86-generic",
                                  p4_snapshot=""):
  command = GetInitialCommand()
  # TODO(asharif): Get rid of this hack at some point.
  command += "&& mkdir -p perforce2/gcctools/google_vendor_src_branch/gcc"
  command += "; " + GetP4VersionDirCommand(p4_snapshot)

  if chromeos_version == "weekly":
    command += "; cp -rp " + GetWeeklyChromeOSLocation() + " chromeos"
  elif chromeos_version == "quarterly":
    command += " cp -rp " + GetQuarterlyChromeOSLocation() + " chromeos"
  elif (chromeos_version == "top" or chromeos_version == "latest" or
        re.match("^\d\.\d\.\d\.\d$", chromeos_version)):
    command += ("; " + p4_version_dir + "/setup_chromeos.py" +
                " --dir=" + chromeos_root +
                " --version=" + chromeos_version)
  else:
    command += "; cp -rp " + chromeos_version + " chromeos"

  command += ("; " + p4_version_dir + "/build_tc.py" +
                      " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
                      " --chromeos_root=" + chromeos_root +
                      " -B")
  command += ("; " + p4_version_dir + "/build_chromeos.py" +
              " --toolchain_root=" + p4_checkout_dir + "/gcctools" +
              " --chromeos_root=" + chromeos_root +
              " --board=" + board)

  command += ("; " + chromeos_scripts_dir + "/image_to_live.sh " +
              " --board=" + board +
              " --remote=$SECONDARY_MACHINES[0]")

  command += ("; " + p4_version_dir + "/run_tests.py" + 
              " --remote=$SECONDARY_MACHINES[0] " +
              " --chromeos_root=" + chromeos_root +
              " --board=" + board +
              " bvt Page")

  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(tc_job, p4_pkgs_dir, p4_pkgs_dir)

  to_return.AddRequiredMachine("", "chromeos", False, False)

  return to_return

def CreateTestJob(build_chromeos_job):
  command = GetInitialCommand()
  command += " && cd " + chromeos_scripts_dir
  command = "&& ./run_remote_tests.sh --remote=" + hostname + " BuildVerify"
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(p4_job, p4_version_dir, p4_version_dir)
  return to_return

def CreateUpdateJob(chromeos_version,
                    create_image=True,
                    p4_snapshot="",
                    board="x86-generic"):
  command = GetInitialCommand()
  dirname = time.asctime()
  dirname = dirname.replace(" ", "-")
  command += "; " + GetP4VersionDirCommand(p4_snapshot)
  command += ("; " + p4_version_dir + "/setup_chromeos.py" +
              " --dir=" + chromeos_root +
              " --version=latest")
  command += ("; " + p4_version_dir + "/build_chromeos.py" + 
              " --chromeos_root=" + chromeos_root +
              " --vanilla --board=" + board)
  command += ("&& cd chromeos/src/scripts " +
              "&& ./make_chroot --delete" +
              "&& cd -")

  location = utils.GetRoot(GetWeeklyChromeOSLocation())[0]
  command += "&& mkdir -p " + location
###  command += ("&& rsync -a" +
###              " --exclude=build --exclude=.repo/ --exlclude=.git/" +
###              " chromeos/ " + location +
###              "/chromeos." + dirname)
###  command += (" && ln -fs -T chromeos." + dirname + " " +
###              location + "/" + chromeos_version)
  command += (" && rsync -r chromeos/build/ " + location +
              "/chormeos." + dirname + ".build")
  command += (" && ln -fs -T chromeos." + dirname + ".build " +
              location + "/" + chromeos_version + ".build")
  to_return = CreateLinuxJob(command)
  return to_return

