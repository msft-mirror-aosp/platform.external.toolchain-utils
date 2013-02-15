#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build the ChromeOS toolchain.

This script sets up the toolchain if you give it the gcctools directory.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import getpass
import optparse
import os
import sys
import tempfile
import tc_enter_chroot
from utils import command_executer
from utils import utils


class ToolchainPart(object):
  def __init__(self, name, source_path, chromeos_root, board, incremental,
               build_env):
    self._name = name
    self._source_path = utils.CanonicalizePath(source_path)
    self._chromeos_root = chromeos_root
    self._board = board
    self._ctarget = utils.GetCtargetFromBoard(self._board,
                                              self._chromeos_root)
    self._ce = command_executer.GetCommandExecuter()
    self._mask_file = os.path.join(
        self._chromeos_root,
        "chroot",
        "etc/portage/package.mask/cross-%s" % self._ctarget)
    self._new_mask_file = None

    self._chroot_source_path = "usr/local/toolchain_root/%s" % self._name
    self._incremental = incremental
    self._build_env = build_env

  def RunSetupBoardIfNecessary(self):
    cross_symlink = os.path.join(
        self._chromeos_root,
        "chroot",
        "usr/local/portage/crossdev/cross-%s" % self._ctarget)
    if not os.path.exists(cross_symlink):
      command = "./setup_board --board=%s" % self._board
      self._ce.ChrootRunCommand(self._chromeos_root, command)

  def Build(self):
    self.RunSetupBoardIfNecessary()

    try:
      self.UninstallTool()
      self.MoveMaskFile()
      self.SwitchToBFD()
      self.MountSources()
      if not self._incremental:
        self.RemoveCompiledFile()
      self.BuildTool()
    finally:
      self.UnMoveMaskFile()
      self.SwitchToOriginalLD()

  def RemoveCompiledFile(self):
    compiled_file = os.path.join(self._chromeos_root,
                                 "chroot",
                                 "var/tmp/portage/cross-%s" % self._ctarget,
                                 "%s-9999" % self._name,
                                 ".compiled")
    command = "rm -rf %s" % compiled_file
    self._ce.RunCommand(command)

  def MountSources(self):
    mount_points = []
    mounted_source_path = os.path.join(self._chromeos_root,
                                       "chroot",
                                       self._chroot_source_path)
    src_mp = tc_enter_chroot.MountPoint(
        self._source_path,
        mounted_source_path,
        getpass.getuser(),
        "ro")
    mount_points.append(src_mp)

    build_suffix = "build-%s" % self._ctarget
    build_dir = "%s-%s" % (self._source_path, build_suffix)

    if not self._incremental and os.path.exists(build_dir):
      command = "rm -rf %s/*" % build_dir
      self._ce.RunCommand(command)

    # Create a -build directory for the objects.
    command = "mkdir -p %s" % build_dir
    self._ce.RunCommand(command)

    mounted_build_dir = os.path.join(
        self._chromeos_root, "chroot", "%s-%s" %
        (self._chroot_source_path, build_suffix))
    build_mp = tc_enter_chroot.MountPoint(
        build_dir,
        mounted_build_dir,
        getpass.getuser())
    mount_points.append(build_mp)

    mount_statuses = [mp.DoMount() == 0 for mp in mount_points]

    if not all(mount_statuses):
      mounted = [mp for mp, status in zip(mount_points, mount_statuses) if status]
      unmount_statuses = [mp.UnMount() == 0 for mp in mounted]
      assert all(unmount_statuses), "Could not unmount all mount points!"

  def UninstallTool(self):
    command = "sudo CLEAN_DELAY=0 emerge -C cross-%s/%s" % (self._ctarget, self._name)
    self._ce.ChrootRunCommand(self._chromeos_root, command)

  def BuildTool(self):
    env = self._build_env
    features = "nostrip userpriv userfetch -sandbox noclean"
    env["FEATURES"] = features

    if self._incremental:
      env["FEATURES"] += " keepwork"

    env["USE"] = "multislot mounted_%s" % self._name
    env["%s_SOURCE_PATH" % self._name.upper()] = (
        os.path.join("/", self._chroot_source_path))
    env["ACCEPT_KEYWORDS"] = "~*"
    env_string = " ".join(["%s=\"%s\"" % var for var in env.items()])
    command = "emerge =cross-%s/%s-9999" % (self._ctarget, self._name)
    full_command = "sudo %s %s" % (env_string, command)
    self._ce.ChrootRunCommand(self._chromeos_root, full_command)

  def SwitchToBFD(self):
    command = "sudo binutils-config %s-2.21" % self._ctarget
    self._ce.ChrootRunCommand(self._chromeos_root, command)

  def SwitchToOriginalLD(self):
    pass

  def MoveMaskFile(self):
    self._new_mask_file = None
    if os.path.isfile(self._mask_file):
      self._new_mask_file = tempfile.mktemp()
      command = "sudo mv %s %s" % (self._mask_file, self._new_mask_file)
      self._ce.RunCommand(command)

  def UnMoveMaskFile(self):
    if self._new_mask_file:
      command = "sudo mv %s %s" % (self._new_mask_file, self._mask_file)
      self._ce.RunCommand(command)


def Main(argv):
  """The main function."""
  # Common initializations
  parser = optparse.OptionParser()
  parser.add_option("-c",
                    "--chromeos_root",
                    dest="chromeos_root",
                    help=("ChromeOS root checkout directory"
                          " uses ../.. if none given."))
  parser.add_option("-g",
                    "--gcc_dir",
                    dest="gcc_dir",
                    help="The directory where gcc resides.")
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-agz",
                    help="The target board.")
  parser.add_option("-n",
                    "--noincremental",
                    dest="noincremental",
                    default=False,
                    action="store_true",
                    help="Use FEATURES=keepwork to do incremental builds.")
  parser.add_option("-d",
                    "--debug",
                    dest="debug",
                    default=False,
                    action="store_true",
                    help="Build a compiler with -g3 -O0.")
  parser.add_option("-m",
                    "--mount_only",
                    dest="mount_only",
                    default=False,
                    action="store_true",
                    help="Just mount the tool directories.")


  options, _ = parser.parse_args(argv)

  chromeos_root = utils.CanonicalizePath(options.chromeos_root)
  gcc_dir = utils.CanonicalizePath(options.gcc_dir)
  build_env = {}
  if options.debug:
    debug_flags = "-g3 -O0"
    build_env["CFLAGS"] = debug_flags
    build_env["CXXFLAGS"] = debug_flags

  # Create toolchain parts
  toolchain_parts = []
  for board in options.board.split(","):
    if options.gcc_dir:
      tp = ToolchainPart("gcc", gcc_dir, chromeos_root, board,
                         not options.noincremental, build_env)
      toolchain_parts.append(tp)

  try:
    for tp in toolchain_parts:
      if options.mount_only:
        tp.MountSources()
      else:
        tp.Build()
  finally:
    print "Exiting..."
  return 0


if __name__ == "__main__":
  retval = Main(sys.argv)
  sys.exit(retval)
