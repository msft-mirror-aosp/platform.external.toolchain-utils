#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import re

from automation.common import command as cmd
from automation.common import job
from automation.common import machine
from utils import logger
from utils import utils

DEPOT2_DIR = "//depot2/"
P4_CHECKOUT_DIR = "perforce2/"
P4_VERSION_DIR = os.path.join(P4_CHECKOUT_DIR, "gcctools/chromeos/v14")

CHROMEOS_ROOT = "chromeos"
CHROMEOS_SCRIPTS_DIR = os.path.join(CHROMEOS_ROOT, "src/scripts")
CHROMEOS_BUILDS_DIR = "/home/mobiletc-prebuild/www/chromeos_builds"


def _GetP4ClientSpec(client_name, p4_paths):
  mappings = [(remote, os.path.join(client_name, local))
              for remote, local in p4_paths]

  return " ".join(["-a \"%s //%s\"" % mapping for mapping in mappings])


def GetP4Command(p4_port, p4_paths, revision, checkoutdir, p4_snapshot=""):
  if p4_snapshot:
    return _GetP4SnapshotCommand(p4_paths, checkoutdir, p4_snapshot)

  client_name = "p4-automation-$HOSTNAME-$JOB_ID"

  return cmd.Chain(
      "export P4CONFIG=.p4config",
      "mkdir -p %s" % checkoutdir,
      "cd %s" % checkoutdir,
      "cp ${HOME}/.p4config .",
      "chmod u+w .p4config",
      "echo \"P4PORT=%s\" >> .p4config" % p4_port,
      "echo \"P4CLIENT=%s\" >> .p4config" % client_name,
      "g4 client %s" % _GetP4ClientSpec(client_name, p4_paths),
      "g4 sync ...",
      "g4 client -d %s" % client_name,
      "cd -")


def _GetP4SnapshotCommand(p4_paths, checkoutdir, p4_snapshot):
  command = ["mkdir -p %s" % checkoutdir]

  for p4_path in p4_paths:
    local_path = p4_path[1]

    if local_path.endswith("..."):
      local_path = local_path.replace("/...", "")

      remote_checkout_dir = os.path.join(p4_snapshot, local_path)
      local_checkout_dir = os.path.join(checkoutdir,
                                        os.path.dirname(local_path))

      command.append(cmd.Chain(
          "mkdir -p %s" % local_checkout_dir,
          "rsync -lr %s %s" % (remote_checkout_dir, local_checkout_dir)))

  return " ; ".join(command)


def CreateLinuxJob(label, command, lock=False):
  to_return = job.Job(label, command)
  to_return.DependsOnMachine(machine.MachineSpecification("*", "linux", lock))
  return to_return


def GetInitialCommand():
  return cmd.Chain("pwd", "uname -a")


def GetCopyTreeCommand(source, dest):
  return cmd.Chain(
      "mkdir -p %s" % dest,
      "cp -pr %s/* %s" % (source, dest))


def GetP4VersionDirCommand(p4_snapshot=""):
  p4_port = "perforce2:2666"
  p4_paths = [("//depot2/gcctools/chromeos/v14/...",
               "gcctools/chromeos/v14/...")]
  p4_revision = 1
  return GetP4Command(p4_port, p4_paths, p4_revision, P4_CHECKOUT_DIR,
                      p4_snapshot)


def GetP4BenchmarksDirCommand(p4_snapshot=""):
  p4_port = "perforce2:2666"
  p4_paths = [("//depot2/third_party/android_bench/v2_0/...",
               "third_party/android_bench/v2_0/...")]
  p4_revision = 1
  return GetP4Command(p4_port, p4_paths, p4_revision, P4_CHECKOUT_DIR,
                      p4_snapshot)


def GetTCRootDir(toolchain="trunk"):
  mapping = {"trunk": "",
             "v1": "branches/chromeos_toolchain_v1_release_branch",
             "v2": "branches/mobile_toolchain_v14_release_branch"}

  try:
    gcctools_prefix = mapping[toolchain]
  except KeyError:
    logger.GetLogger().LogFatal("Wrong value for toolchain %s" % toolchain)

  local_path = os.path.join(P4_CHECKOUT_DIR, gcctools_prefix, "gcctools/")
  depot_path = os.path.join(DEPOT2_DIR, gcctools_prefix, "gcctools/")

  return depot_path, local_path


def _GetToolchainCheckoutCommand(toolchain="trunk", p4_snapshot=""):
  p4_port = "perforce2:2666"

  depot_path, local_path = GetTCRootDir(toolchain)
  local_path = local_path.split("/", 1)[1]

  depot_path = os.path.join(depot_path, "google_vendor_src_branch")
  local_path = os.path.join(local_path, "google_vendor_src_branch")

  p4_paths = [("//depot2/gcctools/chromeos/v14/...",
               "gcctools/chromeos/v14/..."),
              (os.path.join(depot_path, "gcc/gcc-4.4.3/..."),
               os.path.join(local_path, "gcc/gcc-4.4.3/...")),
              (os.path.join(depot_path, "binutils/binutils-2.20.1-mobile/..."),
               os.path.join(local_path, "binutils/binutils-2.20.1-mobile/...")),
              (os.path.join(depot_path, "binutils/binutils-20100303/..."),
               os.path.join(local_path, "binutils/binutils-20100303/..."))]
  p4_revision = 1

  return GetP4Command(p4_port, p4_paths, p4_revision, P4_CHECKOUT_DIR,
                      p4_snapshot)


