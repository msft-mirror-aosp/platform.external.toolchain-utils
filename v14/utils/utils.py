#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""


__author__ = "asharif@google.com (Ahmad Sharif)"

import os
import pickle
import re
import StringIO
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


def Serialize(argument):
  string = StringIO.StringIO()
  pickle.dump(argument, string)
  return string.getvalue()


def Deserialize(argument):
  return pickle.load(StringIO.StringIO(argument))


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")

def FormatCommands(commands):
    output = commands
    output = re.sub("&&", "&&\n", output)
    output = re.sub(";", ";\n", output)
    output = re.sub("\n+\s*", "\n", output)
    return output

def GetBuildPackagesCommand(board):
  command = ""
  command += ("./build_packages --nousepkg --withdev --withtest"
              " --withautotest --board=%s" %
              (board))
  return command

def GetBuildImageCommand(board):
  command = ""
  command += ("./build_image --withdev --board=%s" %
              board)
  return command

def GetModImageForTestCommand(board):
  command = ""
  command += ("./mod_image_for_test.sh --yes --board=%s" %
              board)
  return command

def GetSetupBoardCommand(board,
    gcc_version=None,
    binutils_version=None,
    usepkg=None,
    force=None):
  if not gcc_version:
    gcc_version_option = ""
  else:
    gcc_version_option = "--gcc_version=" + gcc_version
  if not binutils_version:
    binutils_version_option = ""
  else:
    binutils_version_option = "--binutils_version=" + binutils_version
  if not usepkg:
    usepkg_option = ""
  elif usepkg == True:
    usepkg_option = "--usepkg"
  elif usepkg == False:
    usepkg_option = "--nousepkg"
  if not force:
    force_option = ""
  elif force == True:
    force_option = "--force"
  else:
    force_option = ""
  command = ""
  command += ("./setup_board --board=%s %s %s %s %s" %
              (board,
               gcc_version_option,
               binutils_version_option,
               usepkg_option,
               force_option))
  return command


def Md5File(filename, block_size=2**10):
  f = open(filename, "r")
  AssertExit(f is not None)
  md5 = hashlib.md5()
  while True:
    data = f.read(block_size)
    if not data:
      break
    md5.update(data)
  f.close()
  return md5.hexdigest()


def ExitWithCode(code):
  if code == None:
    AssertExit("Exit code should not be None!")
  sys.exit(code)

