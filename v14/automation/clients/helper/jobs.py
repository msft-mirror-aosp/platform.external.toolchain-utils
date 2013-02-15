#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import re

from automation.common import command as cmd
from automation.common import job
from automation.common import machine
from utils import logger
from automation.clients.helper import perforce

DEPOT2_DIR = "//depot2/"
P4_CHECKOUT_DIR = "perforce2/"
P4_VERSION_DIR = os.path.join(P4_CHECKOUT_DIR, "gcctools/chromeos/v14")

CHROMEOS_ROOT = "chromeos"
CHROMEOS_SCRIPTS_DIR = os.path.join(CHROMEOS_ROOT, "src/scripts")
CHROMEOS_BUILDS_DIR = "/home/mobiletc-prebuild/www/chromeos_builds"


class ScriptsFactory(object):
  def __init__(self, chromeos_root, scripts_path):
    self._chromeos_root = chromeos_root
    self._scripts_path = scripts_path

  def RunDejaGNU(self, toolchain_path, board):
    return cmd.Shell("run_dejagnu.py",
                     "--testflags=\"\"",
                     "--chromeos_root=%s" % self._chromeos_root,
                     "--toolchain_root=%s" % toolchain_path,
                     "--remote=$SECONDARY_MACHINES[0]",
                     "--board=%s" % board,
                     path=self._scripts_path)

  def SummarizeResults(self, logs_path):
    return cmd.Shell("summarize_results.py",
                     logs_path,
                     path=self._scripts_path)

  def RunTests(self, board, *tests):
    return cmd.Shell("run_tests.py",
                     "--remote=$SECONDARY_MACHINES[0]",
                     "--chromeos_root=%s" % self._chromeos_root,
                     "--board=%s" % board,
                     *tests,
                     path=self._scripts_path)

  def ImageChromeOS(self, board):
    return cmd.Shell("image_chromeos.py",
                     "--chromeos_root=%s" % self._chromeos_root,
                     "--remote=$SECONDARY_MACHINES[0]",
                     "--board=%s" % board,
                     path=self._scripts_path)

  def SetupChromeOS(self, version="latest", use_minilayout=False):
    setup_chromeos = cmd.Shell("setup_chromeos.py",
                               "--dir=%s" % self._chromeos_root,
                               "--version=%s" % version,
                               path=self._scripts_path)
    if use_minilayout:
      setup_chromeos.AddOption("--minilayout")
    return setup_chromeos

  def BuildChromeOS(self, board, vanilla=False):
    build_chromeos = cmd.Shell("build_chromeos.py",
                               "--chromeos_root=%s" % self._chromeos_root,
                               "--board=%s" % board,
                               path=self._scripts_path)
    if vanilla:
      build_chromeos.AddOption("--vanilla")
    return build_chromeos

  def BuildTC(self, toolchain_path, board, use_binary=True, rebuild=False):
    build_tc = cmd.Shell("build_tc.py",
                         "--toolchain_root=%s" % toolchain_path,
                         "--chromeos_root=%s" % self._chromeos_root,
                         "--board=%s" % board,
                         path=self._scripts_path)
    if use_binary:
      build_tc.AddOption("-B")
    return build_tc


def CreateLinuxJob(label, command, lock=False):
  to_return = job.Job(label, command)
  to_return.DependsOnMachine(machine.MachineSpecification("*", "linux", lock))
  return to_return


def GetP4Snapshot(p4view, p4_snapshot=""):
  p4client = perforce.CommandsFactory(P4_CHECKOUT_DIR, p4view)

  if p4_snapshot:
    return p4client.CheckoutFromSnapshot(p4_snapshot)
  else:
    return p4client.SetupAndDo(p4client.Sync(), p4client.Remove())


def CheckoutBuildHelpers(p4_snapshot=""):
  p4view = perforce.View(DEPOT2_DIR, [
      perforce.PathMapping("gcctools/chromeos/v14/...")])
  return GetP4Snapshot(p4view, p4_snapshot)


def CheckoutBenchmarks(p4_snapshot=""):
  p4view = perforce.View(DEPOT2_DIR, [
      perforce.PathMapping("third_party/android_bench/v2_0/...")])
  return GetP4Snapshot(p4view, p4_snapshot)


def GetToolchainPath(toolchain="trunk"):
  mapping = {"trunk": "",
             "v1": "branches/chromeos_toolchain_v1_release_branch",
             "v2": "branches/mobile_toolchain_v14_release_branch"}

  try:
    gcctools_prefix = mapping[toolchain]
  except KeyError:
    logger.GetLogger().LogFatal("Wrong value for toolchain %s" % toolchain)

  return os.path.join(gcctools_prefix, "gcctools")


def CheckoutChromeOSToolchain(toolchain_path, p4_snapshot=""):
  google_vendor_src_branch_path = os.path.join(toolchain_path, "gcctools",
                                               "google_vendor_src_branch")
  p4view = perforce.View(
      DEPOT2_DIR, perforce.PathMapping.ListFromPathDict({
          "gcctools": ["chromeos/v14/..."],
          google_vendor_src_branch_path: [
              "gcc/gcc-4.4.3/...",
              "binutils/binutils-2.20.1-mobile/...",
              "binutils/binutils-20100303/..."]}))

  return GetP4Snapshot(p4view, p4_snapshot)


def MakeSymlink(to_path, link_name):
  return cmd.Shell("ln", "-f", "-s", "-T", to_path, link_name)


def MakeDir(*dirs):
  return cmd.Shell("mkdir", "-p", *dirs)


