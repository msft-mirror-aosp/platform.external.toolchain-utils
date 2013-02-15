import threading
from automation.common import job
import getpass
from utils import utils
import os
import re
import sys
from utils import logger
from utils import command_executer

JOBDIR_PREFIX = "/usr/local/google/tmp/automation/job-"

class JobExecuter(threading.Thread):

  def __init__(self, job, machines, listeners):
    threading.Thread.__init__(self)
    self.job = job
    self.job_log_root = utils.GetRoot(sys.argv[0])[0]

    # Setup log files for the job.
    job_log_file_name = "job-" + str(self.job.GetID()) + ".log"
    job_logger = logger.Logger(self.job_log_root,
                               job_log_file_name,
                               True)
    self.cmd_executer = command_executer.GetCommandExecuter(job_logger)
    self.listeners = listeners
    self.machines = machines
    self.command_terminator = command_executer.CommandTerminator()


  def _IsJobFailed(self, return_value, fail_message):
    if return_value == 0:
      return False
    else:
      logger.GetLogger().LogError("Job failed. Exit code %s. %s"
                                  % (return_value, fail_message))
      if self.command_terminator.IsTerminated():
        logger.GetLogger().LogOutput("Job '%s' was killed"
                                     % str(self.job.GetID()))
      self.job.SetStatus(job.STATUS_FAILED)
      for listener in self.listeners:
        listener.NotifyJobComplete(self.job)
      return True


  def _FormatCommand(self, command):
    ret = command
    ret = ret.replace("$JOB_ID", str(self.job.GetID()))
    ret = ret.replace("$PRIMARY_MACHINE", self.job.machines[0].name)
    while True:
      mo = re.search("\$SECONDARY_MACHINES\[(\d+)\]", ret)
      if mo is not None:
        index = int(mo.group(1))
        ret = (ret[0:mo.start()] + self.job.machines[1 + index].name +
               ret[mo.end():])
      else:
        break
    return ret

  def Kill(self):
    self.command_terminator.Terminate()

  def CleanUp(self):
    rm_success = self.cmd_executer.RunCommand("sudo rm -rf %s" %
                                              self.job.GetJobDir(),
                                              False, self.machines[0].name,
                                              self.machines[0].username)
    if rm_success != 0:
      logger.GetLogger().LogError("Cleanup failed.");


  def run(self):
    self.job.SetStatus(job.STATUS_SETUP)
    # Set job directory
    job_dir = JOBDIR_PREFIX + str(self.job.GetID())
    self.job.SetJobDir(job_dir)

    primary_machine = self.machines[0]
    self.job.SetMachines(self.machines)

    logger.GetLogger().LogOutput("Executing job with ID '%s' on machine '%s' "
                                 "in directory '%s'" %
                                 (self.job.GetID(), primary_machine.name,
                                  self.job.GetJobDir()))

    rm_success = self.cmd_executer.RunCommand("sudo rm -rf %s" %
                                              self.job.GetJobDir(),
                                              False, primary_machine.name,
                                              primary_machine.username,
                                              self.command_terminator)
    if self._IsJobFailed(rm_success, "rm of old job directory Failed."):
      return

    mkdir_command = ("mkdir -p %s && mkdir -p %s" %
                     (self.job.GetWorkDir(),
                      self.job.GetLogsDir()))
    mkdir_success = self.cmd_executer.RunCommand(mkdir_command,
                                                 False, primary_machine.name,
                                                 primary_machine.username,
                                                 self.command_terminator)
    if self._IsJobFailed(mkdir_success, "mkdir of new job directory Failed."):
      return

    self.job.SetStatus(job.STATUS_COPYING)

    for required_folder in self.job.GetRequiredFolders():
      to_folder = self.job.GetWorkDir() + "/" + required_folder.dest
      from_folder = (required_folder.job.GetWorkDir() + "/" +
                     required_folder.src)

      to_folder_parent = utils.GetRoot(to_folder)[0]
      self.cmd_executer.RunCommand("mkdir -p %s" %
                                   to_folder_parent,
                                   False, primary_machine.name,
                                   primary_machine.username,
                                   self.command_terminator)

      from_machine = required_folder.job.GetMachines()[0].name
      from_user = required_folder.job.GetMachines()[0].username
      to_machine = self.job.GetMachines()[0].name
      to_user = self.job.GetMachines()[0].username
      if from_machine == to_machine and required_folder.read_only:
        # No need to make a copy, just symlink it
        symlink_success = self.cmd_executer.RunCommand("ln -sf %s %s" %
                                                       (from_folder, to_folder),
                                                       False,
                                                       from_machine, from_user,
                                                       self.command_terminator)
        if self._IsJobFailed(symlink_success, "Failed to create symlink to "
                             "required directory."):
          return
      else:
        copy_success = self.cmd_executer.CopyFiles(from_folder, to_folder,
                                                   from_machine, to_machine,
                                                   from_user, to_user, True)
        if self._IsJobFailed(copy_success, "Failed to copy required files."):
          return

    command = self.job.GetCommand()

    command = self._FormatCommand(command)

    self.job.SetStatus(job.STATUS_RUNNING)

    command_success = (self.cmd_executer.
                       RunCommand("PS1=. TERM=linux "
                                  "source ~/.bashrc ; cd %s && %s"
                                  % (self.job.GetWorkDir(), command), False,
                                  primary_machine.name,
                                  primary_machine.username,
                                  self.command_terminator))

    if self._IsJobFailed(command_success,
                         "Command failed to execute: '%s'." % command):
      return

    # Copy results back to results directories.
    if len(self.job.GetResultsDirs()) > 0 and self.job.GetResultsDestDir():
      to_folder = self.job.GetResultsDestDir() + "/job-" + str(self.job.GetID())
      to_machine = self.job.GetResultsDestMachine()

      mkdir_success = (self.cmd_executer.RunCommand
                       ("mkdir -p %s" % to_folder, False, to_machine,
                        command_terminator=self.command_terminator))

      if self._IsJobFailed(mkdir_success, "mkdir of results directory Failed."):
        return
      for directory in self.job.GetResultsDirs():
        from_folder = self.job.GetWorkDir() + "/" + directory
        from_machine = primary_machine.name
        from_user = primary_machine.username
        copy_success = self.cmd_executer.CopyFiles(from_folder, to_folder,
                                                   from_machine, to_machine,
                                                   from_user, recursive=True)
        if self._IsJobFailed(copy_success, "Failed to copy result files."):
          return

    # If we get here, the job succeeded. 
    self.job.SetStatus(job.STATUS_COMPLETED)

    self.ShipLogs()

    for listener in self.listeners:
      listener.NotifyJobComplete(self.job)

  def ShipLogs(self):
    job_machine = self.job.GetMachines()[0]
    from_machine = os.uname()[1]
    from_folder = "%s/logs/job-%d*" % (self.job_log_root, self.job.GetID())
    to_machine = job_machine.name
    to_folder = self.job.GetLogsDir()
    user = getpass.getuser()
    copy_status = self.cmd_executer.CopyFiles(from_folder, to_folder,
                                              from_machine, to_machine,
                                              user, recursive=True)
    return copy_status
