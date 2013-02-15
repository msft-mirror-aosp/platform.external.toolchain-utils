#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to checkout the ChromeOS source.

This script sets up the ChromeOS source in the given directory, matching a
particular release of ChromeOS.
"""

__author__ = "raymes@google.com (Raymes Khoury)"

import optparse
import os
import sys
from utils import utils


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def ExecuteCommandInChroot(chromeos_root, toolchain_root, command,
                           return_output=False):
  commands = []
  tc_enter_chroot = (os.path.dirname(os.path.abspath(__file__)) +
                     "/tc-enter-chroot.sh")
  commands.append("%s --chromeos_root=%s --toolchain_root=%s -- %s"
                  % (tc_enter_chroot, chromeos_root, toolchain_root, command))
  return utils.RunCommands(commands, return_output)


def StoreFile(filename, contents):
  utils.RunCommand("echo '%s' > %s" % (contents, filename))


def Main():
  """Build ChromeOS."""
  # Common initializations
  (rootdir, basename) = utils.GetRoot(sys.argv[0])
  utils.InitLogger(rootdir, basename)

  parser = optparse.OptionParser()
  parser.add_option("--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("--clobber_chroot", dest="clobber_chroot",
                    action="store_true", help=
                    "Delete the chroot and start fresh", default=False)
  parser.add_option("--clobber_board", dest="clobber_board",
                    action="store_true",
                    help="Delete the board and start fresh", default=False)
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

  if options.toolchain_root is None:
    Usage(parser, "--toolchain_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  # Make chroot
  commands = []
  commands.append("cd " + options.chromeos_root + "/src/scripts")
  clobber_chroot = ""
  if options.clobber_chroot:
    clobber_chroot = "--replace"
  commands.append("./make_chroot --fast " + clobber_chroot)
  utils.RunCommands(commands)

  # Setup board
  force = ""
  if options.clobber_board:
    force = "--force"
  ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                         "FEATURES=\\\"keepwork noclean\\\" "
                         "./setup_board --nousepkg --board=%s "
                         "%s"
                         % (options.board, force))

  # Find Chrome browser version
  chrome_version = (ExecuteCommandInChroot
                    (options.chromeos_root, options.toolchain_root,
                     "./chromeos_version.sh | "
                     "grep CHROME_BUILD", True))

  chrome_version = chrome_version[1].strip().split("=")
  if len(chrome_version) == 2:
    chrome_version = chrome_version[1]
  else:
    chrome_version = ""

  # Modify make.conf to add CFLAGS/CXXFLAGS/LDFLAGS
  ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                         "mv /build/%s/etc/make.conf "
                         "/build/%s/etc/make.conf.orig"
                         % (options.board, options.board))
  makeconf = ("source /build/%s/etc/make.conf.orig\n"
              "/CFLAGS=%s\nCXXFLAGS=%s\nLDFLAGS=%s\n" %
              (options.board, options.cflags,
               options.cxxflags, options.ldflags))
  StoreFile("%s/chroot/build/%s/etc/make.conf" %
            (options.chromeos_root, options.board), makeconf)

  # Build packages
  ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                         "CHROME_ORIGIN=SERVER_SOURCE CHROME_BUILD=%s "
                         "./build_packages --withdev "
                         "--board=%s --withtest --withautotest"
                         % (chrome_version, options.board))

  # Build image
  ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                         "./build_image --board=%s")

  # Mod image for test
  ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                         "./mod_image_for_test --board=%s")


if __name__ == "__main__":
  Main()
