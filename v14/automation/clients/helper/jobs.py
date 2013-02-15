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
  cmds = [cmd.Shell("mkdir", "-p", checkoutdir)]

  for p4_path in p4_paths:
    local_path = p4_path[1]

    if local_path.endswith("..."):
      local_path = local_path.replace("/...", "")

      remote_checkout_dir = os.path.join(p4_snapshot, local_path)
      local_checkout_dir = os.path.join(checkoutdir,
                                        os.path.dirname(local_path))

      cmds.append(cmd.Chain(
          "mkdir -p %s" % local_checkout_dir,
          "rsync -lr %s %s" % (remote_checkout_dir, local_checkout_dir)))

  return " ; ".join([str(command) for command in cmds])


def CreateLinuxJob(label, command, lock=False):
  to_return = job.Job(label, command)
  to_return.DependsOnMachine(machine.MachineSpecification("*", "linux", lock))
  return to_return


def GetInitialCommand():
  return cmd.Chain("pwd", "uname -a")


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


def GetToolchainPath(toolchain="trunk"):
  mapping = {"trunk": "",
             "v1": "branches/chromeos_toolchain_v1_release_branch",
             "v2": "branches/mobile_toolchain_v14_release_branch"}

  try:
    gcctools_prefix = mapping[toolchain]
  except KeyError:
    logger.GetLogger().LogFatal("Wrong value for toolchain %s" % toolchain)

  return os.path.join(gcctools_prefix, "gcctools")


def _GetToolchainCheckoutCommand(toolchain_path, p4_snapshot=""):
  p4_port = "perforce2:2666"

  local_path = os.path.join(toolchain_path, "google_vendor_src_branch")
  depot_path = os.path.join(
      DEPOT2_DIR, toolchain_path, "google_vendor_src_branch")

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
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  return cmd.Chain(
      GetInitialCommand(),
      _GetToolchainCheckoutCommand(toolchain_path, p4_snapshot),
      # When g4 syncs this file, often times the timestamp of this file is
      # earlier than that of the file that is its dependency (ldlex.l).
      # Since we mount the filesystem as r/o in the build, we cannot
      # regenerate this file (we also link instead of copy in the 9999
      # ebuild).  Longer-term, we would want to change the fileattr of
      # this file in g4 so it syncs the timestamp as well as the file
      # contents.
      # This is a workaround.
      cmd.Shell("touch", os.path.join(
          toolchain_path, "google_vendor_src_branch", "binutils",
          "binutils-2.20.1-mobile", "ld", "ldlex.c")),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCScript(toolchain_path, board, False, True))


def _GetRunDejaGNUScript(toolchain_path, board):
  return cmd.Shell("run_dejagnu.py",
                   "--testflags=\"\"",
                   "--chromeos_root=%s" % CHROMEOS_ROOT,
                   "--toolchain_root=%s" % toolchain_path,
                   "--remote=$SECONDARY_MACHINES[0]",
                   "--board=%s" % board,
                   path=P4_VERSION_DIR)


def _GetSummarizeResultsScript(logs_path):
  return cmd.Shell("summarize_results.py", logs_path, path=P4_VERSION_DIR)


def GetDejaGNUCommand(chromeos_version="top", board="x86-generic",
                      p4_snapshot="", toolchain="trunk"):
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))
  dejagnu_logs = os.path.join(toolchain_path, "output/dejagnu")

  return cmd.Chain(
      GetInitialCommand(),
      _GetToolchainCheckoutCommand(toolchain_path),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCScript(toolchain_path, board),
      _GetRunDejaGNUScript(toolchain_path, board),
      _GetSummarizeResultsScript(os.path.join(dejagnu_logs, "gcc.log")),
      _GetSummarizeResultsScript(os.path.join(dejagnu_logs, "g++.log")))


def _GetRunTestsScript(board, *tests):
  return cmd.Shell("run_tests.py",
                   "--remote=$SECONDARY_MACHINES[0]",
                   "--chromeos_root=%s" % CHROMEOS_ROOT,
                   "--board=%s" % board,
                   *tests,
                   path=P4_VERSION_DIR)


def GetBuildAndTestChromeOSCommand(chromeos_version="latest",
                                   board="x86-generic", p4_snapshot="",
                                   toolchain="trunk", tests=None):
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  test_list = tests or []
  test_list.insert(0, "bvt")

  return cmd.Chain(
      GetInitialCommand(),
      # TODO(asharif): Get rid of this hack at some point.
      cmd.Shell("mkdir", "-p", os.path.join(
          P4_CHECKOUT_DIR, "gcctools/google_vendor_src_branch/gcc")),
      GetP4VersionDirCommand(p4_snapshot),
      _GetSetupChromeOSCommand(chromeos_version),
      _GetBuildTCScript(toolchain_path, board),
      _GetBuildChromeOSScript(board),
      _GetImageChromeOSScript(board),
      _GetRunTestsScript(*test_list),
      _GetSummarizeResultsScript(
          os.path.join(P4_VERSION_DIR, "logs", "run_tests.py.out")))


def _GetImageChromeOSScript(board):
  return cmd.Shell("image_chromeos.py",
                   "--chromeos_root=%s" % CHROMEOS_ROOT,
                   "--remote=$SECONDARY_MACHINES[0]",
                   "--board=%s" % board,
                   path=P4_VERSION_DIR)


