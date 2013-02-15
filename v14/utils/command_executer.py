import getpass
import logger
import os
import pty
import re
import select
import subprocess
import sys
import tempfile
import time
import utils

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


class CommandExecuter:
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
      if return_output:
        return [1, "", ""]
      else:
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

    while len(pipes):
      fds = select.select(pipes, [], [], 0.1)
      if command_terminator and command_terminator.IsTerminated():
        self.RunCommand("sudo kill -9 " + str(p.pid))
        wait = p.wait()
        self.logger.LogError("Command was terminated!")
        if return_output:
          return (p.wait, full_stdout, full_stderr)
        else:
          return wait
      for fd in fds[0]:
        if fd == p.stdout:
          out = os.read(p.stdout.fileno(), 16384)
          if return_output:
            full_stdout += out
          self.logger.LogCommandOutput(out)
          if out == "":
            pipes.remove(p.stdout)
        if fd == p.stderr:
          err = os.read(p.stderr.fileno(), 16384)
          if return_output:
            full_stderr += err
          self.logger.LogCommandError(err)
          if err == "":
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

      if out == err == "":
        break

    p.wait()
    os.close(pty_fds[0])
    os.close(pty_fds[1])
    if return_output:
      return (p.returncode, full_stdout, full_stderr)
    return p.returncode

  def RemoteAccessInitCommand(self, chromeos_root, machine):
    command = ""
    command += "\nset -- --remote=" + machine
    command += "\n. " + chromeos_root + "/src/scripts/common.sh"
    command += "\n. " + chromeos_root + "/src/scripts/remote_access.sh"
    command += "\nTMP=$(mktemp -d)"
    command += "\nFLAGS \"$@\" || exit 1"
    command += "\nremote_access_init"
    return command

  def WriteToTempShFile(self, contents):
    handle, command_file = tempfile.mkstemp(prefix=os.uname()[1],
                                            suffix=".sh")
    os.write(handle, "#!/bin/bash\n")
    os.write(handle, contents)
    os.close(handle)
    return command_file


  def CrosLearnBoard(self, chromeos_root, machine):
    command = self.RemoteAccessInitCommand(chromeos_root, machine)
    command += "\nlearn_board"
    command += "\necho ${FLAGS_board}"
    retval, output, err = self.RunCommand(command, True)
    self.logger.LogFatalIf(retval, "learn_board command failed")
    return output.split()[-1]

  def CrosRunCommand(self, cmd, return_output=False, machine=None,
      username=None, command_terminator=None, chromeos_root=None,
                     command_timeout=None):
    """Run a command on a chromeos box"""
    self.logger.LogFatalIf(not machine, "No machine provided!")
    self.logger.LogFatalIf(not chromeos_root, "chromeos_root not given!")
    chromeos_root = os.path.expanduser(chromeos_root)

    # Write all commands to a file.
    command_file = self.WriteToTempShFile(cmd)
    self.CopyFiles(command_file, command_file,
                   dest_machine=machine,
                   command_terminator=command_terminator,
                   chromeos_root=chromeos_root,
                   dest_cros=True,
                   recursive=False)

    command = self.RemoteAccessInitCommand(chromeos_root, machine)
    command += "\nremote_sh bash %s" % command_file
    command += "\necho \"$REMOTE_OUT\""
    retval = self.RunCommand(command, return_output,
                             command_terminator=command_terminator,
                             command_timeout=command_timeout)
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

  def ChrootRunCommand(self, chromeos_root, command, return_output=False,
                       command_terminator=None):
    handle, command_file = tempfile.mkstemp(dir=os.path.join(chromeos_root,
                                                           "src/scripts"),
                                          suffix=".sh",
                                          prefix="in_chroot_cmd")
    os.write(handle, "#!/bin/bash\n")
    os.write(handle, command)
    os.close(handle)

    os.chmod(command_file, 0777)

    with utils.WorkingDirectory(chromeos_root):
      command = "cros_sdk -- ./%s" % os.path.basename(command_file)
      ret = self.RunCommand(command, return_output,
                          command_terminator=command_terminator)
      os.remove(command_file)
      return ret


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

    if recursive:
      src = src + "/"
      dest = dest + "/"

    if src_cros == True or dest_cros == True:
      self.logger.LogFatalIf(not (src_cros ^ dest_cros), "Only one of src_cros "
                             "and desc_cros can be non-null.")
      self.logger.LogFatalIf(not chromeos_root, "chromeos_root not given!")
      if src_cros == True:
        cros_machine = src_machine
      else:
        cros_machine = dest_machine

      command = self.RemoteAccessInitCommand(chromeos_root, cros_machine)
      src_parent, src_child = utils.GetRoot(src)
      dest_parent, dest_child = utils.GetRoot(dest)
      ssh_command = ("ssh -p ${FLAGS_ssh_port}" +
                     " -o StrictHostKeyChecking=no" +
                     " -o UserKnownHostsFile=$(mktemp)" +
                     " -i $TMP_PRIVATE_KEY")
      rsync_prefix = "\nrsync -r -e \"%s\" " % ssh_command
      if dest_cros == True:
        command += rsync_prefix + "%s root@%s:%s" % (src, dest_machine, dest)
        return self.RunCommand(command,
                               machine=src_machine,
                               username=src_user,
                               command_terminator=command_terminator)
      else:
        command += rsync_prefix + "root@%s:%s %s" % (src_machine, src, dest)
        return self.RunCommand(command,
                               machine=dest_machine,
                               username=dest_user,
                               command_terminator=command_terminator)


    if dest_machine == src_machine:
      command = ("rsync -a %s %s" %
                     (src,
                      dest))
    else:
      if src_machine is None:
        src_machine = os.uname()[1]
        src_user = getpass.getuser()
      command = ("rsync -a %s@%s:%s %s" %
                     (src_user, src_machine, src,
                      dest))
    return self.RunCommand(command,
                           machine=dest_machine,
                           username=dest_user,
                           command_terminator=command_terminator)


class MockCommandExecuter(CommandExecuter):
  def __init__(self, logger_to_set=None):
    if logger is not None:
      self.logger = logger_to_set
    else:
      self.logger = logger.GetLogger()

  def RunCommand(self, cmd, return_output=False, machine=None, username=None,
                 command_terminator=None):
    cmd = str(cmd)
    if machine is None:
      machine = "localhost"
    if username is None:
      username = "current"
    logger.GetLogger().LogCmd("(Mock) " + cmd, machine, username)
    return 0


class CommandTerminator:
  def __init__(self):
    self.terminated = False

  def Terminate(self):
    self.terminated = True

  def IsTerminated(self):
    return self.terminated
