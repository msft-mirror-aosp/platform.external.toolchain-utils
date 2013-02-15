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

    self.logger.LogCmd(cmd, machine, username)

    if self._dry_run:
      return 0

    if not command_terminator:
      command_terminator = CommandTerminator()

    if command_terminator.IsTerminated():
      self.logger.LogError("Command has been already terminated!")
      return 1

    # Rewrite command for remote execution.
    if machine:
      if username:
        login = "%s@%s" % (username, machine)
      else:
        login = machine

      cmd = "ssh %s -- '%s'" % (login, cmd)

    child = self._SpawnProcess(cmd, command_terminator, command_timeout)

    self.logger.LogOutput(
        "[PID: %d] Finished with %d code." % (child.pid, child.returncode))

    return child.returncode

  def _Terminate(self, child, command_timeout, wait_timeout=10):
    """Gracefully shutdown the child by sending SIGTERM."""

    if command_timeout:
      self.logger.LogWarning("[PID: %d] Timeout of %s seconds reached since "
                             "process started." % (child.pid, command_timeout))

    self.logger.LogWarning("[PID: %d] Terminating child." % child.pid)

    try:
      child.terminate()
    except OSError:
      pass

    wait_started = time.time()

    while not child.poll():
      if time.time() - wait_started >= wait_timeout:
        break
      time.sleep(0.1)

    return child.poll()

  def _Kill(self, child):
    """Kill the child with immediate result."""
    self.logger.LogWarning("[PID: %d] Process still alive." % child.pid)
    self.logger.LogWarning("[PID: %d] Killing child." % child.pid)
    child.kill()
    child.wait()

  def _SpawnProcess(self, cmd, command_terminator, command_timeout):
    # Create a child process executing provided command.
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE, shell=True)

    # Close stdin so the child won't be able to block on read.
    child.stdin.close()

    started_time = time.time()

    # Watch for data on process stdout, stderr.
    pipes = [child.stdout, child.stderr]

    # Put pipes into non-blocking mode.
    for pipe in pipes:
      fd = pipe.fileno()
      fd_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
      fcntl.fcntl(fd, fcntl.F_SETFL, fd_flags | os.O_NONBLOCK)

    already_terminated = False

    while pipes:
      # Maybe timeout reached?
      if command_timeout and time.time() - started_time > command_timeout:
        command_terminator.Terminate()

      # Check if terminate request was received.
      if command_terminator.IsTerminated() and not already_terminated:
        if not self._Terminate(child, command_timeout):
          self._Kill(child)
        # Don't exit the loop immediately. Firstly try to read everything that
        # was left on stdout and stderr.
        already_terminated = True

      # Wait for pipes to become ready.
      ready_pipes, _, _ = select.select(pipes, [], [], 0.1)

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
            self.DataReceivedOnOutput(data)
          elif pipe == child.stderr:
            self.DataReceivedOnError(data)

          try:
            data = os.read(fd, 4096)
          except OSError:
            # terminate loop if EWOULDBLOCK (EAGAIN) is received
            data = ""

    if not already_terminated:
      self.logger.LogOutput("Waiting for command to finish.")
      child.wait()

    return child

  def DataReceivedOnOutput(self, data):
    """Invoked when the child process wrote data to stdout."""
    self.logger.LogCommandOutput(data)

  def DataReceivedOnError(self, data):
    """Invoked when the child process wrote data to stderr."""
    self.logger.LogCommandError(data)


class CommandTerminator(object):
  def __init__(self):
    self.terminated = False

  def Terminate(self):
    self.terminated = True

  def IsTerminated(self):
    return self.terminated
