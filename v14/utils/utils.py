#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Utilities for toolchain build."""


__author__ = "asharif@google.com (Ahmad Sharif)"

import os
import pickle
import select
import StringIO
import subprocess
import sys


class Logger(object):

  """Logging helper class."""

  def __init__ (self, rootdir, basefilename, print_console=True):
    self._logdir = rootdir + "/logs/"
    AtomicMkdir(self._logdir)
    self._basefilename = basefilename
    self.cmdfd = open(self._logdir + self._basefilename + ".cmd", "w", 0755)
    self.stdout = open(self._logdir + self._basefilename + ".out", "w")
    self.stderr = open(self._logdir + self._basefilename + ".err", "w")
    self.print_console = print_console

  def Logcmd(self, cmd):
    self.cmdfd.write(str(cmd) + "\n")
    if self.print_console:
      print "CMD: " + str(cmd)

  def LogOutput(self, msg):
    msg = "OUTPUT: " + msg + "\n"
    self.stdout.write(msg)
    if self.print_console:
      sys.stderr.write(msg)

  def LogError(self, msg):
    msg = "ERROR: " + msg + "\n"
    self.stderr.write(msg)
    if self.print_console:
      sys.stderr.write(msg)

  def RunLoggedCommand(self, cmd, return_output=False):
    """Run a command and log the output."""
    cmdlist = ["bash", "-c", cmd]
    self.Logcmd(cmdlist)

    p = subprocess.Popen(cmdlist, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=sys.stdin)

    full_stdout = ""
    full_stderr = ""

    # Pull output from pipes, send it to file/stdout/string
    out = err = None
    while True:
      fds = select.select([p.stdout, p.stderr], [], [], 0.1)
      for fd in fds[0]:
        if fd == p.stdout:
          out = os.read(p.stdout.fileno(), 1)
          if return_output:
            full_stdout += out
          if self.print_console:
            sys.stdout.write(out)
            sys.stdout.flush()
          self.stdout.write(out)
          self.stdout.flush()
        if fd == p.stderr:
          err = os.read(p.stderr.fileno(), 1)
          if return_output:
            full_stderr += err
          if self.print_console:
            sys.stderr.write(err)
            sys.stderr.flush()
          self.stderr.write(err)
          self.stderr.flush()

      if out == err == "":
        break

    p.wait()
    if return_output:
      return (p.returncode, full_stdout, full_stderr)
    return p.returncode

  def __del__ (self):
    self.cmdfd.close()
    self.stdout.close()
    self.stderr.close()
    return


main_logger = None


def AssertTrue(condition, msg=""):
  if not condition:
    main_logger.LogError(msg)
    sys.exit(1)


def InitLogger(rootdir, basefilename):
  """Initialize a global logger. To be called only once."""
  global main_logger
  main_logger = Logger(rootdir, basefilename)


def GetRoot(scr_name):
  """Break up pathname into (dir+name)."""
  abs_path = os.path.abspath(scr_name)
  return (os.path.dirname(abs_path), os.path.basename(abs_path))


def RunCommand(cmd, return_output=False):
  """"Run a command while redirecting stdout and stderr to predefined files."""
  return main_logger.RunLoggedCommand(cmd, return_output)


def RunCommands(cmdlist, return_output=False):
  cmd = " ; " .join(cmdlist)
  return RunCommand(cmd, return_output)


def AtomicMkdir(newdir):
  try:
    os.makedirs(newdir)
  except OSError:
    # Check if it has been created, perhaps by another process
    if os.path.exists(newdir):
      return


def Serialize(argument):
  string = StringIO.StringIO()
  pickle.dump(argument, string)
  return string.getvalue()

def Deserialize(argument):
  return pickle.load(StringIO.StringIO(argument))


def FormatQuotedCommand(command):
  return command.replace("\"", "\\\"")