def GetBuildToolchainCommand(chromeos_version="top", board="x86-generic",
                             p4_snapshot="", toolchain="trunk"):

  _, local_path = GetTCRootDir(toolchain)

  return cmd.Chain(
      GetInitialCommand(),
      _GetToolchainCheckoutCommand(toolchain, p4_snapshot),
      # When g4 syncs this file, often times the timestamp of this file is
      # earlier than that of the file that is its dependency (ldlex.l).
      # Since we mount the filesystem as r/o in the build, we cannot
      # regenerate this file (we also link instead of copy in the 9999
      # ebuild).  Longer-term, we would want to change the fileattr of
      # this file in g4 so it syncs the timestamp as well as the file
      # contents.
      # This is a workaround.
      "touch %s" % os.path.join(local_path, "google_vendor_src_branch",
                                "binutils/binutils-2.20.1-mobile",
                                "ld/ldlex.c"),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCCommand(toolchain, board, False, True))


def _GetMakeChrootCommand(delete=False):
  make_chroot = cmd.Shell("make_chroot", path=".", opts=["--fast"])

  if delete:
    make_chroot.AddOption("--delete")

  return cmd.Chain("cd %s" % CHROMEOS_SCRIPTS_DIR, make_chroot, "cd -")


def GetDejaGNUCommand(chromeos_version="top", board="x86-generic",
                      p4_snapshot="", toolchain="trunk"):
  local_path = GetTCRootDir(toolchain)[1]
  dejagnu_logs = os.path.join(local_path, "output/dejagnu")

  return cmd.Chain(
      GetInitialCommand(),
      _GetToolchainCheckoutCommand(toolchain),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCCommand(toolchain, board),
      cmd.Shell("run_dejagnu.py",
                path=P4_VERSION_DIR,
                opts=["--testflags=\"\"",
                      "--chromeos_root=%s" % CHROMEOS_ROOT,
                      "--toolchain_root=%s" % local_path,
                      "--remote=$SECONDARY_MACHINES[0]",
                      "--board=%s" % board]),
      cmd.Shell("summarize_results.py", os.path.join(dejagnu_logs, "gcc.log"),
                path=P4_VERSION_DIR),
      cmd.Shell("summarize_results.py", os.path.join(dejagnu_logs, "g++.log"),
                path=P4_VERSION_DIR))


def GetBuildAndTestChromeOSCommand(chromeos_version="latest",
                                   board="x86-generic", p4_snapshot="",
                                   toolchain="trunk", tests=None):

  test_list = tests or []

  return cmd.Chain(
      GetInitialCommand(),
      # TODO(asharif): Get rid of this hack at some point.
      "mkdir -p perforce2/gcctools/google_vendor_src_branch/gcc",
      GetP4VersionDirCommand(p4_snapshot),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCCommand(toolchain, board),
      _GetBuildChromeOSCommand(board),
      _GetImageChromeOSCommand(board),
      cmd.Shell("run_tests.py", "bvt", *test_list,
                path=P4_VERSION_DIR,
                opts=["--remote=$SECONDARY_MACHINES[0]",
                      "--chromeos_root=%s" % CHROMEOS_ROOT,
                      "--board=%s" % board]),
      cmd.Shell("summarize_results.py",
                os.path.join(P4_VERSION_DIR, "logs/run_tests.py.out"),
                path=P4_VERSION_DIR))


def _GetImageChromeOSCommand(board):
  return cmd.Shell("image_chromeos.py",
                   path=P4_VERSION_DIR,
                   opts=["--chromeos_root=%s" % CHROMEOS_ROOT,
                         "--remote=$SECONDARY_MACHINES[0]",
                         "--board=%s" % board])


def _GetSetupChromeOSScriptCommand(version="latest", use_minilayout=False):
  setup_chromeos = cmd.Shell("setup_chromeos.py",
                             path=P4_VERSION_DIR,
                             opts=["--dir=%s" % CHROMEOS_ROOT,
                                   "--version=%s" % version])

  if use_minilayout:
    setup_chromeos.AddOption("--minilayout")

  return setup_chromeos


def _GetBuildChromeOSCommand(board, vanilla=False):
  build_chromeos = cmd.Shell("build_chromeos.py",
                             path=P4_VERSION_DIR,
                             opts=["--chromeos_root=%s" % CHROMEOS_ROOT,
                                   "--board=%s" % board])

  if vanilla:
    build_chromeos.AddOption("--vanilla")

  return build_chromeos


