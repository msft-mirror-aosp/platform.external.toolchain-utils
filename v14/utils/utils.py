#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""

__author__ = "asharif@google.com (Ahmad Sharif)"

import hashlib
import os
import re
import stat
import command_executer
import logger
from contextlib import contextmanager


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")


def FormatCommands(commands):
  output = str(commands)
  output = re.sub("&&", "&&\n", output)
  output = re.sub(";", ";\n", output)
  output = re.sub("\n+\s*", "\n", output)
  return output


def GetBuildPackagesCommand(board):
  return "./build_packages --nousepkg --withdev --withtest --withautotest " \
         "--skip_toolchain_update --nowithdebug --board=%s" % board


def GetBuildImageCommand(board):
  return "./build_image --withdev --board=%s" % board


def GetModImageForTestCommand(board):
  return "./mod_image_for_test.sh --yes --board=%s" % board


def GetSetupBoardCommand(board, gcc_version=None, binutils_version=None,
                         usepkg=None, force=None):
  options = []

  if gcc_version:
    options.append("--gcc_version=%s" % gcc_version)

  if binutils_version:
    options.append("--binutils_version=%s" % binutils_version)

  if usepkg:
    options.append("--usepkg")
  else:
    options.append("--nousepkg")

  if force:
    options.append("--force")

  return "./setup_board --board=%s %s" % (board, " ".join(options))


def ExecuteCommandInChroot(chromeos_root, command, return_output=False):
  ce = command_executer.GetCommandExecuter()
  command_file = "in_chroot_cmd.sh"
  command_file_path = os.path.join(chromeos_root, "src/scripts", command_file)
  with open(command_file_path, "w") as f:
    print >>f, "#!/bin/bash"
    print >>f, command
  os.chmod(command_file_path, 0777)
  with WorkingDirectory(chromeos_root):
    command = "cros_sdk -- ./%s" % command_file
    return ce.RunCommand(command, return_output)


@contextmanager
def WorkingDirectory(new_dir):
  old_dir = os.getcwd()
  if old_dir != new_dir:
    msg = "cd %s" % new_dir
    logger.GetLogger().LogCmd(msg)
  os.chdir(new_dir)
  yield new_dir
  if old_dir != new_dir:
    msg = "cd %s" % old_dir
    logger.GetLogger().LogCmd(msg)
  os.chdir(old_dir)
