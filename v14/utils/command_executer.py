import select
import subprocess
import sys
import os
import logger
import utils
import re

dry_run = False


def InitCommandExecuter(mock=False):
  global dry_run
  dry_run = mock


def GetCommandExecuter(logger_to_set=None):
  if dry_run:
    return MockCommandExecuter(logger_to_set)
  else:
    return CommandExecuter(logger_to_set)


class CommandExecuter:
  def __init__(self, logger_to_set=None):
    if logger_to_set is not None:
      self.logger = logger_to_set
    else:
      self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False, machine=None,
                 username=None, command_terminator=None):
    """Run a command."""

    self.logger.LogCmd(cmd, machine, username)
    if command_terminator and command_terminator.IsTerminated():
      self.logger.LogError("Command was terminated!")
      return 1

    if machine is not None:
      user = ""
      if username is not None:
        user = username + "@"
      cmd = "ssh %s%s -- bash <<\EOF\n%s\nEOF" % (user, machine, cmd)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=sys.stdin, shell=True)

    full_stdout = ""
    full_stderr = ""

    # Pull output from pipes, send it to file/stdout/string
    out = err = None
    while True:
      fds = select.select([p.stdout, p.stderr], [], [], 0.1)
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
        if fd == p.stderr:
          err = os.read(p.stderr.fileno(), 16384)
          if return_output:
            full_stderr += err
          self.logger.LogCommandError(err)

      if out == err == "":
        break

    p.wait()
    if return_output:
      return (p.returncode, full_stdout, full_stderr)
    return p.returncode

  def RemoteAccessInitCommand(self, chromeos_root, machine):
    command = ""
    command += "\nset -- --remote=" + machine
    command += "\n. " + chromeos_root + "/src/scripts/common.sh"
    command += "\n. " + chromeos_root + "/src/scripts/remote_access.sh"
    command += "\nTMP=/tmp"
    command += "\nFLAGS \"$@\" || exit 1"
    command += "\nremote_access_init"
    return command


  def CrosLearnBoard(self, chromeos_root, machine):
    command = self.RemoteAccessInitCommand(chromeos_root, machine)
    command += "\nlearn_board"
    command += "\necho ${FLAGS_board}"
    retval, output, err = self.RunCommand(command, True)
    utils.AssertTrue(retval == 0)
    return output.split()[-1]

  def CrosRunCommand(self, cmd, return_output=False, machine=None,
      username=None, command_terminator=None, chromeos_root=None):
    """Run a command on a chromeos box"""
    utils.AssertTrue(machine is not None, "Machine was none!")
    utils.AssertTrue(chromeos_root is not None, "chromeos_root not given!")
    chromeos_root=os.path.expanduser(chromeos_root)
    command = self.RemoteAccessInitCommand(chromeos_root, machine)
    command += "\nremote_sh " + cmd
    command += "\necho \"$REMOTE_OUT\""
    retval = self.RunCommand(command, return_output)
    if return_output:
      connect_signature = ("Initiating first contact with remote host\n" +
                           "Connection OK\n")
      connect_signature_re = re.compile(connect_signature)
      modded_return = []
      for r in retval:
        modded_return.append(r)
      modded_return[1] = connect_signature_re.sub("", modded_return[1])
      return modded_return
    return retval

  def RunCommands(self, cmdlist, return_output=False, machine=None,
                  username=None, command_terminator=None):
    cmd = " ;\n" .join(cmdlist)
    return self.RunCommand(cmd, return_output, machine, username,
                           command_terminator)

  def CopyFiles(self, src, dest, src_machine=None, dest_machine=None,
                src_user=None, dest_user=None, recursive=True,
                command_terminator=None,
                chromeos_root=None, src_cros=False, dest_cros=False):
    src = os.path.expanduser(src)
    dest = os.path.expanduser(dest)

    recurse = ""
    if recursive:
      recurse = "-r"

    if src_cros == True or dest_cros == True:
      utils.AssertTrue(src_cros ^ dest_cros)
      utils.AssertTrue(chromeos_root is not None)
      if src_cros == True:
        cros_machine = src_machine
      else:
        cros_machine = dest_machine

      command = self.RemoteAccessInitCommand(chromeos_root, cros_machine)
      src_parent, src_child = utils.GetRoot(src)
      dest_parent, dest_child = utils.GetRoot(dest)
      if dest_cros == True:
        if recursive:
          dest_parent = dest
        command += "\ncd " + src_parent
        command += ("\ntar zcvf - " + src_child +
                    " | remote_sh 'cd " + dest_parent + "; tar zxvf - '")
      else:
        command += ("\nremote_sh (cd " + src_parent + "; tar zcvf - " +
                    src_child + ") | (cd " + dest_parent + "; tar zxvf -)")

      command += "\necho $REMOTE_OUT"
      return self.RunCommand(command, command_terminator=command_terminator)

    if src_user is None:
      src_user = ""
    else:
      src_user += "@"
    if dest_user is None:
      dest_user = ""
    else:
      dest_user += "@"

    if src_machine is None:
      # Assume local
      src_machine = ""
      src_user = ""
    else:
      src_machine += ":"

    if dest_machine is None:
      # Assume local
      dest_machine = ""
      dest_user = ""
    else:
      dest_machine += ":"

    return self.RunCommand("scp %s %s%s%s %s%s%s"
                           % (recurse, src_user, src_machine, src,
                              dest_user, dest_machine, dest),
                           command_terminator=command_terminator)


class MockCommandExecuter(CommandExecuter):
  def __init__(self, logger_to_set=None):
    if logger is not None:
      self.logger = logger_to_set
    else:
      self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False, machine=None, username=None,
                 command_terminator=None):
    if machine is None:
      machine = "localhost"
    if username is None:
      username = "current"
    logger.GetLogger().LogCmd("(Mock)" + cmd, machine, username)
    return 0


class CommandTerminator:
  def __init__(self):
    self.terminated = False

  def Terminate(self):
    self.terminated = True

  def IsTerminated(self):
    return self.terminated
