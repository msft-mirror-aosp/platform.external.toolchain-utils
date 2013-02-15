#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""


__author__ = "asharif@google.com (Ahmad Sharif)"

import os
import pickle
import StringIO
import sys
import logger


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
    sys.exit(1)


def AssertError(condition, msg=""):
  if not condition:
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


EXPECTCMD = '/usr/bin/expect -c "spawn %s %s; expect *Password:*; send -- \\"test0000\n\\"; interact;"'

def ssh_cmd(sshargs):
  """Guts of ssh_cmd"""

  cmd = EXPECTCMD % ('ssh', sshargs)
  return os.system(cmd)

def scp_cmd(scpargs):
  """Guts of scp_cmd"""

  cmd = EXPECTCMD % ('scp', scpargs)
  return os.system(cmd)
