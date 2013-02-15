#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
#

import os
import pty
import select
import subprocess
import time

from automation.common import logger

mock_default = False


def InitCommandExecuter(mock=False):
  global mock_default
  # Whether to default to a mock command executer or not
  mock_default = mock


def GetCommandExecuter(logger_to_set=None, mock=False):
  # If the default is a mock executer, always return one.
  if mock_default or mock:
    return MockCommandExecuter(logger_to_set)
  else:
    return CommandExecuter(logger_to_set)


class CommandExecuter(object):
  def __init__(self, logger_to_set=None):
    if logger_to_set is not None:
      self.logger = logger_to_set
    else:
      self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False, machine=None,
                 username=None, command_terminator=None,
                 command_timeout=None,
                 terminated_timeout=10):
    """Run a command."""

    cmd = str(cmd)

    self.logger.LogCmd(cmd, machine, username)
    if command_terminator and command_terminator.IsTerminated():
      self.logger.LogError("Command was terminated!")
      return 1

    if machine is not None:
      user = ""
      if username is not None:
        user = username + "@"
      cmd = "ssh -t -t %s%s -- '%s'" % (user, machine, cmd)

    pty_fds = pty.openpty()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=pty_fds[0], shell=True)

    full_stdout = ""
    full_stderr = ""

    # Pull output from pipes, send it to file/stdout/string
    out = err = None
    pipes = [p.stdout, p.stderr]

    terminated_time = None
    started_time = time.time()

    while pipes:
      fds = select.select(pipes, [], [], 0.1)
      if command_terminator and command_terminator.IsTerminated():
        self.RunCommand("sudo kill -9 " + str(p.pid))
        wait = p.wait()
        self.logger.LogError("Command was terminated!")
        return wait
      for fd in fds[0]:
        if fd == p.stdout:
          out = os.read(p.stdout.fileno(), 16384)
          if return_output:
            full_stdout += out
          self.logger.LogCommandOutput(out)
          if not out:
            pipes.remove(p.stdout)
        if fd == p.stderr:
          err = os.read(p.stderr.fileno(), 16384)
          if return_output:
            full_stderr += err
          self.logger.LogCommandError(err)
          if not err:
            pipes.remove(p.stderr)

      if p.poll() is not None:
        if terminated_time is None:
          terminated_time = time.time()
        elif (terminated_timeout is not None and
              time.time() - terminated_time > terminated_timeout):
          m = ("Timeout of %s seconds reached since process termination."
               % terminated_timeout)
          self.logger.LogWarning(m)
          break

      if (command_timeout is not None and
          time.time() - started_time > command_timeout):
        m = ("Timeout of %s seconds reached since process started."
             % command_timeout)
        self.logger.LogWarning(m)
        self.RunCommand("kill %d || sudo kill %d || sudo kill -9 %d" %
                        (p.pid, p.pid, p.pid))
        break

      if not out and not err:
        break

    p.wait()
    os.close(pty_fds[0])
    os.close(pty_fds[1])
    if return_output:
      return (p.returncode, full_stdout, full_stderr)
    return p.returncode

  def CopyFiles(self, src, dest, src_machine=None, dest_machine=None,
                src_user=None, dest_user=None, recursive=True,
                command_terminator=None):
    src = os.path.expanduser(src)
    dest = os.path.expanduser(dest)

    if recursive:
      src += "/"
      dest += "/"

    if dest_machine == src_machine:
      command = "rsync -a %s %s" % (src, dest)
    else:
      if not src_machine:
        src_machine = os.uname()[1]
        src_user = os.getlogin()
      command = "rsync -a %s@%s:%s %s" % (src_user, src_machine, src, dest)

    return self.RunCommand(command,
                           machine=dest_machine,
                           username=dest_user,
                           command_terminator=command_terminator)


class MockCommandExecuter(CommandExecuter):
  def RunCommand(self, cmd, return_output=False, machine=None,
                 username=None, command_terminator=None,
                 command_timeout=None,
                 terminated_timeout=10):
    cmd = str(cmd)
    if machine is None:
      machine = "localhost"
    if username is None:
      username = "current"
    logger.GetLogger().LogCmd("(Mock) " + cmd, machine, username)
    return 0


class CommandTerminator(object):
  def __init__(self):
    self.terminated = False

  def Terminate(self):
    self.terminated = True

  def IsTerminated(self):
    return self.terminated
