#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import re
import threading

from automation.common import job
import report_generator
from utils import command_executer
from utils import logger

WORKDIR_PREFIX = "/usr/local/google/tmp/automation"


class JobExecuter(threading.Thread):
  def __init__(self, job_to_execute, machines, listeners):
    threading.Thread.__init__(self)

    self.job = job_to_execute
    self.listeners = listeners
    self.machines = machines

    job_dir = "job-%d" % self.job.id

    # Set job directory
    self.job.work_dir = os.path.join(WORKDIR_PREFIX, job_dir)
    self.job.home_dir = os.path.join(self.job.group.home_dir, job_dir)
    self.job_log_root = self.job.logs_dir

    # Setup log files for the job.
    self.job_log_file_name = "job-%s.log" % self.job.id
    self.job_logger = logger.Logger(self.job_log_root, self.job_log_file_name,
                                    True, subdir="")
    self._executer = command_executer.GetCommandExecuter(self.job_logger,
                                                         self.job.dry_run)
    self._terminator = command_executer.CommandTerminator()

  def _FormatCommand(self, command):
    ret = str(command)
    ret = ret.replace("$JOB_ID", "%s" % self.job.id)
    ret = ret.replace("$JOB_TMP", self.job.work_dir)
    ret = ret.replace("$JOB_HOME", self.job.home_dir)
    ret = ret.replace("$PRIMARY_MACHINE", self.job.machines[0].hostname)
    while True:
      mo = re.search("\$SECONDARY_MACHINES\[(\d+)\]", ret)
      if mo:
        index = int(mo.group(1))
        ret = "%s%s%s" % (ret[0:mo.start()],
                          self.job.machines[1 + index].hostname,
                          ret[mo.end():])
      else:
        break
    return ret

  def Kill(self):
    self._terminator.Terminate()

  def CleanUpWorkDir(self, ct=None):
    command = "sudo rm -rf %s" % self.job.work_dir

    exit_code = self._executer.RunCommand(command, False,
                                          self.machines[0].hostname,
                                          self.machines[0].username,
                                          command_terminator=ct)
    if exit_code:
      raise job.JobFailure("Cleanup workdir failed.", exit_code)

  def CleanUpHomeDir(self, ct=None):
    command = "rm -rf %s" % self.job.home_dir

    exit_code = self._executer.RunCommand(command, False, command_terminator=ct)

    if exit_code:
      raise job.JobFailure("Cleanup homedir failed.", exit_code)

  def _RunCommand(self, command, machine, fail_msg):
    exit_code = self._executer.RunCommand(command, False, machine.hostname,
                                          machine.username, self._terminator)
    if exit_code:
      raise job.JobFailure(fail_msg, exit_code)

  def _PrepareJobFolders(self, machine):
    command = " && ".join(["mkdir -p %s" % self.job.work_dir,
                           "mkdir -p %s" % self.job.logs_dir,
                           "mkdir -p %s" % self.job.test_results_dir_src])
    self._RunCommand(command, machine, "Creating new job directory failed.")

  def _SatisfyFolderDependencies(self, machine):
    for dependency in self.job.folder_dependencies:
      to_folder = os.path.join(self.job.work_dir, dependency.dest)
      from_folder = os.path.join(dependency.job.work_dir, dependency.src)
      to_folder_parent = os.path.dirname(os.path.realpath(to_folder))

      command = "mkdir -p %s" % to_folder_parent

      self._RunCommand(command, machine, "Creating directory for results "
                       "produced by dependencies failed.")

      from_machine = dependency.job.machines[0]
      to_machine = self.job.machines[0]

      if from_machine == to_machine and dependency.read_only:
        # No need to make a copy, just symlink it
        command = "ln -sf %s %s" % (from_folder, to_folder)
        self._RunCommand(command, from_machine, "Failed to create symlink to "
                         "required directory.")
      else:
        exit_code = self._executer.CopyFiles(from_folder, to_folder,
                                             from_machine.hostname,
                                             to_machine.hostname,
                                             from_machine.username,
                                             to_machine.username,
                                             recursive=True)
        if exit_code:
          raise job.JobFailure("Failed to copy required files.", exit_code)

  def _LaunchJobCommand(self, machine):
    command = self._FormatCommand(self.job.command)
    wrapper = " ; ".join(["PS1=. TERM=linux source ~/.bashrc",
                          "cd %s && %s" % (self.job.work_dir, command)])

    self._RunCommand(wrapper, machine,
                     "Command failed to execute: '%s'." % command)

  def _CopyJobResults(self, machine):
    """Copy test results back to directory."""

    to_folder = self.job.home_dir
    from_folder = self.job.test_results_dir_src
    from_user = machine.username
    from_machine = machine.hostname

    exit_code = self._executer.CopyFiles(from_folder, to_folder, from_machine,
                                         None, from_user, recursive=False)
    if exit_code:
      raise job.JobFailure("Failed to copy results.", exit_code)

  def _GenerateJobReport(self):
    """Generate diff of baseline and results.csv."""

    results_filename = self.job.test_results_filename
    baseline_filename = self.job.baseline_filename

    if not baseline_filename:
      self.job_logger.LogWarning("Baseline not specified.")

    try:
      report = report_generator.GenerateResultsReport(baseline_filename,
                                                      results_filename)
    except IOError:
      self.job_logger.LogWarning("Couldn't generate report")
    else:
      try:
        with open(self.job.test_report_filename, "w") as report_file:
          report_file.write(report.GetReport())

        with open(self.job.test_report_summary_filename, "w") as summary_file:
          summary_file.write(report.GetSummary())
      except IOError:
        self.job_logger.LogWarning("Could not write results report")

  def run(self):
    self.job.status = job.STATUS_SETUP

    self.job.machines = self.machines

    primary_machine = self.machines[0]

    self.job_logger.LogOutput("Executing job with ID '%s' on machine '%s' in "
                              "directory '%s'" % (self.job.id,
                                                  primary_machine.hostname,
                                                  self.job.work_dir))

    try:
      self.CleanUpWorkDir(self._terminator)

      self._PrepareJobFolders(primary_machine)

      self.job.status = job.STATUS_COPYING

      self._SatisfyFolderDependencies(primary_machine)

      self.job.status = job.STATUS_RUNNING

      self._LaunchJobCommand(primary_machine)
      self._CopyJobResults(primary_machine)

      # If we get here, the job succeeded.
      self.job.status = job.STATUS_SUCCEEDED
    except job.JobFailure as ex:
      self.job_logger.LogError("Job failed. Exit code %s. %s" % (ex.exit_code,
                                                                 ex.message))
      if self._terminator.IsTerminated():
        self.job_logger.LogOutput("Job %s was killed" % self.job.id)

      self.job.status = job.STATUS_FAILED

    self._GenerateJobReport()
    self.job_logger.Flush()

    for listener in self.listeners:
      listener.NotifyJobComplete(self.job)
