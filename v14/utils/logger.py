#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import sys
import traceback
import utils


class Logger(object):
  """Logging helper class."""

  MAX_LOG_FILES = 10

  def __init__ (self, rootdir, basefilename, print_console, subdir="logs"):
    logdir = os.path.join(rootdir, subdir)
    basename = os.path.join(logdir, basefilename)

    try:
      os.makedirs(logdir)
    except OSError:
      pass
      # print "Warning: Logs directory '%s' already exists." % logdir

    self.print_console = print_console

    self._CreateLogFileHandles(basename)

    self._WriteTo(self.cmdfd, " ".join(sys.argv), True)

  def _AddSuffix(self, basename, suffix):
    return "%s%s" % (basename, suffix)

  def _FindSuffix(self, basename):
    timestamps = []
    found_suffix = None
    for i in range(self.MAX_LOG_FILES):
      suffix = str(i)
      suffixed_basename = self._AddSuffix(basename, suffix)
      cmd_file = "%s.cmd" % suffixed_basename
      if not os.path.exists(cmd_file):
        found_suffix = suffix
        break
      timestamps.append(os.stat(cmd_file).st_mtime)

    if found_suffix:
      return found_suffix

    # Try to pick the oldest file with the suffix and return that one.
    suffix = str(timestamps.index(min(timestamps)))
    # print ("Warning: Overwriting log file: %s" %
    #       self._AddSuffix(basename, suffix))
    return suffix

  def _CreateLogFileHandles(self, basename):
    suffix = self._FindSuffix(basename)
    suffixed_basename = self._AddSuffix(basename, suffix)

    self.cmdfd = open("%s.cmd" % suffixed_basename, "w", 0755)
    self.stdout = open("%s.out" % suffixed_basename, "w")
    self.stderr = open("%s.err" % suffixed_basename, "w")

    self._CreateLogFileSymlinks(basename, suffixed_basename)

  # Symlink unsuffixed basename to currently suffixed one.
  def _CreateLogFileSymlinks(self, basename, suffixed_basename):
    try:
      for extension in ["cmd", "out", "err"]:
        src_file = "%s.%s" % (os.path.basename(suffixed_basename), extension)
        dest_file = "%s.%s" % (basename, extension)
        if os.path.exists(dest_file):
          os.remove(dest_file)
        os.symlink(src_file, dest_file)
    except IOError as ex:
      self.LogFatal(str(ex))

  def _WriteTo(self, fd, msg, flush):
    fd.write(msg)
    if flush:
      fd.flush()

  def _LogMsg(self, file_fd, term_fd, msg, flush=True):
    self._WriteTo(file_fd, msg, flush)
    if self.print_console:
      self._WriteTo(term_fd, msg, flush)

  def LogCmd(self, cmd, machine="", user=None):
    if user:
      host = "%s@%s" % (user, machine)
    else:
      host = machine

    self._LogMsg(self.cmdfd, sys.stdout, "CMD (%s): %s\n" % (host, cmd))

  def LogFatal(self, msg):
    self._LogMsg(self.stderr, sys.stderr, "FATAL: %s\n" % msg)
    self._LogMsg(self.stderr, sys.stderr, "\n".join(traceback.format_stack()))
    sys.exit(1)

  def LogError(self, msg):
    self._LogMsg(self.stderr, sys.stderr, "ERROR: %s\n" % msg)

  def LogWarning(self, msg):
    self._LogMsg(self.stderr, sys.stderr, "WARNING: %s\n" % msg)

  def LogOutput(self, msg):
    self._LogMsg(self.stdout, sys.stdout, "OUTPUT: %s\n" % msg)

  def LogFatalIf(self, condition, msg):
    if condition:
      self.LogFatal(msg)

  def LogErrorIf(self, condition, msg):
    if condition:
      self.LogError(msg)

  def LogWarningIf(self, condition, msg):
    if condition:
      self.LogWarning(msg)

  def LogCommandOutput(self, msg):
    self._LogMsg(self.stdout, sys.stdout, msg, flush=False)

  def LogCommandError(self, msg):
    self._LogMsg(self.stderr, sys.stderr, msg, flush=False)

  def Flush(self):
    self.cmdfd.flush()
    self.stdout.flush()
    self.stderr.flush()

main_logger = None


def InitLogger(script_name, print_console=True):
  """Initialize a global logger. To be called only once."""
  global main_logger
  assert not main_logger, "The logger has already been initialized"
  rootdir, basefilename = utils.GetRoot(script_name)
  main_logger = Logger(rootdir, basefilename, print_console)


def GetLogger():
  if not main_logger:
    InitLogger(sys.argv[0])
  return main_logger


def HandleUncaughtExceptions(fun):
  """Catches all exceptions that would go outside decorated fun scope."""

  def _Interceptor(*args, **kwargs):
    try:
      return fun(*args, **kwargs)
    except StandardError:
      GetLogger().LogFatal("Uncaught exception:\n%s" % traceback.format_exc())

  return _Interceptor
