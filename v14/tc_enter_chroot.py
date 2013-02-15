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
import pwd
import stat
import sys
from utils import command_executer
from utils import logger
from utils import utils

class MountPoint:
  def __init__(self, external_dir, mount_dir, owner, options=None):
    self.external_dir = external_dir
    self.mount_dir = mount_dir
    self.owner = owner
    self.options = options


  def CreateAndOwnDir(self, dir_name):
    retval = 0
    if not os.path.exists(dir_name):
      command = "mkdir -p " + dir_name
      command += " || sudo mkdir -p " + dir_name
      retval = command_executer.GetCommandExecuter().RunCommand(command)
    if retval != 0:
      return retval
    pw = pwd.getpwnam(self.owner)
    if os.stat(dir_name).st_uid != pw.pw_uid:
      command = "sudo chown -f " + self.owner + " " + dir_name
      retval = command_executer.GetCommandExecuter().RunCommand(command)
    return retval


  def DoMount(self):
    retval = self.CreateAndOwnDir(self.mount_dir)
    logger.GetLogger().LogFatalIf(retval, "Cannot create mount_dir!")
    retval = self.CreateAndOwnDir(self.external_dir)
    logger.GetLogger().LogFatalIf(retval, "Cannot create external_dir!")
    retval = self.MountDir()
    logger.GetLogger().LogFatalIf(retval, "Cannot mount!")
    return retval


  def MountDir(self):
    command = "sudo mount --bind " + self.external_dir + " " + self.mount_dir
    if self.options == "ro":
      command += " && sudo mount --bind -oremount,ro " + self.mount_dir
    retval = command_executer.GetCommandExecuter().RunCommand(command)
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
  parser.add_option("-o", "--output", dest="output",
                    help="Toolchain output directory")
  parser.add_option("-r", "--third_party", dest="third_party",
                    help="The third_party directory to mount.")
  parser.add_option("-m", "--other_mounts", dest="other_mounts",
                    help="Other mount points in the form: " +
                         "dir:mounted_dir:options")
  parser.add_option("-s", "--mount-scripts-only",
                    dest="mount_scripts_only",
                    action="store_true",
                    default=False,
                    help="Mount only the scripts dir, and not the sources.")

  passthrough_argv = []
  (options, passthrough_argv) = parser.parse_args(argv)

  chromeos_root = options.chromeos_root

  chromeos_root = os.path.expanduser(chromeos_root)
  if options.toolchain_root:
    options.toolchain_root = os.path.expanduser(options.toolchain_root)

  chromeos_root = os.path.abspath(chromeos_root)

  tc_dirs = []
  if options.toolchain_root is None or options.mount_scripts_only:
    m = "toolchain_root not specified. Will not mount toolchain dirs."
    logger.GetLogger().LogWarning(m)
  else:
    tc_dirs = [options.toolchain_root + "/google_vendor_src_branch/gcc",
               options.toolchain_root + "/google_vendor_src_branch/binutils"]

  for tc_dir in tc_dirs:
    if not os.path.exists(tc_dir):
      logger.GetLogger().LogError("toolchain path " +
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

  rootdir = utils.GetRoot(__file__)[0]
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

  # Add the third_party mount point if it exists
  if options.third_party:
    third_party_dir = options.third_party
    logger.GetLogger().LogFatalIf(not os.path.isdir(third_party_dir),
                                  "--third_party option is not a valid dir.")
  else:
    third_party_dir = os.path.abspath("%s/../../../third_party" %
                                      os.path.dirname(__file__))

  if os.path.isdir(third_party_dir):
    mount_point = MountPoint(third_party_dir,
                             ("%s/%s" %
                              (full_mounted_tc_root,
                               os.path.basename(third_party_dir))),
                               getpass.getuser())
    mount_points.append(mount_point)

  output = options.output
  if output is None and options.toolchain_root:
    # Mount the output directory at /usr/local/toolchain_root/output
    output = options.toolchain_root + "/output"

  if output:
    mount_points.append(MountPoint(output, full_mounted_tc_root + "/output",
                                   getpass.getuser()))

  # Mount the other mount points
  mount_points += CreateMountPointsFromString(options.other_mounts,
                                              chromeos_root + "/chroot/")

  last_dir = utils.GetRoot(version_dir)[1]

  # Mount the version dir (v14) at /usr/local/toolchain_root/v14
  mount_point = MountPoint(version_dir, full_mounted_tc_root + "/" + last_dir,
                           getpass.getuser())
  mount_points.append(mount_point)

  for mount_point in mount_points:
    retval = mount_point.DoMount()
    if retval != 0:
      return retval

  # Finally, create the symlink to build-gcc.
  command = "sudo chown " + getpass.getuser() + " " + full_mounted_tc_root
  retval = command_executer.GetCommandExecuter().RunCommand(command)

  try:
    CreateSymlink(last_dir + "/build-gcc", full_mounted_tc_root + "/build-gcc")
    CreateSymlink(last_dir + "/build-binutils", full_mounted_tc_root + "/build-binutils")
  except Exception as e:
    logger.GetLogger().LogError(str(e))

  # Now call enter_chroot with the rest of the arguments.
  command = chromeos_root + "/src/scripts/enter_chroot.sh"

  if len(passthrough_argv) > 1:
    inner_command = " ".join(passthrough_argv[1:])
    inner_command = inner_command.strip()
    if inner_command.startswith("-- "):
      inner_command = inner_command[3:]
    command_file = "tc_enter_chroot.cmd"
    command_file_path = chromeos_root + "/src/scripts/" + command_file
    retval = command_executer.GetCommandExecuter().RunCommand("sudo rm -f " + command_file_path)
    if retval != 0:
      return retval
    f = open(command_file_path, "w")
    f.write(inner_command)
    f.close()
    logger.GetLogger().LogCmd(inner_command)
    retval = command_executer.GetCommandExecuter().RunCommand("chmod +x " + command_file_path)
    if retval != 0:
      return retval
    command += " ./" + command_file
    retval = command_executer.GetCommandExecuter().RunCommand(command, return_output)
    return retval
  else:
    return os.execv(command, [""])


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
    if len(mount_values) > 2:
      options = mount_values[2]
    else:
      options = None
    mount_point = MountPoint(external_dir, chroot_dir + "/" + mount_dir,
                             getpass.getuser(), options)
    mount_points.append(mount_point)
  return mount_points


def CreateSymlink(target, link_name):
  logger.GetLogger().LogFatalIf(target.startswith("/"),
                                "Can't create symlink to absolute path!")
  real_from_file = utils.GetRoot(link_name)[0] + "/" + target
  if os.path.realpath(real_from_file) != os.path.realpath(link_name):
    if os.path.exists(link_name):
      command = "rm -rf " + link_name
      command_executer.GetCommandExecuter().RunCommand(command)
    os.symlink(target, link_name)


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
