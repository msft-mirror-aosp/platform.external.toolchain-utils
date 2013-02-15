#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Script to image a ChromeOS device.

This script images a remote ChromeOS device with a specific image."
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import filecmp
import glob
import optparse
import os
import shutil
import sys
import tempfile
import tc_enter_chroot
from utils import command_executer
from utils import logger
from utils import utils
from utils.file_utils import FileUtils

checksum_file = "/usr/local/osimage_checksum_file"


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)

def Main(argv):
  """Build ChromeOS."""
  # Common initializations
  cmd_executer = command_executer.GetCommandExecuter()
  l = logger.GetLogger()

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("-r", "--remote", dest="remote",
                    help="Target device.")
  parser.add_option("-i", "--image", dest="image",
                    help="Image binary file.")
  parser.add_option("-b", "--board", dest="board",
                    help="Target board override.")
  parser.add_option("-f", "--force", dest="force",
                    action="store_true",
                    default=False,
                    help="Force an image even if it is non-test.")
  parser.add_option("-a",
                    "--image_to_live_args",
                    dest="image_to_live_args")


  options = parser.parse_args(argv[1:])[0]

  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.remote is None:
    Usage(parser, "--remote must be set")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  if options.board is None:
    board = cmd_executer.CrosLearnBoard(options.chromeos_root, options.remote)
  else:
    board = options.board

  if options.image is None:
    image = (options.chromeos_root +
             "/src/build/images/" + board +
             "/latest/" +
             "/chromiumos_image.bin")
  else:
    image = options.image
    image = os.path.expanduser(image)

  image = os.path.realpath(image)

  if not os.path.exists(image):
    Usage(parser, "Image file: " + image + " does not exist!")

  image_checksum = FileUtils().Md5File(image)

  command = "cat " + checksum_file
  retval, device_checksum, err = cmd_executer.CrosRunCommand(command,
      return_output=True,
      chromeos_root=options.chromeos_root,
      machine=options.remote)

  device_checksum = device_checksum.strip()
  image_checksum = str(image_checksum)

  l.LogOutput("Image checksum: " + image_checksum)
  l.LogOutput("Device checksum: " + device_checksum)

  if image_checksum != device_checksum:
    [found, located_image] = LocateOrCopyImage(options.chromeos_root,
                                               image,
                                               board=board)

    l.LogOutput("Checksums do not match. Re-imaging...")

    is_test_image = IsImageModdedForTest(options.chromeos_root,
                                         located_image)

    if not is_test_image and not options.force:
      logger.GetLogger().LogFatal("Have to pass --force to image a non-test "
                                  "image!")

    # If the device has /tmp mounted as noexec, image_to_live.sh can fail.
    command = "mount -o remount,rw,exec /tmp"
    cmd_executer.CrosRunCommand(command,
                                chromeos_root=options.chromeos_root,
                                machine=options.remote)

    command = (options.chromeos_root +
               "/src/scripts/image_to_live.sh --remote=" +
               options.remote +
               " --image=" + located_image)
    if options.image_to_live_args:
      command += " %s" % options.image_to_live_args

    retval = cmd_executer.RunCommand(command)

    if found == False:
      temp_dir = os.path.dirname(located_image)
      l.LogOutput("Deleting temp image dir: %s" % temp_dir)
      shutil.rmtree(temp_dir)

    logger.GetLogger().LogFatalIf(retval, "Image command failed")
    command = "'echo " + image_checksum + " > " + checksum_file
    command += "&& chmod -w " + checksum_file + "'"
    retval = cmd_executer.CrosRunCommand(command,
                                         chromeos_root=options.chromeos_root,
                                         machine=options.remote)
    logger.GetLogger().LogFatalIf(retval, "Writing checksum failed.")

    successfully_imaged = VerifyChromeChecksum(options.chromeos_root,
                                               image,
                                               options.remote)
    logger.GetLogger().LogFatalIf(not successfully_imaged,
                                  "Image verification failed!")
  else:
    l.LogOutput("Checksums match. Skipping reimage")

  return retval


