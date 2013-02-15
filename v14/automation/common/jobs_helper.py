import getpass
import job
from automation.common import machine_description
import os
import re
import sys
import time
from utils import utils

depot2_dir = "//depot2/"
p4_checkout_dir = "perforce2/"
version_dir = "/gcctools/chromeos/v14/"
p4_version_dir = p4_checkout_dir + version_dir

chromeos_root = "chromeos"
scripts_dir = "src/scripts"
chromeos_scripts_dir = chromeos_root + "/" + scripts_dir

tc_pkgs_dir = "output/pkgs"
tc_objects_dir = "output/objects"

perflab_binary = "/home/mobiletc-prebuild/perflab-checkout/google3/blaze-bin/platforms/performance/brrd/perflab/perflab"
perflab_interpreter_arg = "--perflab_interpreter=/home/mobiletc-prebuild/perflab-checkout/google3/blaze-bin/platforms/performance/brrd/run_tools/experiment_job_dag"
perflab_brrd_config_arg = "--brrd_config=/home/mobiletc-prebuild/perflab-checkout/google3/platforms/performance/brrd/perflab/util/perflab.cfg"
perflab_options = "--alsologtostderr"
perflab_command = ("%s %s %s %s " %
    (perflab_binary, perflab_interpreter_arg,
     perflab_brrd_config_arg, perflab_options))

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

  client_name = "p4-automation-$HOSTNAME-$JOB_ID"
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

def GetChromeOSCheckoutLocation():
  return "/home/mobiletc-prebuild/www/chromeos_golden_sources/"

def GetChromeOSImageLocation():
  return "/home/mobiletc-prebuild/www/chromeos_golden_images/"

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

def GetP4BenchmarksDirCommand(p4_snapshot=""):
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/third_party/android_bench/v2_0/...", "gcctools/chromeos/v14/third_party/android_bench/v2_0/..."))
  p4_revision = 1
  command = GetP4Command(p4_port, p4_paths, p4_revision, p4_checkout_dir, p4_snapshot)
  return command

def GetTCRootDir(toolchain="trunk"):
  if toolchain == "trunk":
    gcctools_prefix = ""
  elif toolchain == "v1":
    gcctools_prefix = "branches/chromeos_toolchain_v1_release_branch/"
  else:
    utils.AssertExit(False, "Toolchain can only be trunk or branch")
  local_path = p4_checkout_dir + gcctools_prefix + "gcctools/"
  depot_path = depot2_dir + gcctools_prefix + "gcctools/"
  return depot_path, local_path

def _GetToolchainCheckoutCommand(toolchain="trunk", p4_snapshot=""):
  p4_port = "perforce2:2666"
  p4_paths = []
  p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
  utils.AssertExit(toolchain == "v1" or toolchain == "trunk")
  depot_path, local_path = GetTCRootDir(toolchain)
  short_local_path = "/".join(local_path.split("/")[1:])
  p4_paths.append((depot_path + "google_vendor_src_branch/gcc/gcc-4.4.3/...",
                   short_local_path + "google_vendor_src_branch/gcc/gcc-4.4.3/..."))
  p4_paths.append((depot_path + "google_vendor_src_branch/binutils/binutils-2.20.1-mobile/...",
                   short_local_path + "google_vendor_src_branch/binutils/binutils-2.20.1-mobile/..."))
  p4_paths.append((depot_path + "google_vendor_src_branch/binutils/binutils-20100303/...",
                   short_local_path + "google_vendor_src_branch/binutils/binutils-20100303/..."))
  p4_revision = 1

  command = GetP4Command(p4_port, p4_paths,
                                 p4_revision, p4_checkout_dir, p4_snapshot)
  return command