def _GetSetupChromeOSScript(version="latest", use_minilayout=False):
  setup_chromeos = cmd.Shell("setup_chromeos.py",
                             "--dir=%s" % CHROMEOS_ROOT,
                             "--version=%s" % version,
                             path=P4_VERSION_DIR)

  if use_minilayout:
    setup_chromeos.AddOption("--minilayout")

  return setup_chromeos


def _GetBuildChromeOSScript(board, vanilla=False):
  build_chromeos = cmd.Shell("build_chromeos.py",
                             "--chromeos_root=%s" % CHROMEOS_ROOT,
                             "--board=%s" % board,
                             path=P4_VERSION_DIR)

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
    return _GetSetupChromeOSScript(version, use_minilayout)
  elif version.endswith("bz2") or version.endswith("gz"):
    return cmd.Chain(
        cmd.Shell("mkdir", CHROMEOS_ROOT),
        cmd.Shell("tar", "-x", "-f", location_expanded, "-C", CHROMEOS_ROOT))
  else:
    signature_file_location = os.path.join(location,
                                           "src/scripts/enter_chroot.sh")
    logger.GetLogger().LogFatalIf(not os.path.exists(signature_file_location),
                                  "Signature file %s does not exist." %
                                  signature_file_location)
    return cmd.Shell("rsync", "-a", version + "/", "chromeos/")


def _GetBuildTCScript(toolchain_path, board, use_binary=True, rebuild=False):
  build_tc = cmd.Shell("build_tc.py",
                       "--toolchain_root=%s" % toolchain_path,
                       "--chromeos_root=%s" % CHROMEOS_ROOT,
                       "--board=%s" % board,
                       path=P4_VERSION_DIR)

  if use_binary:
    build_tc.AddOption("-B")

  return build_tc


def _GetPerflabBinaryCommand(toolchain_path, board):
  perflab_checkout_path = "/home/mobiletc-prebuild/perflab-checkout"
  perflab_bbrd_bin_path = os.path.join(
      perflab_checkout_path, "google3/blaze-bin/platforms/performance/brrd")
  perflab_bbrd_src_path = os.path.join(
      perflab_checkout_path, "google3/platforms/performance/brrd")

  perflab_binary_path = os.path.join(perflab_bbrd_bin_path, "perflab")
  perflab_interpreter_path = os.path.join(perflab_bbrd_bin_path,
                                          "run_tools/experiment_job_dag")
  perflab_brrd_config_path = os.path.join(perflab_bbrd_src_path,
                                          "perflab/util/perflab.cfg")

  return cmd.Shell(
      "perflab",
      "--perflab_interpreter=%s" % perflab_interpreter_path,
      "--brrd_config=%s" % perflab_brrd_config_path,
      "--alsologtostderr",
      "--noenable_loas_kerberos_checks_at_startup",
      "--stubby_server_host=$(hostname)",
      "--crosstool=%s" % os.path.join("$PWD", toolchain_path),
      "--chromeos_root=%s" % os.path.join("$PWD", CHROMEOS_ROOT),
      "--arch=chromeos_%s" % board,
      "--workdir=$(readlink -f %s)" % P4_VERSION_DIR,
      path=perflab_binary_path)


def GetPerflabCommand(chromeos_version, benchmark, board="x86-agz",
                      p4_snapshot="", toolchain="trunk"):
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  perflab_command = str(_GetPerflabBinaryCommand(toolchain_path, board))
  perflab_output_dir = "perflab-output"

  # TODO(asharif): Compare this to a golden baseline dir.
  return cmd.Chain(
      GetInitialCommand(),
      GetP4VersionDirCommand(p4_snapshot),
      GetP4BenchmarksDirCommand(p4_snapshot),
      _GetSetupChromeOSScript(chromeos_version),
      _GetBuildTCScript(toolchain_path, board),
      cmd.Shell(perflab_command, "build", benchmark),
      cmd.Shell(perflab_command, "run", benchmark),
      cmd.Shell("mkdir", "-p", "results"),
      cmd.Shell("rsync", "-a",
                os.path.join(P4_VERSION_DIR, perflab_output_dir, ""),
                os.path.join("results", perflab_output_dir, "")))


def GetUpdateCommand(chromeos_versions, create_image=True, p4_snapshot="",
                     boards="x86-generic"):
  cmds = cmd.Chain(GetInitialCommand(),
                   GetP4VersionDirCommand(p4_snapshot),
                   _GetSetupChromeOSScript())

  board_list = boards.split(",")

  for board in board_list:
    cmds.append(_GetBuildChromeOSScript(board, True))

  dirname = "$(cd chromeos/src/scripts; git describe --tags --always HEAD)"

  build_location = os.path.join(CHROMEOS_BUILDS_DIR, dirname)

  for board in board_list:
    build_dir = os.path.join(build_location, board, "")
    source_dir = os.path.join("chromeos/src/build/images", board, "")

    cmds.extend([cmd.Shell("mkdir", "-p", build_dir),
                 cmd.Shell("rsync", "-a", source_dir, build_dir)])

  for chromeos_version in chromeos_versions.split(","):
    build_link = os.path.join(CHROMEOS_BUILDS_DIR, chromeos_version)

    cmds.append(cmd.Shell("ln", "-f", "-s", "-T", dirname, build_link))

  return cmds
