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
from utils import command_executer
from utils import logger
from utils import utils

# Common initializations
cmd_executer = command_executer.GetCommandExecuter()


class MountPoint:
  def __init__(self, external_dir, mount_dir, owner, options=None):
    self.external_dir = external_dir
    self.mount_dir = mount_dir
    self.owner = owner
    self.options = options


  def CreateMountPoint(self):
    if not os.path.exists(self.mount_dir):
      command = "mkdir -p " + self.mount_dir
      command += " || sudo mkdir -p " + self.mount_dir
      retval = cmd_executer.RunCommand(command)
      if retval != 0:
        return retval
    command = "sudo chown " + self.owner + " " + self.mount_dir
    retval = cmd_executer.RunCommand(command)
    return retval


  def DoMount(self):
    self.CreateMountPoint()
    self.MountDir()


  def MountDir(self):
    command = "sudo mount --bind " + self.external_dir + " " + self.mount_dir
    if self.options == "ro":
      command += " && sudo mount --bind -oremount,ro " + self.mount_dir
    retval = cmd_executer.RunCommand(command)
    return retval


  def __str__(self):
    ret = ""
    ret += self.external_dir + "\n"
    ret += self.mount_dir + "\n"
    if self.owner:
      ret += self.owner + "\n"
    if self.options:
      ret += self.options + "\n"
    return ret


def Main(argv, return_output=False):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    default="../..",
                    help="ChromeOS root checkout directory.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="Toolchain root directory.")
  parser.add_option("-o", "--other_mounts", dest="other_mounts",
                    help="Other mount points in the form: " + 
                         "dir:mounted_dir:options")

  relevant_argv = []
  passthrough_argv = []
  for i in xrange(len(argv)):
    found = False
    for option in parser.option_list:
      for long_opt in option._long_opts:
        if argv[i].startswith(long_opt):
          found = True
          break
      for short_opt in option._short_opts:
        if argv[i].startswith(short_opt):
          found = True
          break

      if found == True:
        break

    if found == True:
      relevant_argv.append(argv[i])
    else:
      passthrough_argv.append(argv[i])

  options = parser.parse_args(relevant_argv)[0]

  chromeos_root = options.chromeos_root

  chromeos_root = os.path.expanduser(chromeos_root)
  if options.toolchain_root:
    options.toolchain_root = os.path.expanduser(options.toolchain_root)

  chromeos_root = os.path.abspath(chromeos_root)

  if options.toolchain_root is None:
    logger.GetLogger().LogError("--toolchain_root not specified")
    parser.print_help()
    sys.exit(1)

  tc_dirs = [options.toolchain_root + "/google_vendor_src_branch/gcc"]

  for tc_dir in tc_dirs:
    if not os.path.exists(tc_dir):
      logger.GetLogger().LogError("toolchain path " + options.toolchain_root + 
                                 tc_dir + " does not exist!")
      parser.print_help()
      sys.exit(1)

  if not os.path.exists(chromeos_root):
    logger.GetLogger().LogError("chromeos_root " + options.chromeos_root +
                                 " does not exist!")
    parser.print_help()
    sys.exit(1)

  if not os.path.exists(chromeos_root + "/src/scripts/enter_chroot.sh"):
    logger.GetLogger().LogError(options.chromeos_root + 
                                 "/src/scripts/enter_chroot.sh"
                                 " not found!")
    parser.print_help()
    sys.exit(1)

  rootdir = utils.GetRoot(sys.argv[0])[0]
  version_dir = rootdir

  mounted_tc_root = "/usr/local/toolchain_root"
  full_mounted_tc_root = chromeos_root + "/chroot/" + mounted_tc_root
  full_mounted_tc_root = os.path.abspath(full_mounted_tc_root)
 
  mount_points = []
  for tc_dir in tc_dirs:
    last_dir = utils.GetRoot(tc_dir)[1]
    mount_point = MountPoint(tc_dir, full_mounted_tc_root + "/" + last_dir,
                             getpass.getuser(), "ro")
    mount_points.append(mount_point)

  mount_points += CreateMountPointsFromString(options.other_mounts, 
                                              chromeos_root + "/chroot/")

  last_dir = utils.GetRoot(version_dir)[1]
  mount_point = MountPoint(version_dir, full_mounted_tc_root + "/" + last_dir,
                           getpass.getuser())
  mount_points.append(mount_point)

  for mount_point in mount_points:
    mount_point.DoMount()

  # Finally, create the symlink to build-gcc.
  command = "sudo chown " + getpass.getuser() + " " + full_mounted_tc_root
  retval = cmd_executer.RunCommand(command)

  try:
    os.symlink(last_dir + "/build-gcc", full_mounted_tc_root + "/build-gcc")
  except Exception as e:
    logger.GetLogger().LogError(str(e))

  # Now call enter_chroot with the rest of the arguments.
  command = chromeos_root + "/src/scripts/enter_chroot.sh"

  if len(passthrough_argv) > 1:
    command += " " + " ".join(passthrough_argv[1:])
    retval = cmd_executer.RunCommand(command, return_output)
    return retval
  else:
    os.execv(command, [""])


def CreateMountPointsFromString(mount_strings, chroot_dir):
  # String has options in the form dir:mount:options
  mount_points = []
  if not mount_strings:
    return mount_points
  mount_list = mount_strings.split()
  for mount_string in mount_list:
    mount_values = mount_string.split(":")
    external_dir = mount_values[0]
    mount_dir = mount_values[1]
    if len(mount_values)>2:
      options = mount_values[2]
    else:
      options = None
    mount_point = MountPoint(external_dir, chroot_dir + "/" + mount_dir, 
                             getpass.getuser(), options)
    mount_points.append(mount_point)
  return mount_points


if __name__ == "__main__":
  Main(sys.argv)