def CreateBuildTCJob(chromeos_version="top",
                     board="x86-generic",
                     p4_snapshot="",
                     toolchain="trunk"):

  depot_path, local_path = GetTCRootDir(toolchain)
  command = GetInitialCommand()
  command += "&& " + _GetToolchainCheckoutCommand(toolchain, p4_snapshot)

  # When g4 syncs this file, often times the timestamp of this file is earlier
  # than that of the file that is its dependency (ldlex.l).
  # Since we mount the filesystem as r/o in the build, we cannot regenerate
  # this file (we also link instead of copy in the 9999 ebuild).
  # Longer-term, we would want to change the fileattr of this file in g4
  # so it syncs the timestamp as well as the file contents.
  # This is a workaround.
  command += ("&& touch " + local_path + "google_vendor_src_branch/" +
              "binutils/binutils-2.20.1-mobile/ld/ldlex.c")

  command += "&& " + _GetSetupChromeOSCommand(chromeos_version, True)

  command += "&& " + _GetBuildTCCommand(toolchain, board, False, True)
  tc_job = CreateLinuxJob(command)
  return tc_job

def _GetMakeChrootCommand(delete=False):
  make_chroot_args = ""
  if delete==True:
    make_chroot_args = " --delete"
  command = "cd " + chromeos_scripts_dir
  command += "&& ./make_chroot --fast " + make_chroot_args
  command += "&& cd -"
  return command

def CreateDejaGNUJob(chromeos_version="latest",
    board="x86-generic", p4_snapshot="", toolchain="trunk"):
  local_path = GetTCRootDir(toolchain)[1]
  command = GetInitialCommand()
  command += "&& " + _GetToolchainCheckoutCommand(toolchain)
  command += "&& " + _GetSetupChromeOSCommand(chromeos_version, True)
  command += "&& " + _GetMakeChrootCommand()
  command += ("&& " + p4_version_dir + "/run_dejagnu.py" +
              " --chromeos_root=chromeos"
              " --toolchain_root=" + local_path +
              " --remote=$SECONDARY_MACHINES[0]" +
              " --board=" + board)
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredMachine("", "chromeos", True, False)
  return to_return

def CreateBuildAndTestChromeOSJob(chromeos_version="latest",
                                  board="x86-generic",
                                  p4_snapshot="",
                                  toolchain="trunk"):
  command = GetInitialCommand()
  # TODO(asharif): Get rid of this hack at some point.
  command += "&& mkdir -p perforce2/gcctools/google_vendor_src_branch/gcc"
  command += "&& " + GetP4VersionDirCommand(p4_snapshot)

  command += "&& " + _GetSetupChromeOSCommand(chromeos_version, False)
  command += "&& " + _GetBuildTCCommand(toolchain, board)
  command += ("&& " + p4_version_dir + "/build_chromeos.py" +
              " --chromeos_root=" + chromeos_root +
              " --board=" + board)

  command += "&& " + _GetImageChromeOSCommand()

  command += ("&& " + p4_version_dir + "/run_tests.py" +
              " --remote=$SECONDARY_MACHINES[0] " +
              " --chromeos_root=" + chromeos_root +
              " --board=" + board +
              " bvt Page")

  to_return = CreateLinuxJob(command)

  to_return.AddRequiredMachine("", "chromeos", True, False)

  return to_return

def _GetImageChromeOSCommand():
  command = (p4_version_dir + "/image_chromeos.py" +
             " --chromeos_root=chromeos" +
             " --remote=$SECONDARY_MACHINES[0]")
  return command

def _GetSetupChromeOSCommand(version, use_minilayout=False, board="x86-generic"):
  command = ""
  version_re = "^\d+\.\d+\.\d+\.[a-zA-Z0-9]+$"
  if version == "weekly" or version == "quarterly":
    location = GetChromeOSCheckoutLocation() + board + "/" + version
    location_dir = utils.GetRoot(location)[0]
    utils.AssertExit(os.path.islink(location) == True,
                     "Symlink: " + location + " does not exist.")
    location_expanded = os.path.realpath(location)
    chromeos_version = utils.GetRoot(location_expanded)[1]
    utils.AssertExit(re.match(version_re, chromeos_version) is not None,
                     "Version " + chromeos_version + " is invalid!")
  elif (version == "top" or version == "latest" or
        re.match(version_re, version)):
    chromeos_version = version
  else:
    command += "rsync -a " + version + " chromeos"
    return command

  command += (p4_version_dir + "/setup_chromeos.py" +
              " --dir=" + chromeos_root +
              " --version=" + chromeos_version)
  if use_minilayout == True:
    command += " --minilayout"
  return command

