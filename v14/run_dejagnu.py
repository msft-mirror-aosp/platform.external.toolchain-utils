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
from utils import utils

DEJAGNU_DIR = "/usr/local/toolchain_root/v14/dejagnu"


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

  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.toolchain_root is None:
    Usage(parser, "--toolchain_root must be set")

  if options.remote is None:
    Usage(parser, "--remote must be set")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

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
  gcc_build_dir = ("/usr/local/toolchain_root/v14/output/objects/cross/"
                   "%s/portage/cross-%s/gcc-9999/work/build/gcc"
                   % (target, target))

  # Construct the command to run DejaGNU.
  dejagnu_run = ("DEJAGNU=%s/site.exp DEJAGNU_HOSTNAME=%s make "
                 "RUNTESTFLAGS='%s' check-gcc"
                 % (DEJAGNU_DIR, options.remote, options.testflags))

  # Construct command to init the ssh tcp connection 
  init = "%s/remote_init.sh --init --remote=%s" % (DEJAGNU_DIR, options.remote)

  # Construct the command to cleanup the ssh tcp connection
  cleanup = ("%s/remote_init.sh --cleanup --remote=%s" %
             (DEJAGNU_DIR, options.remote))

  # Run DejaGNU
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "%s ; %s && cd %s && %s ; %s" %
                                (cleanup, init, gcc_build_dir, dejagnu_run, cleanup),
                                full_mount=True))
  utils.AssertWarning(ret == 0, "Failed to run DejaGNU tests successfully")



if __name__ == "__main__":
  Main(sys.argv)
