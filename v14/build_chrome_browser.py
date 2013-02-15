#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to checkout the ChromeOS source.

This script sets up the ChromeOS source in the given directory, matching a
particular release of ChromeOS.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import optparse
import sys
from utils import command_executer
from utils import logger
from utils import utils
import build_chromeos

cmd_executer = None


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def Main():
  """Build Chrome browser."""
  # Common initializations
  global cmd_executer
  cmd_executer = command_executer.GetCommandExecuter()

  parser = optparse.OptionParser()
  parser.add_option("--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("--version", dest="version")
  parser.add_option("--cflags", dest="cflags",
                    help="CFLAGS for the ChromeOS packages")
  parser.add_option("--cxxflags", dest="cxxflags",
                    help="CXXFLAGS for the ChromeOS packages")
  parser.add_option("--ldflags", dest="ldflags",
                    help="LDFLAGS for the ChromeOS packages")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")

  options = parser.parse_args()[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

    if options.toolchain_root is not None:
      logger.GetLogger().LogOutput("Installing the toolchain.")
      rootdir = rootdir = utils.GetRoot(sys.argv[0])[0]
      ret = cmd_executer.RunCommand(rootdir + "/build_tc.py --chromeos_root=%s "
                                    "--toolchain_root=%s --board=%s -B"
                                    % (options.chromeos_root,
                                       options.toolchain_root, options.board))
      utils.AssertTrue(ret == 0, "build_tc.py failed")
    else:
      logger.GetLogger().LogOutput("--toolchain_root not given, "
                                   "so just using the existing toolchain")

  if options.version is None:
    logger.GetLogger().LogOutput("No Chrome version given so "
                                 "using the default checked in version.")
    chrome_version = ""
  else:
    chrome_version = "CHROME_VERSION=%s" % options.version

  # Emerge the browser
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "CHROME_ORIGIN=SERVER_SOURCE %s "
                                "CFLAGS=\"$(portageq-%s envvar CFLAGS) %s\" "
                                "LDFLAGS=\"$(portageq-%s envvar LDFLAGS) %s\" "
                                "CXXFLAGS=\"$(portageq-%s envvar CXXFLAGS) %s\" "
                                "emerge-%s chromeos-chrome" %
                                (chrome_version, options.board, options.cflags,
                                 options.board, options.ldflags, options.board,
                                 options.cxxflags, options.board)))

  utils.AssertTrue(ret == 0, "build_packages failed")

  # Build image
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "./build_image --yes --board=%s" % options.board))

  utils.AssertTrue(ret == 0, "build_image failed")

  # Mod image for test
  ret = (build_chromeos.
         ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "./mod_image_for_test.sh --board=%s"
                                % options.board))

  utils.AssertTrue(ret == 0, "mod_image_for_test failed")

if __name__ == "__main__":
  Main()
