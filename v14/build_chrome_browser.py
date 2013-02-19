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

import build_chromeos
from utils import command_executer
from utils import logger
from utils import misc

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
                    help=("Clean the /var/cache/chromeos-chrome/"
                          "chrome-src/src/out_$board dir"))
  parser.add_option("--env",
                    dest="env",
                    default="",
                    help="Use the following env")
  parser.add_option("--ebuild_version",
                    dest="ebuild_version",
                    help="Use this ebuild instead of the default one.")
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
  parser.add_option("--build_image_args",
                    default="",
                    dest="build_image_args",
                    help="Optional arguments to build_image.")
  parser.add_option("--cros_workon", dest="cros_workon",
                    help="Build using external source tree.")

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

  options.chromeos_root = misc.CanonicalizePath(options.chromeos_root)

  unmask_env = "ACCEPT_KEYWORDS=~*"
  if options.ebuild_version:
    ebuild_version = "=%s" % options.ebuild_version
    options.env = "%s %s" % (options.env, unmask_env)
  else:
    ebuild_version = "chromeos-chrome"

  if options.cros_workon and not (
    os.path.isdir(options.cros_workon) and os.path.exists(
      os.path.join(options.cros_workon, "src/chromeos/chromeos.gyp"))):
    Usage(parser, "--cros_workon must be a valid chromium browser checkout.")

  options.env = misc.MergeEnvStringWithDict(options.env,
                                            {"USE": "chrome_internal"})
  if options.clean:
    misc.RemoveChromeBrowserObjectFiles(options.chromeos_root, options.board)

  chrome_origin="SERVER_SOURCE"
  if options.cros_workon:
    chrome_origin="LOCAL_SOURCE"
    command = 'cros_workon --board={0} start chromeos-chrome'.format(
      options.board)
    ret = cmd_executer.ChrootRunCommand(
      options.chromeos_root, command, return_output=True)

    # cros_workon start returns non-zero if chromeos-chrome is already a
    # cros_workon package.
    if ret[0] and ret[2].find(
      "WARNING : Already working on chromeos-base/chromeos-chrome") == -1:
      logger.GetLogger().LogFatal("cros_workon chromeos-chrome failed.")

    # Return value is non-zero means we do find the "Already working on..."
    # message, keep the information, so later on we do not revert the
    # cros_workon status.
    cros_workon_keep = (ret[0] != 0)

  # Emerge the browser
  emerge_browser_command = \
      ("CHROME_ORIGIN={0} {1} "
       "CFLAGS=\"$(portageq-{2} envvar CFLAGS) {3}\" "
       "LDFLAGS=\"$(portageq-{2} envvar LDFLAGS) {4}\" "
       "CXXFLAGS=\"$(portageq-{2} envvar CXXFLAGS) {5}\" "
       "{6} emerge-{2} --buildpkg {7}").format(
        chrome_origin, chrome_version, options.board, options.cflags,
        options.ldflags, options.cxxflags, options.env, ebuild_version)

  cros_sdk_options = ''
  if options.cros_workon:
    cros_sdk_options='--chrome_root={0}'.format(options.cros_workon)

  ret = cmd_executer.ChrootRunCommand(options.chromeos_root,
                                      emerge_browser_command,
                                      cros_sdk_options=cros_sdk_options)

  logger.GetLogger().LogFatalIf(ret, "build_packages failed")

  if options.cros_workon and not cros_workon_keep:
    command = 'cros_workon --board={0} stop chromeos-chrome'.format(
      options.board)
    ret = cmd_executer.ChrootRunCommand(options.chromeos_root, command)
    # cros_workon failed, not a fatal one, just report it.
    if ret:
      print "cros_workon stop chromeos-chrome failed."

  # Build image
  ret = (cmd_executer.
         ChrootRunCommand(options.chromeos_root,
                          ("%s %s %s %s" %
                           (unmask_env,
                            options.env,
                            misc.GetBuildImageCommand(options.board),
                            options.build_image_args))))

  logger.GetLogger().LogFatalIf(ret, "build_image failed")


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
