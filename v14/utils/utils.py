#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""


__author__ = "asharif@google.com (Ahmad Sharif)"

import os
import pickle
import re
import sys
import logger
import hashlib
import traceback


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


# deprecated. Use AssertExit()
def AssertTrue(condition, msg=""):
  if not condition:
    logger.GetLogger().LogError(msg)
    sys.exit(1)


def AssertExit(condition, msg=""):
  if not condition:
    logger.GetLogger().LogError(msg)
    print "\n".join(traceback.format_stack())
    sys.exit(1)


def AssertError(condition, msg=""):
  if not condition:
    print "\n".join(traceback.format_stack())
    logger.GetLogger().LogError(msg)


def AssertWarning(condition, msg=""):
  if not condition:
    logger.GetLogger().LogWarning(msg)


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")


def FormatCommands(commands):
  output = commands
  output = re.sub("&&", "&&\n", output)
  output = re.sub(";", ";\n", output)
  output = re.sub("\n+\s*", "\n", output)
  return output

def GetBuildPackagesCommand(board):
  return "./build_packages --nousepkg --withdev --withtest --withautotest " \
         "--board=%s" % board


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


def Md5File(filename, block_size=2**10):
  md5 = hashlib.md5()

  try:
    with open(filename) as f:
      while True:
        data = f.read(block_size)
        if not data:
          break
        md5.update(data)
  except IOError as ex:
    AssertExit(False, str(ex))

  return md5.hexdigest()
