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


def AssertTrue(condition, msg=""):
  if not condition:
    logger.GetLogger().LogError(msg)
    sys.exit(1)


def Serialize(argument):
  string = StringIO.StringIO()
  pickle.dump(argument, string)
  return string.getvalue()


def Deserialize(argument):
  return pickle.load(StringIO.StringIO(argument))


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")

