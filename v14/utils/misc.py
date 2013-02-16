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


def ApplySubs(string, *substitutions):
  for pattern, replacement in substitutions:
    string = re.sub(pattern, replacement, string)
  return string


def UnitToNumber(string, base=1000):
  unit_dict = {"kilo": base,
               "mega": base**2,
               "giga": base**3}
  string = string.lower()
  mo = re.search("(\d*)(.+)", string)
  number = mo.group(1)
  unit = mo.group(2)
  for k, v in unit_dict.items():
    if k.startswith(unit):
      return float(number) * v
  raise Exception("Unit: %s not found in byte: %s!" %
                  (unit,
                   string))


def GetFilenameFromString(string):
  return ApplySubs(string,
                   ("/", "__"),
                   ("\s", "_"),
                   ("=", ""),
                   ("\"", ""))


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def GetChrootPath(chromeos_root):
  return os.path.join(chromeos_root,
                      "chroot")


def GetInsideChrootPath(chromeos_root, file_path):
  if not file_path.startswith(GetChrootPath(chromeos_root)):
    raise Exception("File: %s doesn't seem to be in the chroot: %s" %
                    (file_path,
                     chromeos_root))
  return file_path[len(GetChrootPath(chromeos_root)):]


def GetOutsideChrootPath(chromeos_root, file_path):
  return os.path.join(GetChrootPath(chromeos_root),
                      file_path.lstrip("/"))


def FormatQuotedCommand(command):
  return ApplySubs(command,
                   ("\"", "\\\""))


def FormatCommands(commands):
  return ApplySubs(str(commands),
                   ("&&", "&&\n"),
                   (";", ";\n"),
                   ("\n+\s*", "\n"))


def GetImageDir(chromeos_root, board):
  return os.path.join(chromeos_root,
                      "src",
                      "build",
                      "images",
                      board)


def LabelLatestImage(chromeos_root, board, label):
  image_dir = GetImageDir(chromeos_root, board)
  latest_image_dir = os.path.join(image_dir, "latest")
  latest_image_dir = os.path.realpath(latest_image_dir)
  latest_image_dir = os.path.basename(latest_image_dir)
  with WorkingDirectory(image_dir):
    command = "ln -sf -T %s %s" % (latest_image_dir, label)
    ce = command_executer.GetCommandExecuter()
    return ce.RunCommand(command)


def DoesLabelExist(chromeos_root, board, label):
  image_label = os.path.join(GetImageDir(chromeos_root, board),
                             label)
  return os.path.exists(image_label)


def GetBuildPackagesCommand(board, usepkg=False):
  if usepkg:
    usepkg_flag = "--usepkg"
  else:
    usepkg_flag = "--nousepkg"
  return ("./build_packages %s --withdev --withtest --withautotest "
          "--skip_toolchain_update --nowithdebug --board=%s" %
          (usepkg_flag, board))


def GetBuildImageCommand(board):
  return "./build_image --board=%s test" % board


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
  command = ("source "
             "../platform/dev/toolchain_utils.sh; get_ctarget_from_board %s" %
             base_board)
  ce = command_executer.GetCommandExecuter()
  ret, out, err = ce.ChrootRunCommand(chromeos_root,
                                      command,
                                      return_output=True)
  if ret != 0:
    raise ValueError("Board %s is invalid!" % board)
  return out.strip()


def GetChromeSrcDir():
  return "var/cache/distfiles/target/chrome-src/src"


def GetEnvStringFromDict(env_dict):
  return " ".join(["%s=\"%s\"" % var for var in env_dict.items()])


def GetAllImages(chromeos_root, board):
  ce = command_executer.GetCommandExecuter()
  command = ("find %s/src/build/images/%s -name chromiumos_test_image.bin" %
             (chromeos_root, board))
  ret, out, err = ce.RunCommand(command, return_output=True)
  return out.splitlines()


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
