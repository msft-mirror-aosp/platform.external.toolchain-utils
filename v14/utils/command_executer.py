import select
import subprocess
import sys
import os
import logger

command_executer = None


def InitCommandExecuter(mock=False):
  global command_executer
  if mock:
    command_executer = MockCommandExecuter()
  else:
    command_executer = CommandExecuter()


def GetCommandExecuter():
  if command_executer is None:
    InitCommandExecuter()
  return command_executer


class MockCommandExecuter:
  def __init__(self):
    self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False):
    pass

  def RunCommands(self, cmdlist, return_output=False):
    cmd = " ; " .join(cmdlist)
    return self.RunCommand(cmd, return_output)

  def CopyFiles(self, src, dest, src_machine="", dest_machine="", recursive=True):
    pass

  def RunCommandOverSSH(self, cmd, machine):
    pass

  def RunCommandsOverSSH(self, cmds, machine):
    pass

  def AtomicMkdir(self, newdir):
    pass


class CommandExecuter:
  def __init__(self):
    self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False):
    """Run a command."""
    cmdlist = ["bash", "-c", cmd]
    self.logger.Logcmd(cmdlist)

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
          out = os.read(p.stdout.fileno(), 256)
          if return_output:
            full_stdout += out
          self.logger.LogCommandOutput(out)
        if fd == p.stderr:
          err = os.read(p.stderr.fileno(), 256)
          if return_output:
            full_stderr += err
          self.logger.LogCommandError(err)

      if out == err == "":
        break

    p.wait()
    if return_output:
      return (p.returncode, full_stdout, full_stderr)
    return p.returncode

  def RunCommands(self, cmdlist, return_output=False):
    cmd = " ; " .join(cmdlist)
    return self.RunCommand(cmd, return_output)

  def CopyFiles(self, src, dest, src_machine="", dest_machine="", recursive=True):
    pass

  def RunCommandOverSSH(self, cmd, machine):
    pass

  def RunCommandsOverSSH(self, cmds, machine):
    pass