def LocateOrCopyImage(chromeos_root, image, board=None):
  l = logger.GetLogger()
  if board is None:
    board_glob = "*"
  else:
    board_glob = board

  chromeos_root_realpath = os.path.realpath(chromeos_root)
  image = os.path.realpath(image)

  if image.startswith("%s/" % chromeos_root_realpath):
    return [True, image]

  # First search within the existing build dirs for any matching files.
  images_glob = ("%s/src/build/images/%s/*/*.bin" %
                 (chromeos_root_realpath,
                  board_glob))
  images_list = glob.glob(images_glob)
  for potential_image in images_list:
    if filecmp.cmp(potential_image, image):
      l.LogOutput("Found matching image %s in chromeos_root." % potential_image)
      return [True, potential_image]
  # We did not find an image. Copy it in the src dir and return the copied file.
  if board is None:
    board = ""
  base_dir = ("%s/src/build/images/%s" %
              (chromeos_root_realpath,
               board))
  if not os.path.isdir(base_dir):
    os.makedirs(base_dir)
  temp_dir = tempfile.mkdtemp(prefix="%s/tmp" % base_dir)
  new_image = "%s/%s" % (temp_dir, os.path.basename(image))
  l.LogOutput("No matching image found. Copying %s to %s" %
              (image, new_image))
  shutil.copyfile(image, new_image)
  return [False, new_image]


def GetImageMountCommand(chromeos_root, image, rootfs_mp, stateful_mp):
  image_dir = os.path.dirname(image)
  image_file = os.path.basename(image)
  mount_command = ("cd %s/src/scripts &&"
                   "./mount_gpt_image.sh --from=%s --image=%s"
                   " --safe --read_only"
                   " --rootfs_mountpt=%s"
                   " --stateful_mountpt=%s" %
                   (chromeos_root, image_dir, image_file, rootfs_mp,
                    stateful_mp))
  return mount_command


def MountImage(chromeos_root, image, rootfs_mp, stateful_mp, unmount=False):
  cmd_executer = command_executer.GetCommandExecuter()
  command = GetImageMountCommand(chromeos_root, image, rootfs_mp, stateful_mp)
  if unmount:
    command = "%s --unmount" % command
  retval = cmd_executer.RunCommand(command)
  logger.GetLogger().LogFatalIf(retval, "Mount/unmount command failed!")
  return retval


def IsImageModdedForTest(chromeos_root, image):
  rootfs_mp = tempfile.mkdtemp()
  stateful_mp = tempfile.mkdtemp()
  MountImage(chromeos_root, image, rootfs_mp, stateful_mp)
  lsb_release_file = os.path.join(rootfs_mp, "etc/lsb-release")
  is_test_image = "Test Build" in open(lsb_release_file).read()
  MountImage(chromeos_root, image, rootfs_mp, stateful_mp, unmount=True)
  return is_test_image


def VerifyChromeChecksum(chromeos_root, image, remote):
  cmd_executer = command_executer.GetCommandExecuter()
  rootfs_mp = tempfile.mkdtemp()
  stateful_mp = tempfile.mkdtemp()
  MountImage(chromeos_root, image, rootfs_mp, stateful_mp)
  image_chrome_checksum = FileUtils().Md5File("%s/opt/google/chrome/chrome" %
                                              rootfs_mp)
  MountImage(chromeos_root, image, rootfs_mp, stateful_mp, unmount=True)

  command = "md5sum /opt/google/chrome/chrome"
  [r, o, e] = cmd_executer.CrosRunCommand(command,
                                          return_output=True,
                                          chromeos_root=chromeos_root,
                                          machine=remote)
  device_chrome_checksum = o.split()[0]
  if image_chrome_checksum.strip() == device_chrome_checksum.strip():
    return True
  else:
    return False


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
