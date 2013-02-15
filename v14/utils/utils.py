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
import tempfile
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


def CanonicalizePath(path):
  path = os.path.expanduser(path)
  path = os.path.realpath(path)
  return path


def GetCtargetFromBoard(board, chromeos_root):
  base_board = board.split("_")[0]
  command = ("cat"
             " $(cros_overlay_list --board=%s --primary_only)/toolchain.conf" %
             (base_board))
  ce = command_executer.GetCommandExecuter()
  ret, out, err = ce.ChrootRunCommand(chromeos_root,
                                      command,
                                      return_output=True)
  if ret != 0:
    raise ValueError("Board %s is invalid!" % board)
  return out.strip()


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