def _GetBuildTCCommand(toolchain, board, use_binary=True, rebuild=False):
  local_path = GetTCRootDir(toolchain)[1]
  command = (p4_version_dir + "/build_tc.py" +
             " --toolchain_root=" + local_path +
             " --chromeos_root=" + chromeos_root)
  if use_binary:
    command += " -B"
  return command

def CreatePerflabJob(chromeos_version,
                                  benchmark,
                                  board="x86-generic",
                                  p4_snapshot="",
                                  toolchain="trunk"):
  toolchain_root = GetTCRootDir("trunk")[1]
  if "cpu" in benchmark:
    use_minilayout = True
  else:
    use_minilayout = False
  command = GetInitialCommand()
  command += "&& " + GetP4VersionDirCommand(p4_snapshot)
  command += "&& " + GetP4BenchmarksDirCommand(p4_snapshot)

  command += "&& " + _GetSetupChromeOSCommand(chromeos_version, use_minilayout)
  command += "&& " + _GetBuildTCCommand(toolchain, board)
  command += ("&& %s --crosstool=$PWD/%s  --chromeos_root=$PWD/%s" +
              " --machines=chromeos_x86-agz_1 build %s" %
              (perflab_command, toolchain_root, chromeos_root, benchmark))
  command += ("&& %s --crosstool=$PWD/%s  --chromeos_root=$PWD/%s" +
              " --machines=chromeos_x86-agz_1 run %s" %
              (perflab_command, toolchain_root, chromeos_root, benchmark))
  to_return = CreateLinuxJob(command)
  return to_return

def CreateTestJob(build_chromeos_job):
  command = GetInitialCommand()
  command += " && cd " + chromeos_scripts_dir
  command = "&& ./run_remote_tests.sh --remote=" + hostname + " BuildVerify"
  to_return = CreateLinuxJob(command)
  to_return.AddRequiredFolder(p4_job, p4_version_dir, p4_version_dir)
  return to_return

def CreateUpdateJob(chromeos_versions,
                    create_image=True,
                    p4_snapshot="",
                    board="x86-generic"):
  command = GetInitialCommand()
  command += "&& " + GetP4VersionDirCommand(p4_snapshot)
  command += ("&& " + p4_version_dir + "/setup_chromeos.py" +
              " --dir=" + chromeos_root +
              " --version=latest")
  command += ("&& " + p4_version_dir + "/build_chromeos.py" +
              " --chromeos_root=" + chromeos_root +
              " --vanilla --board=" + board)
  command += "&& " + _GetMakeChrootCommand(True)

  image_location = GetChromeOSImageLocation() + board
  src_location = GetChromeOSCheckoutLocation() + board
  command += "&& mkdir -p " + image_location
  command += "&& mkdir -p " + src_location
  dirname = "$(cd chromeos/src/scripts; git branch | cut -d' ' -f 2)"
  image_dir = dirname + ".image." + board
  src_dir = dirname

  command += " && touch " + src_location + "/" + src_dir
  command += (" && rsync -a chromeos/src/build/images/" + board + "/ " +
              image_location + "/" + image_dir)
  for chromeos_version in chromeos_versions.split(","):
    image_link = chromeos_version + ".image." + board
    src_link = chromeos_version
    command += (" && ln -fs -T " + image_dir + " " +
                image_location + "/" + image_link)
    command += (" && ln -fs -T " + src_dir + " " +
                src_location + "/" + src_link)
  to_return = CreateLinuxJob(command)
  return to_return

