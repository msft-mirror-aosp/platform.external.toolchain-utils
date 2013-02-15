#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""


__author__ = "asharif@google.com (Ahmad Sharif)"

import os
import subprocess


class Logger(object):

  """Logging helper class."""

  def __init__ (self, rootdir, basefilename):
    self._logdir = rootdir + "/logs/"
    AtomicMkdir(self._logdir)
    self._basefilename = basefilename
    self._cmdfd = open(self._logdir + self._basefilename + ".cmd", "w", 0755)
    self._stout = open(self._logdir + self._basefilename + ".out", "w")
    self._sterr = open(self._logdir + self._basefilename + ".err", "w")

  def Stdout(self):
    return self._stout

  def Stderr(self):
    return self._sterr

  def Logcmd(self, cmd):
    self._cmdfd.write(str(cmd) + "\n")

  def __del__ (self):
    self._cmdfd.close()
    self._stout.close()
    self._sterr.close()
    return


main_logger = None


def InitLogger(rootdir, basefilename):
  """Initialize a global logger. To be called only once."""
  global main_logger
  main_logger = Logger(rootdir, basefilename)


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def RunCommand(cmd):
  """"Run a command while redirecting stdout and stderr to predefined files."""
  cmdlist = ["bash", "-c", cmd]
  main_logger.Logcmd(cmdlist)
  stout = main_logger.Stdout()
  sterr = main_logger.Stderr()
  p = subprocess.Popen(cmdlist, stdout=stout, stderr=sterr)
  p.wait()
  return p.returncode


def RunCommands(cmdlist):
  cmd = " ; " .join(cmdlist)
  print "CMD=", cmd
  return RunCommand(cmd)


def DoCommand(cmd):
  """"Run a command and return stdout and stderr as string. Log output."""
  cmdlist = ["bash", "-c", cmd]
  main_logger.Logcmd(cmdlist)
  p = subprocess.Popen(cmdlist, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
  (out, err) = p.communicate()
  # For now, log the output and error in the standard place. May need to revisit
  # if its making out files too large.
  stout = main_logger.Stdout()
  sterr = main_logger.Stderr()
  stout.write(out)
  sterr.write(err)
  stout.flush()
  sterr.flush()
  return (p.returncode, out, err)


def DoCommands(cmdlist):
  cmd = " ; " .join(cmdlist)
  return DoCommand(cmd)


def AtomicMkdir(newdir):
  try:
    os.makedirs(newdir)
  except OSError:
    # Check if it has been created, perhaps by another process
    if os.path.exists(newdir):
      return
