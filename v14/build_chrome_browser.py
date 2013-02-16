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
import shutil
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


def Main(argv):
  """Build Chrome browser."""
  # Common initializations
  global cmd_executer
  cmd_executer = command_executer.GetCommandExecuter()

  parser = optparse.OptionParser()
  parser.add_option("--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("--version", dest="version")
  parser.add_option("--clean",
                    dest="clean",
                    default=False,
                    action="store_true",
                    help="Clean the /var/cache/chromeos-chrome/chrome-src/src/out_$board dir")
  parser.add_option("--env",
                    dest="env",
                    default="",
                    help="Use the following env")
  parser.add_option("--cflags", dest="cflags",
                    default="",
                    help="CFLAGS for the ChromeOS packages")
  parser.add_option("--cxxflags", dest="cxxflags",
                    default="",
                    help="CXXFLAGS for the ChromeOS packages")
  parser.add_option("--ldflags", dest="ldflags",
                    default="",
                    help="LDFLAGS for the ChromeOS packages")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")
  parser.add_option("--label", dest="label",
                    help="Optional label to apply to the ChromeOS image.")

  options = parser.parse_args(argv)[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  if options.version is None:
    logger.GetLogger().LogOutput("No Chrome version given so "
                                 "using the default checked in version.")
    chrome_version = ""
  else:
    chrome_version = "CHROME_VERSION=%s" % options.version

  if options.clean:
    out_dir = os.path.join(options.chromeos_root,
                           "chroot",
                           "var/cache/chromeos-chrome/chrome-src/src/out_%s"
                           % options.board)
    if os.path.exists(out_dir):
      shutil.rmtree(out_dir)

  # Emerge the browser
  ret = (cmd_executer.
         ChrootRunCommand(options.chromeos_root,
                          "CHROME_ORIGIN=SERVER_SOURCE %s "
                          "CFLAGS=\"$(portageq-%s envvar CFLAGS) %s\" "
                          "LDFLAGS=\"$(portageq-%s envvar LDFLAGS) %s\" "
                          "CXXFLAGS=\"$(portageq-%s envvar CXXFLAGS) %s\" "
                          "%s "
                          "emerge-%s --buildpkg chromeos-chrome" %
                          (chrome_version, options.board, options.cflags,
                           options.board, options.ldflags, options.board,
                           options.cxxflags, options.env, options.board)))

  logger.GetLogger().LogFatalIf(ret, "build_packages failed")

  # Build image
  ret = (cmd_executer.
         ChrootRunCommand(options.chromeos_root,
                          utils.GetBuildImageCommand(options.board)))

  logger.GetLogger().LogFatalIf(ret, "build_image failed")

  # Mod image for test
  ret = (cmd_executer.
         ChrootRunCommand(options.chromeos_root,
                          utils.GetModImageForTestCommand(options.board)))

  logger.GetLogger().LogFatalIf(ret, "mod_image_for_test failed")

  flags_file_name = "chrome_flags.txt"
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
