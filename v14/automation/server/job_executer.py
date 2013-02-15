import threading
from automation.common import job
import report_generator
from utils import utils
import re
from utils import logger
from utils import command_executer

WORKDIR_PREFIX = "/usr/local/google/tmp/automation/job-"

class JobExecuter(threading.Thread):

  def __init__(self, job, machines, listeners):
    threading.Thread.__init__(self)
    self.job = job
    self.listeners = listeners
    self.machines = machines

    # Set job directory
    work_dir = WORKDIR_PREFIX + str(self.job.GetID())
    self.job.SetWorkDir(work_dir)
    self.job.SetHomeDir(self.job.GetGroup().GetHomeDir() +
                        "/job-" + str(self.job.GetID()))
    self.job_log_root = self.job.GetLogsDir()

    # Setup log files for the job.
    self.job_log_file_name = "job-" + str(self.job.GetID()) + ".log"
    self.job_logger = logger.Logger(self.job_log_root,
                               self.job_log_file_name,
                               True, subdir="")
    self.cmd_executer = (command_executer.GetCommandExecuter
                         (self.job_logger, self.job.GetDryRun()))
    self.command_terminator = command_executer.CommandTerminator()


  def _IsJobFailed(self, return_value, fail_message):
    if return_value == 0:
      return False
    else:
      output_string = ""
      error_string = ("Job failed. Exit code %s. %s" %
                      (return_value, fail_message))
      if self.command_terminator.IsTerminated():
        output_string = ("Job %s was killed"
                         % str(self.job.GetID()))
      self.job_logger.LogError(error_string)
      self.job_logger.LogOutput(output_string)

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

  def CleanUpWorkDir(self, ct=None):
    rm_success = self.cmd_executer.RunCommand("sudo rm -rf %s" %
                                              self.job.GetWorkDir(),
                                              False, self.machines[0].name,
                                              self.machines[0].username,
                                              command_terminator=ct)
    if rm_success != 0:
      self.job_logger.LogError("Cleanup workdir failed.");
    return rm_success

  def CleanUpHomeDir(self, ct=None):
    rm_success = self.cmd_executer.RunCommand("rm -rf %s" %
                                              self.job.GetHomeDir(),
                                              False, command_terminator=ct)
    if rm_success != 0:
      self.job_logger.LogError("Cleanup homedir failed.");
    return rm_success

  def run(self):
    self.job.SetStatus(job.STATUS_SETUP)

    primary_machine = self.machines[0]
    self.job.SetMachines(self.machines)

    self.job_logger.LogOutput("Executing job with ID '%s' on machine '%s' "
                                 "in directory '%s'" %
                                 (self.job.GetID(), primary_machine.name,
                                  self.job.GetWorkDir()))

    self.CleanUpWorkDir(self.command_terminator)

    mkdir_command = ("mkdir -p %s && mkdir -p %s && mkdir -p %s" %
                     (self.job.GetWorkDir(),
                      self.job.GetLogsDir(),
                      self.job.GetTestResultsDirSrc()))
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

    # Copy test results back to directory
    to_folder = self.job.GetHomeDir()
    from_folder = self.job.GetTestResultsDirSrc()
    from_user = primary_machine.username
    from_machine = primary_machine.name
    copy_success = self.cmd_executer.CopyFiles(from_folder, to_folder,
                                               from_machine, None,
                                               from_user, recursive=False)
    if self._IsJobFailed(copy_success, "Failed to copy results."):
      return

    # Generate diff of baseline and results.csv
    report = None
    try:
      results_filename = self.job.GetTestResultsFile()
      baseline_filename = self.job.GetBaselineFile()
      if not baseline_filename:
        self.job_logger.LogWarning("Baseline not specified.")
      else:
        report = report_generator.GenerateResultsReport(baseline_filename,
                                                        results_filename)
    except StandardError, e:
      self.job_logger.LogWarning("Couldn't generate report")

    if report:
      try:
        report_file = open(self.job.GetTestReportFile(), "w")
        report_file.write(report.GetReport())

        summary_file = open(self.job.GetTestReportSummaryFile(), "w")
        summary_file.write(report.GetSummary())
      except IOError, e:
        self.job_logger.LogWarning("Could not write results report")
      finally:
        if report_file:
          report_file.close()
        if summary_file:
          summary_file.close()

    # If we get here, the job succeeded. 
    self.job.SetStatus(job.STATUS_SUCCEEDED)
    self.job_logger.Flush()

    for listener in self.listeners:
      listener.NotifyJobComplete(self.job)

