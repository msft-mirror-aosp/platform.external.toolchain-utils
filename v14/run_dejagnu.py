#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""This script runs the DejaGNU test suite in the ChromeOS chroot environment.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import optparse
import os
import sys
import build_chromeos
from utils import command_executer
from utils import utils
from utils import logger


DEJAGNU_DIR = "/tmp/dejagnu"


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def Main(argv):
  # Common initializations

  parser = optparse.OptionParser()
  parser.add_option("--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("--board", dest="board", default="x86-generic",
                    help="board is the argument to the setup_board command.")
  parser.add_option("--remote", dest="remote",
                    help="The IP address of the machine to run the tests on")
  parser.add_option("--testflags", dest="testflags", default="",
                    help="Arguments to pass to DejaGNU.")
  parser.add_option("--vanilla", dest="vanilla", default=False,
                    action="store_true",
                    help="Use the toolchain inside the chroot to run tests.")

  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.toolchain_root is None and options.vanilla == False:
    Usage(parser, "--toolchain_root or --vanilla must be set")

  if options.toolchain_root is not None and options.vanilla == True:
    Usage(parser, "If --vanilla specified, cannot use --toolchain_root")

  if options.remote is None:
    Usage(parser, "--remote must be set")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  if os.path.exists(options.chromeos_root) == False:
    logger.GetLogger().LogOutput("chroot not found. Creating one.")
    ret = build_chromeos.MakeChroot(options.chromeos_root)
    utils.AssertExit(ret == 0, "Failed to make chroot!")

  # Emerge DejaGNU
  # Remove the dev-tcltk manifest which is currently incorrect
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "rm -f ~/trunk/src/third_party/portage/"
                                "dev-tcltk/expect/Manifest"))
  utils.AssertExit(ret == 0, "Failed to remove incorrect manifest")

  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "sudo emerge -u dejagnu"))
  utils.AssertExit(ret == 0, "Failed to emerge dejagnu")

  # Find the toolchain objects directory
  f = open(options.chromeos_root + "/src/overlays/overlay-" +
           options.board.split("_")[0] + "/toolchain.conf", "r")
  target = f.read()
  f.close()
  target = target.strip()
  if options.vanilla:
    gcc_build_dir = "/var/tmp/portage/cross-%s/gcc-*/work/build" % target
  else:
    gcc_build_dir = ("/usr/local/toolchain_root/output/objects"
                     "/portage/cross-%s/gcc-9999/work/build"
                     % target)

  # Copy the dejagnu site.exp into the chroot.
  ce = command_executer.GetCommandExecuter()
  ce.CopyFiles(utils.GetRoot(sys.argv[0])[0] + "/dejagnu",
               options.chromeos_root + "/chroot/" + DEJAGNU_DIR, recursive=True)

  # Construct the command to run DejaGNU.
  dejagnu_run = ("DEJAGNU=%s/site.exp DEJAGNU_HOSTNAME=%s make "
                 "RUNTESTFLAGS='%s' check-gcc"
                 % (DEJAGNU_DIR, options.remote, options.testflags))

  # Construct command to init the ssh tcp connection 
  init = GetRemoteAccessInitCommand(options.remote)

  # Construct the command to cleanup the ssh tcp connection
  cleanup = GetRemoteAccessCleanupCommand()

  common = GetRemoteAccessCommonCommands(options.remote)

  # Run DejaGNU
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "%s ; %s ; %s && cd %s && %s ; %s" %
                                (common, cleanup, init, gcc_build_dir,
                                 dejagnu_run, cleanup), full_mount=True))
  utils.AssertWarning(ret == 0, "Failed to run DejaGNU tests successfully")

  # Copy results to a not-so-deep location
  results_dir = "%s/gcc/testsuite/" % gcc_build_dir
  new_results_dir = "/usr/local/toolchain_root/output/dejagnu/"
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "mkdir -p %s ; cp %s/g++/g++.log %s ; "
                                "cp %s/gcc/gcc.log %s" %
                                (new_results_dir, results_dir, new_results_dir,
                                 results_dir, new_results_dir)))

  utils.AssertWarning(ret == 0, "Failed to copy results to final destination.")


def GetRemoteAccessCommonCommands(remote):
    command = "\nset -- --remote=" + remote
    command += "\n. ~/trunk/src/scripts/common.sh"
    command += "\n. ~/trunk/src/scripts/remote_access.sh"
    command += "\nTMP=/tmp/chromeos-toolchain"
    command += "\nFLAGS \"$@\" || exit 1"
    return command

def GetRemoteAccessInitCommand(remote):
  command = ("echo \"Initting access\""
             " && mkdir -p ${TMP}"
             " && remote_access_init"
             " && ( ssh -t -t -p 22 root@%s"
             " -o StrictHostKeyChecking=no"
             " -o UserKnownHostsFile=/tmp/chromeos-toolchain/known_hosts"
             " -i ${TMP}/private_key"
             " -M -S ${TMP}/%%r@%%h:%%p 2>&1 > /dev/null & )"
             " ; echo $! > ${TMP}/master-pid" % remote)
  return command

def GetRemoteAccessCleanupCommand():
  command = ("echo \"Cleaning up access\""
             " && set +e "
             " && kill $(cat ${TMP}/master-pid)"
             " && set -e"
             " && cleanup_remote_access"
             " && rm -rf ${TMP}")
  return command


if __name__ == "__main__":
  Main(sys.argv)
