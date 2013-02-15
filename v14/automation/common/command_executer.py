#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
#

__author__ = "kbaclawski@google.com (Krystian Baclawski)"

import fcntl
import os
import select
import subprocess
import time

from automation.common import logger


class CommandExecuter(object):
  DRY_RUN = False

  def __init__(self, logger_to_set=None, dry_run=False):
    self.logger = logger_to_set or logger.GetLogger()
    self._dry_run = dry_run or self.DRY_RUN

  @classmethod
  def Configure(cls, dry_run):
    cls.DRY_RUN = dry_run

  def RunCommand(self, cmd, machine=None, username=None,
                 command_terminator=None, command_timeout=None):
    """Run a command."""

    cmd = str(cmd)

    if self._dry_run:
      logger.GetLogger().LogCmd(
          "(Mock) %s" % cmd, machine or "localhost", username or os.getlogin())
      return 0

    self.logger.LogCmd(cmd, machine, username)

    if command_terminator and command_terminator.IsTerminated():
      self.logger.LogError("Command was terminated!")
      return 1

    # Rewrite command for remote execution.
    if machine:
      if username:
        login = "%s@%s" % (username, machine)
      else:
        login = machine

      cmd = "ssh -T -n %s -- '%s'" % (login, cmd)

    return self._SpawnProcess(cmd, command_terminator, command_timeout)

  def _SpawnProcess(self, cmd, command_terminator, command_timeout):
    # Create command's process.
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    started_time = time.time()

    # Watch for data on process stdout, stderr.
    pipes = [child.stdout, child.stderr]

    # Put pipes into non-blocking mode.
    for pipe in pipes:
      fd = pipe.fileno()
      fd_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
      fcntl.fcntl(fd, fcntl.F_SETFL, fd_flags | os.O_NONBLOCK)

    while pipes:
      # Wait for pipes to become ready.
      ready_pipes, _, _ = select.select(pipes, [], [], 0.1)

      # Maybe termination request was received?
      if command_terminator and command_terminator.IsTerminated():
        self.logger.LogError("Killing command!")
        self.RunCommand("kill -9 %d" % child.pid)
        break

      # Handle file descriptors ready to be read.
      for pipe in ready_pipes:
        fd = pipe.fileno()

        data = os.read(fd, 4096)

        # check for end-of-file
        if not data:
          pipes.remove(pipe)
          continue

        # read all data that's available
        while data:
          if pipe == child.stdout:
            self.logger.LogCommandOutput(data)
          elif pipe == child.stderr:
            self.logger.LogCommandError(data)

          try:
            data = os.read(fd, 4096)
          except OSError:
            # terminate loop if EWOULDBLOCK (EAGAIN) is received
            data = ""

      if command_timeout and time.time() - started_time > command_timeout:
        self.logger.LogWarning("Timeout of %s seconds reached since process "
                               "started." % command_timeout)
        self.RunCommand("kill %d || kill -9 %d" % (child.pid, child.pid))
        break

    self.logger.LogOutput("Waiting for command to finish.")
    child.wait()

    return child.returncode


class CommandTerminator(object):
  def __init__(self):
    self.terminated = False

  def Terminate(self):
    self.terminated = True

  def IsTerminated(self):
    return self.terminated