def _GetSetupChromeOSCommand(version, use_minilayout=False):
  version_re = "^\d+\.\d+\.\d+\.[a-zA-Z0-9]+$"

  location = os.path.join(CHROMEOS_BUILDS_DIR, version)

  if version in ["weekly", "quarterly"]:
    logger.GetLogger().LogFatalIf(not os.path.islink(location),
                                  "Symlink %s does not exist." % location)
    location_expanded = os.path.realpath(location)
    version = utils.GetRoot(location_expanded)[1]

  if version in ["top", "latest"] or re.match(version_re, version):
    return _GetSetupChromeOSScriptCommand(version, use_minilayout)
  elif version.endswith("bz2") or version.endswith("gz"):
    return cmd.Chain(
        "mkdir %s" % CHROMEOS_ROOT,
        "tar -xf %s -C %s" % (location_expanded, CHROMEOS_ROOT))
  else:
    signature_file_location = os.path.join(location,
                                           "src/scripts/enter_chroot.sh")
    logger.GetLogger().LogFatalIf(not os.path.exists(signature_file_location),
                                  "Signature file %s does not exist." %
                                  signature_file_location)
    return "rsync -a %s/ chromeos/" % version


def _GetBuildTCCommand(toolchain, board, use_binary=True, rebuild=False):
  local_path = GetTCRootDir(toolchain)[1]

  build_tc = cmd.Shell("build_tc.py", path=P4_VERSION_DIR,
                       opts=["--toolchain_root=%s" % local_path,
                             "--chromeos_root=%s" % CHROMEOS_ROOT,
                             "--board=%s" % board])

  if use_binary:
    build_tc.AddOption("-B")

  return build_tc


def GetPerflabCommand(chromeos_version, benchmark, board="x86-agz",
                      p4_snapshot="", toolchain="trunk"):
  toolchain_root = GetTCRootDir("trunk")[1]

  perflab_output_dir = "perflab-output"

  perflab_checkout_path = "/home/mobiletc-prebuild/perflab-checkout"
  perflab_bbrd_bin_path = "google3/blaze-bin/platforms/performance/brrd"
  perflab_bbrd_src_path = "google3/platforms/performance/brrd"

  perflab_binary_path = os.path.join(perflab_checkout_path,
                                     perflab_bbrd_bin_path,
                                     "perflab")

  perflab_interpreter_path = os.path.join(perflab_checkout_path,
                                          perflab_bbrd_bin_path,
                                          "run_tools/experiment_job_dag")

  perflab_brrd_config_path = os.path.join(perflab_checkout_path,
                                          perflab_bbrd_src_path,
                                          "perflab/util/perflab.cfg")

  perflab_command = cmd.Shell(
      "perflab",
      path=perflab_binary_path,
      opts=["--perflab_interpreter=%s" % perflab_interpreter_path,
            "--brrd_config=%s" % perflab_brrd_config_path,
            "--alsologtostderr",
            "--noenable_loas_kerberos_checks_at_startup",
            "--stubby_server_host=$(hostname)",
            "--crosstool=$PWD/%s" % toolchain_root,
            "--chromeos_root=$PWD/%s" % CHROMEOS_ROOT,
            "--arch=chromeos_%s" % board,
            "--workdir=$(readlink -f %s)" % P4_VERSION_DIR])

  # TODO(asharif): Compare this to a golden baseline dir.
  return cmd.Chain(
      GetInitialCommand(),
      GetP4VersionDirCommand(p4_snapshot),
      GetP4BenchmarksDirCommand(p4_snapshot),
      _GetSetupChromeOSScriptCommand(chromeos_version),
      _GetBuildTCCommand(toolchain, board),
      "%s build %s" % (perflab_command, benchmark),
      "%s run %s" % (perflab_command, benchmark),
      "mkdir -p results",
      "rsync -a %s/%s/ results/%s/" % (P4_VERSION_DIR,
                                       perflab_output_dir,
                                       perflab_output_dir))


def GetUpdateCommand(chromeos_versions, create_image=True, p4_snapshot="",
                     boards="x86-generic"):
  cmds = cmd.Chain(GetInitialCommand(),
                   GetP4VersionDirCommand(p4_snapshot),
                   _GetSetupChromeOSScriptCommand())

  board_list = boards.split(",")

  for board in board_list:
    cmds.append(_GetBuildChromeOSCommand(board, True))

  dirname = "$(cd chromeos/src/scripts; git describe --tags --always HEAD)"

  build_location = os.path.join(CHROMEOS_BUILDS_DIR, dirname)

  for board in board_list:
    board_build = os.path.join(build_location, board)
    board_source = os.path.join("chromeos/src/build/images", board)

    cmds.extend(["mkdir -p %s" % board_build,
                 "rsync -a %s/ %s/" % (board_source, board_build)])

  for chromeos_version in chromeos_versions.split(","):
    build_link = os.path.join(CHROMEOS_BUILDS_DIR, chromeos_version)

    cmds.append("ln -fs -T %s %s" % (dirname, build_link))

  return cmds
