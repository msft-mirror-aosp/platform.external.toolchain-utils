#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to enter the ChromeOS chroot with mounted sources.

This script enters the chroot with mounted sources.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import os
import sys
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="ChromeOS root checkout directory.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="Toolchain root directory.")

  (options, args) = parser.parse_args(argv)

  if options.chromeos_root is None:
    chromeos_root = "../.."
  else:
    chromeos_root = options.chromeos_root
  chromeos_root = os.path.abspath(chromeos_root)

  if (options.toolchain_root is None or
      not os.path.exists(options.toolchain_root) or
      not os.path.exists(chromeos_root)):
    parser.print_help()
    sys.exit(1)

  tc_dirs = [options.toolchain_root + "/google_vendor_src_branch/gcc"]
  version_dir = rootdir

  all_dirs = tc_dirs[:]
  all_dirs.append(rootdir)

  mounted_tc_root = "/usr/local/toolchain_root"
  full_mounted_tc_root = chromeos_root + "/chroot/" + mounted_tc_root
  full_mounted_tc_root = os.path.abspath(full_mounted_tc_root)

  # First create the mount points
  CreateDir(full_mounted_tc_root, getpass.getuser())
  for d in all_dirs:
    last_dir = utils.GetRoot(d)[1]
    mounted_dir = (full_mounted_tc_root + "/" + last_dir)
    CreateDir(mounted_dir, getpass.getuser())

  # Now mount the toolchain directories.
  for tc_dir in tc_dirs:
    last_dir = utils.GetRoot(tc_dir)[1]
    MountDir(tc_dir, full_mounted_tc_root + "/" + last_dir, "ro")

  # Next, mount the version directory.
  last_dir = utils.GetRoot(version_dir)[1]
  MountDir(version_dir, full_mounted_tc_root + "/" + last_dir)

  # Finally, create the symlink to build-gcc.
  try:
    os.symlink(last_dir + "/build-gcc", full_mounted_tc_root + "/build-gcc")
  except Exception as e:
    utils.main_logger.LogOutput(str(e))

  # Now call enter_chroot with the rest of the arguments.
  command = "./enter_chroot.sh"

  if len(args) > 1:
    command += " -- " + " ".join(args[1:])
    retval = utils.RunCommand(command)
    return retval
  else:
    os.execv(command, [""])


def MountDir(dir_name, mount_point, options=None):
  command = "sudo mount --bind " + dir_name + " " + mount_point
  if options == "ro":
    command += " && sudo mount --bind -oremount,ro " + mount_point
  retval = utils.RunCommand(command)
  return retval


def CreateDir(dir_name, owner):
  if not os.path.exists(dir_name):
    command = "mkdir -p " + dir_name
    command += " || sudo mkdir -p " + dir_name
    retval = utils.RunCommand(command)
    if retval != 0:
      return retval
  command = "sudo chown " + owner + " " + dir_name
  retval = utils.RunCommand(command)
  return retval


if __name__ == "__main__":
  Main(sys.argv)

