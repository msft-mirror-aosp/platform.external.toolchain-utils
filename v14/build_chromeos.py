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
from utils import command_executer
from utils import logger
from utils import utils


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)

#TODO(raymes): move this to a common utils file.
def ExecuteCommandInChroot(chromeos_root, toolchain_root, command,
                           return_output=False, full_mount=False):
  """Executes a command in the chroot."""
  global cmd_executer
  cmd_executer = command_executer.GetCommandExecuter()
  chromeos_root = os.path.expanduser(chromeos_root)

  if toolchain_root is None:
    cmd_file = "enter_chroot.cmd"
    cmd_file_path = chromeos_root + "/src/scripts/" + cmd_file
    f = open(cmd_file_path, "w")
    f.write(command)
    logger.GetLogger().LogCmd(command)
    f.close()
    retval = cmd_executer.RunCommand("chmod +x " + cmd_file_path)
    utils.AssertTrue(retval == 0, "chmod +x failed!")
    return cmd_executer.RunCommand(chromeos_root +
                                   "/src/scripts/enter_chroot.sh -- ./%s"
                                      % cmd_file)
  else:
    toolchain_root = os.path.expanduser(toolchain_root)
    argv = [os.path.dirname(os.path.abspath(__file__)) + "/tc_enter_chroot.py",
            "--chromeos_root=" + chromeos_root,
            "--toolchain_root=" + toolchain_root,
            "\n" + command]
    if not full_mount:
      argv.append("-s")
    return tc_enter_chroot.Main(argv, return_output)


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
    ret = command_executer.GetCommandExecuter().RunCommands(commands)
    utils.AssertTrue(ret == 0, "make_chroot failed")
  else:
    logger.GetLogger().LogOutput("Did not make_chroot because it already exists")


def Main(argv):
  """Build ChromeOS."""
  # Common initializations
  cmd_executer = command_executer.GetCommandExecuter()

  parser = optparse.OptionParser()
  parser.add_option("--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--clobber_chroot", dest="clobber_chroot",
                    action="store_true", help=
                    "Delete the chroot and start fresh", default=False)
  parser.add_option("--clobber_board", dest="clobber_board",
                    action="store_true",
                    help="Delete the board and start fresh", default=False)
  parser.add_option("--cflags", dest="cflags", default="",
                    help="CFLAGS for the ChromeOS packages")
  parser.add_option("--cxxflags", dest="cxxflags", default="",
                    help="CXXFLAGS for the ChromeOS packages")
  parser.add_option("--ldflags", dest="ldflags", default="",
                    help="LDFLAGS for the ChromeOS packages")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")
  parser.add_option("--vanilla", dest="vanilla",
                    default=False,
                    action="store_true",
                    help="Use default ChromeOS toolchain.")

  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  MakeChroot(options.chromeos_root, options.clobber_chroot)

  if options.vanilla == True:
    command = "./setup_board --nousepkg --board=" + options.board
    command += "&& ./build_packages --nousepkg --board=" + options.board
    command += "&& ./build_image --board=" + options.board
    command += "&& ./mod_image_for_test.sh --yes --board=" + options.board
    ret = ExecuteCommandInChroot(options.chromeos_root, None, command)
    return ret

  # Setup board
  if not os.path.isdir(options.chromeos_root + "/chroot/build/"
                       + options.board) or options.clobber_board:
    force = ""
    if options.clobber_board:
      force = "--force"
    # Run build_tc.py from binary package
    rootdir = utils.GetRoot(argv[0])[0]
    version_number = utils.GetRoot(rootdir)[1]
    ret = ExecuteCommandInChroot(options.chromeos_root, None,
                                 "./setup_board --board=%s "
                                 " --gcc_version=9999 "
                                 " --binutils_version=9999 "
                                 "%s" % (options.board, force))
    utils.AssertTrue(ret == 0, "setup_board failed")
  else:
    logger.GetLogger().LogOutput("Did not setup_board "
                                 "because it already exists")

  # Build packages
  ret = ExecuteCommandInChroot(options.chromeos_root, None,
                               "CFLAGS=\"$(portageq-%s envvar CFLAGS) %s\" "
                               "LDFLAGS=\"$(portageq-%s envvar LDFLAGS) %s\" "
                               "CXXFLAGS=\"$(portageq-%s envvar CXXFLAGS) %s\" "
                               "CHROME_ORIGIN=SERVER_SOURCE "
                               "./build_packages --withdev --nousepkg "
                               "--board=%s --withtest --withautotest"
                               % (options.board, options.cflags, options.board,
                                  options.ldflags, options.board,
                                  options.cxxflags, options.board))

  utils.AssertTrue(ret == 0, "build_packages failed")

  # Build image
  ret = ExecuteCommandInChroot(options.chromeos_root, None,
                               "./build_image --yes --board=%s" % options.board)

  utils.AssertTrue(ret == 0, "build_image failed")

  # Mod image for test
  ret = ExecuteCommandInChroot(options.chromeos_root, None,
                               "./mod_image_for_test.sh --yes --board=%s"
                               % options.board)

  utils.AssertTrue(ret == 0, "mod_image_for_test failed")

if __name__ == "__main__":
  Main(sys.argv)
