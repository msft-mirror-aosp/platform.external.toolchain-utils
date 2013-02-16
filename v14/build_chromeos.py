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
from utils import misc


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


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
    logger.GetLogger().LogFatalIf(ret, "make_chroot failed")
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
  parser.add_option("--rebuild", dest="rebuild",
                    action="store_true",
                    help="Rebuild all board packages except the toolchain.",
                    default=False)
  parser.add_option("--cflags", dest="cflags", default="",
                    help="CFLAGS for the ChromeOS packages")
  parser.add_option("--cxxflags", dest="cxxflags", default="",
                    help="CXXFLAGS for the ChromeOS packages")
  parser.add_option("--ldflags", dest="ldflags", default="",
                    help="LDFLAGS for the ChromeOS packages")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")
  parser.add_option("--label", dest="label",
                    help="Optional label symlink to point to build dir.")
  parser.add_option("--vanilla", dest="vanilla",
                    default=False,
                    action="store_true",
                    help="Use default ChromeOS toolchain.")

  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  build_packages_env = ""
  if options.rebuild == True:
    build_packages_env = "EXTRA_BOARD_FLAGS=-e"

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  MakeChroot(options.chromeos_root, options.clobber_chroot)

  build_packages_command = misc.GetBuildPackagesCommand(options.board)
  build_image_command = misc.GetBuildImageCommand(options.board)

  if options.vanilla == True:
    command = misc.GetSetupBoardCommand(options.board,
                                         usepkg=False,
                                         force=options.clobber_board)
    command += "; " + build_packages_env + " " + build_packages_command
    command += "&& " + build_image_command
    ret = cmd_executer.ChrootRunCommand(options.chromeos_root, command)
    return ret

  # Setup board
  if not os.path.isdir(options.chromeos_root + "/chroot/build/"
                       + options.board) or options.clobber_board:
    # Run build_tc.py from binary package
    rootdir = misc.GetRoot(argv[0])[0]
    version_number = misc.GetRoot(rootdir)[1]
    ret = cmd_executer.ChrootRunCommand(
        options.chromeos_root,
        misc.GetSetupBoardCommand(options.board,
                                   gcc_version="9999",
                                   binutils_version="9999",
                                   force=options.clobber_board))
    logger.GetLogger().LogFatalIf(ret, "setup_board failed")
  else:
    logger.GetLogger().LogOutput("Did not setup_board "
                                 "because it already exists")

  # Build packages
  ret = cmd_executer.ChrootRunCommand(
      options.chromeos_root,
      "CFLAGS=\"$(portageq-%s envvar CFLAGS) %s\" "
      "LDFLAGS=\"$(portageq-%s envvar LDFLAGS) %s\" "
      "CXXFLAGS=\"$(portageq-%s envvar CXXFLAGS) %s\" "
      "CHROME_ORIGIN=SERVER_SOURCE "
      "%s "
      "%s"
      % (options.board, options.cflags,
         options.board, options.cxxflags,
         options.board, options.ldflags,
         build_packages_env,
         build_packages_command))

  logger.GetLogger().LogFatalIf(ret, "build_packages failed")

  # Build image
  ret = cmd_executer.ChrootRunCommand(options.chromeos_root,
                                      build_image_command)

  logger.GetLogger().LogFatalIf(ret, "build_image failed")

  flags_file_name = "flags.txt"
  flags_file_path = ("%s/src/build/images/%s/latest/%s" %
                     (options.chromeos_root,
                      options.board,
                      flags_file_name))
  flags_file = open(flags_file_path, "wb")
  flags_file.write("CFLAGS=%s\n" % options.cflags)
  flags_file.write("CXXFLAGS=%s\n" % options.cxxflags)
  flags_file.write("LDFLAGS=%s\n" % options.ldflags)
  flags_file.close()

  if options.label:
    image_dir_path = ("%s/src/build/images/%s/latest" %
                  (options.chromeos_root,
                   options.board))
    real_image_dir_path = os.path.realpath(image_dir_path)
    command = ("ln -sf -T %s %s/%s" %
               (os.path.basename(real_image_dir_path),
                os.path.dirname(real_image_dir_path),
                options.label))

    ret = cmd_executer.RunCommand(command)
    logger.GetLogger().LogFatalIf(ret, "Failed to apply symlink label %s" %
                                  options.label)

  return ret

if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
