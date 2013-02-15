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

checksum_file = "/home/chronos/osimage_checksum_file"


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)

def ImageChromeOS(argv):
  """Build ChromeOS."""
  # Common initializations
  cmd_executer = command_executer.GetCommandExecuter()

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("-r", "--remote", dest="remote",
                    help="Target device.")
  parser.add_option("-i", "--image", dest="image",
                    help="Image binary file.")

  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.remote is None:
    Usage(parser, "--remote must be set")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  board = cmd_executer.CrosLearnBoard(options.chromeos_root, options.remote)

  if options.image is None:
    image = (options.chromeos_root +
             "/src/build/images/" + board +
             "/latest/" +
             "/chromiumos_image.bin")
  else:
    image = options.image

  image = os.path.realpath(image)

  if not os.path.exists(image):
    Usage(parser, "Image file: " + image + " does not exist!")

  image_checksum = utils.Md5File(image)

  command = "cat " + checksum_file
  retval, device_checksum, err = cmd_executer.CrosRunCommand(command,
      return_output=True,
      chromeos_root=options.chromeos_root,
      machine=options.remote)

  device_checksum = device_checksum.strip()
  image_checksum = str(image_checksum)

  logger.GetLogger().LogOutput("Image checksum: " + image_checksum)
  logger.GetLogger().LogOutput("Device checksum: " + device_checksum)

  if image_checksum != device_checksum:
    command = (options.chromeos_root +
               "/src/scripts/image_to_live.sh --remote=" +
               options.remote +
               " --image=" + image)

    command = "'echo " + image_checksum + " > " + checksum_file
    command += "&& chmod -w " + checksum_file + "'"
    print command
    cmd_executer.CrosRunCommand(command, chromeos_root=options.chromeos_root,
                                machine=options.remote)
  else:
    logger.GetLogger().LogOutput("Checksums match. Skipping reimage")

  return retval

if __name__ == "__main__":
  ImageChromeOS(sys.argv)
