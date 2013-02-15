import threading
from automation.common import job
import machine_manager
import re
from utils import utils
from utils import logger
from utils import command_executer

JOBDIR_PREFIX = "/usr/local/google/tmp/automation/job-"

class JobExecuter(threading.Thread):

  def __init__(self, job, machines, job_manager):
    threading.Thread.__init__(self)
    self.cmd_executer = command_executer.GetCommandExecuter()
    self.job = job
    self.job_manager = job_manager
    self.machines = machines


  def FinishJobIfFailed(self, return_value, fail_message):
    if return_value == 0:
      return
    else:
      logger.GetLogger().LogError("Job failed. Exit code %s. %s"
                                  % (return_value, fail_message))
      self.job.SetStatus(job.STATUS_FAILED)
      self.job_manager.NotifyJobComplete(self.job)

  def _FormatCommand(self, command):
    ret = command
    ret.replace("$JOB_ID", str(self.job.GetID()))
###    ret.replace("$PRIMARY_MACHINE", self.job.machines[0].name)
###    mo = re.search("SECONDARY_MACHINES\[(\d+)\]", ret)
###    if mo is not None:
###      index = int(mo.group(1))
###      ret = (ret[0:mo.start()] + self.job.machines[1+index] +
###             ret[mo.end():])
    return ret

  def run(self):
    # Mark as executing 
    self.job.SetStatus(job.STATUS_EXECUTING)

    # Set job directory
    job_dir = JOBDIR_PREFIX + str(self.job.GetID())
    self.job.SetJobDir(job_dir)

    primary_machine = self.machines[0]
    self.job.SetMachine(primary_machine)

    logger.GetLogger().LogOutput("Executing job with ID '%s' on machine '%s' "
                                 "in directory '%s'" %
                                 (self.job.GetID(), self.job.GetMachine().name,
                                  self.job.GetJobDir()))

    rm_success = self.cmd_executer.RunCommand("sudo rm -rf %s" %
                                              self.job.GetJobDir(),
                                              False, primary_machine.name,
                                              primary_machine.username)
    self.FinishJobIfFailed(rm_success, "rm of old job directory Failed.")

    mkdir_success = self.cmd_executer.RunCommand("mkdir -p %s" %
                                                 self.job.GetWorkDir(),
                                                 False, primary_machine.name,
                                                 primary_machine.username)
    self.FinishJobIfFailed(mkdir_success, "mkdir of new job directory Failed.")

    for required_folder in self.job.GetRequiredFolders():
      to_folder = self.job.GetWorkDir() + "/" + required_folder.dest
      from_folder = (required_folder.job.GetWorkDir() + "/" +
                     required_folder.src)

      from_machine = required_folder.job.GetMachine().name
      from_user = required_folder.job.GetMachine().username
      to_machine = self.job.GetMachine().name
      to_user = self.job.GetMachine().username
      if from_machine == to_machine and required_folder.read_only:
        # No need to make a copy, just symlink it
        symlink_success = self.cmd_executer.RunCommand("ln -sf %s %s" %
                                                       (from_folder, to_folder),
                                                       False,
                                                       from_machine, from_user)
        self.FinishJobIfFailed(symlink_success, "Failed to create symlink to "
                               "required directory.")
      else:
        copy_success = self.cmd_executer.CopyFiles(from_folder, to_folder,
                                                   from_machine, to_machine,
                                                   from_user, to_user, True)
        self.FinishJobIfFailed(copy_success, "Failed to copy required files.")

    command = self.job.GetCommand()

    command = self._FormatCommand(command)

    command_success = (self.cmd_executer.
                       RunCommand("PS1=. TERM=linux "
                                  "source ~/.bashrc ; cd %s && %s"
                                  % (self.job.GetWorkDir(), command), False,
                                  primary_machine.name,
                                  primary_machine.username))

    self.FinishJobIfFailed(command_success, "Command failed to execute: '%s'."
                           % command)

    # If we get here, the job succeeded. 
    logger.GetLogger().LogOutput("Job completed successfully.")
    self.job.SetStatus(job.STATUS_COMPLETED)
    self.job_manager.NotifyJobComplete(self.job)



