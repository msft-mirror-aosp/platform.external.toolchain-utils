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
import hashlib


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