def SyncDir(from_dir, to_dir):
  return cmd.Shell("rsync", "-a",
                   from_dir.rstrip("/") + "/",
                   to_dir.rstrip("/") + "/")


def UnTar(tar_file, dest_dir):
  return cmd.Chain(
      MakeDir(dest_dir),
      cmd.Shell("tar", "-x", "-f", tar_file, "-C", dest_dir))


def NewChain(*commands):
  return cmd.Chain(
      cmd.Shell("pwd"),
      cmd.Shell("uname", "-a"),
      *commands)


def GetChromeOSRootDir(version, use_minilayout=False):
  version_re = "^\d+\.\d+\.\d+\.[a-zA-Z0-9]+$"

  location = os.path.join(CHROMEOS_BUILDS_DIR, version)

  if version in ["weekly", "quarterly"]:
    logger.GetLogger().LogFatalIf(not os.path.islink(location),
                                  "Symlink %s does not exist." % location)
    location_expanded = os.path.realpath(location)
    version = os.path.basename(location_expanded)

  if version in ["top", "latest"] or re.match(version_re, version):
    scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)
    return scripts.SetupChromeOS(version, use_minilayout)

  elif version.endswith("bz2") or version.endswith("gz"):
    return UnTar(location_expanded, CHROMEOS_ROOT)

  else:
    signature_file_location = os.path.join(location,
                                           "src/scripts/enter_chroot.sh")
    logger.GetLogger().LogFatalIf(not os.path.exists(signature_file_location),
                                  "Signature file %s does not exist." %
                                  signature_file_location)
    return SyncDir(location, CHROMEOS_ROOT)


def GetBuildToolchainCommand(chromeos_version="top", board="x86-generic",
                             p4_snapshot="", toolchain="trunk"):
  scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  return NewChain(
      CheckoutChromeOSToolchain(toolchain_path, p4_snapshot),
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
      GetChromeOSRootDir(chromeos_version),
      scripts.BuildTC(toolchain_path, board, False, True))


def GetDejaGNUCommand(chromeos_version="top", board="x86-generic",
                      p4_snapshot="", toolchain="trunk"):
  scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))
  dejagnu_logs = os.path.join(toolchain_path, "output/dejagnu")

  return NewChain(
      CheckoutChromeOSToolchain(toolchain_path, p4_snapshot),
      GetChromeOSRootDir(chromeos_version),
      scripts.BuildTC(toolchain_path, board),
      scripts.RunDejaGNU(toolchain_path, board),
      scripts.SummarizeResults(os.path.join(dejagnu_logs, "gcc.log")),
      scripts.SummarizeResults(os.path.join(dejagnu_logs, "g++.log")))


def GetBuildAndTestChromeOSCommand(chromeos_version="latest",
                                   board="x86-generic", p4_snapshot="",
                                   toolchain="trunk", tests=None):
  scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  test_list = tests or []
  test_list.insert(0, "bvt")

  return NewChain(
      # TODO(asharif): Get rid of this hack at some point.
      MakeDir(os.path.join(P4_CHECKOUT_DIR,
                           "gcctools/google_vendor_src_branch/gcc")),
      CheckoutBuildHelpers(p4_snapshot),
      GetChromeOSRootDir(chromeos_version),
      scripts.BuildTC(toolchain_path, board),
      scripts.BuildChromeOS(board),
      scripts.ImageChromeOS(board),
      scripts.RunTests(*test_list),
      scripts.SummarizeResults(
          os.path.join(P4_VERSION_DIR, "logs", "run_tests.py.out")))


def GetPerflabBinaryCommand(toolchain_path, board):
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
  scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)
  toolchain_path = os.path.join(P4_CHECKOUT_DIR, GetToolchainPath(toolchain))

  perflab_command = str(GetPerflabBinaryCommand(toolchain_path, board))
  perflab_output_dir = "perflab-output"

  # TODO(asharif): Compare this to a golden baseline dir.
  return NewChain(
      CheckoutBuildHelpers(p4_snapshot),
      CheckoutBenchmarks(p4_snapshot),
      scripts.SetupChromeOS(chromeos_version),
      scripts.BuildTC(toolchain_path, board),
      cmd.Shell(perflab_command, "build", benchmark),
      cmd.Shell(perflab_command, "run", benchmark),
      MakeDir("results"),
      SyncDir(os.path.join(P4_VERSION_DIR, perflab_output_dir),
              os.path.join("results", perflab_output_dir)))


def GetUpdateCommand(chromeos_versions, create_image=True, p4_snapshot="",
                     boards="x86-generic"):
  scripts = ScriptsFactory(CHROMEOS_ROOT, P4_VERSION_DIR)

  cmds = NewChain(CheckoutBuildHelpers(p4_snapshot),
                  scripts.SetupChromeOS())

  board_list = boards.split(",")

  for board in board_list:
    cmds.append(scripts.BuildChromeOS(board, True))

  dirname = "$(cd chromeos/src/scripts; git describe --tags --always HEAD)"

  build_location = os.path.join(CHROMEOS_BUILDS_DIR, dirname)

  for board in board_list:
    build_dir = os.path.join(build_location, board)
    source_dir = os.path.join("chromeos/src/build/images", board)

    cmds.extend([MakeDir(build_dir), SyncDir(source_dir, build_dir)])

  for chromeos_version in chromeos_versions.split(","):
    build_link = os.path.join(CHROMEOS_BUILDS_DIR, chromeos_version)

    cmds.append(MakeSymlink(dirname, build_link))

  return cmds
