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
import tc_enter_chroot
from utils import utils


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def ExecuteCommandInChroot(chromeos_root, toolchain_root, command,
                           return_output=False, chrome_root=""):
  """Executes a command in the chroot."""
  chrome_mount = ""
  if chrome_root:
    chrome_mount = "--chrome_root=" + chromeos_root + "/" + chrome_root
  argv=[os.path.dirname(os.path.abspath(__file__)) + "/tc_enter_chroot.py",
        "--chromeos_root=" + chromeos_root,
        "--toolchain_root=" + toolchain_root,
        chrome_mount,
        "--",
        command]
  return tc_enter_chroot.Main(argv)


def MakeChroot(chromeos_root, clobber_chroot=False):
  """Make a chroot given a chromeos checkout."""
  if (not os.path.isdir(chromeos_root + "/chroot")
      or clobber_chroot):
    commands = []
    commands.append("cd " + chromeos_root + "/src/scripts")
    clobber_chroot = ""
    if clobber_chroot:
      clobber_chroot = "--replace"
    commands.append("./make_chroot --fast " + clobber_chroot)
    ret = utils.RunCommands(commands)
    utils.AssertTrue(ret == 0, "make_chroot failed")
  else:
    utils.main_logger.LogOutput("Did not make_chroot because it already exists")


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

  MakeChroot(options.chromeos_root, options.clobber_chroot)

  # Setup board
  if not os.path.isdir(options.chromeos_root + "/chroot/build/"
                       + options.board) or options.clobber_board:
    force = ""
    if options.clobber_board:
      force = "--force"
    # Run build_tc.py from binary package
    ret = utils.RunCommand("./build_tc.py --chromeos_root=%s "
                           "--toolchain_root=%s --board=%s -B"
                           % (options.chromeos_root, options.toolchain_root,
                              options.board))
    utils.AssertTrue(ret == 0, "build_tc.py failed")
    version_number = utils.GetRoot(rootdir)[1]
    pkgdir = "/home/${USER}/toolchain_root/" + version_number + "/pkgs"
    ret = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                 "PKGDIR=%s ./setup_board --board=%s "
                                 " --gcc_version=9999 "
                                 "%s" % (pkgdir, options.board, force))
    utils.AssertTrue(ret == 0, "setup_board failed")
  else:
    utils.main_logger.LogOutput("Did not setup_board because it already exists")

  # Modify make.conf to add CFLAGS/CXXFLAGS/LDFLAGS
  ret1 = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "[ -e /build/%s/etc/make.conf.orig ] || "
                                "sudo mv /build/%s/etc/make.conf "
                                "/build/%s/etc/make.conf.orig"
                                % (options.board, options.board, options.board))
  makeconf = ("source make.conf.orig\\\n")
              #"CFLAGS='%s'\\\nCXXFLAGS='%s'\\\nLDFLAGS='%s'\\\n" %
              #(options.cflags, options.cxxflags, options.ldflags))
  ret2 = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                "if [ -e /build/%s/etc/make.conf.orig ] ; then "
                                "sudo echo -e \\\"%s\\\" | sudo tee "
                                "/build/%s/etc/make.conf > /dev/null ;"
                                "else exit 1 ; fi"
                                % (options.board, makeconf, options.board))

  utils.AssertTrue(ret1 == 0 and ret2 == 0, "Could not modify make.conf")

  # Find Chrome browser version
  chrome_version = utils.RunCommand("%s/src/scripts/chromeos_version.sh | "
                                    "grep CHROME_BUILD"
                                    % options.chromeos_root, True)

  ret = chrome_version[0]
  utils.AssertTrue(ret == 0, "Could not determine Chrome browser version")

  chrome_version = chrome_version[1].strip().split("=")
  if len(chrome_version) == 2:
    chrome_version = chrome_version[1]
  else:
    chrome_version = ""

  # Build packages
  ret = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                               "CHROME_ORIGIN=SERVER_SOURCE CHROME_VERSION=%s "
                               "./build_packages --withdev "
                               "--board=%s --withtest --withautotest"
                               % (chrome_version, options.board),
                               chrome_root="chrome_browser")

  utils.AssertTrue(ret == 0, "build_packages failed")

  # Build image
  ret = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                               "./build_image --board=%s" % options.board)

  utils.AssertTrue(ret == 0, "build_image failed")

  # Mod image for test
  ret = ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                               "./mod_image_for_test.sh --board=%s"
                               % options.board)

  utils.AssertTrue(ret == 0, "mod_image_for_test failed")

if __name__ == "__main__":
  Main()
