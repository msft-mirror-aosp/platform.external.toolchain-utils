#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

import os.path
import re
import threading

from automation.common import command as cmd
from automation.common import command_executer
from automation.common import job


class JobExecuter(threading.Thread):
  def __init__(self, job_to_execute, machines, listeners):
    threading.Thread.__init__(self)

    assert machines

    self.job = job_to_execute
    self.listeners = listeners
    self.machines = machines

    self._executer = command_executer.GetCommandExecuter(
        self.job.logger, self.job.dry_run)
    self._terminator = command_executer.CommandTerminator()

  def _FormatCommand(self, command):
    ret = str(command)
    ret = ret.replace("$JOB_ID", "%s" % self.job.id)
    ret = ret.replace("$JOB_TMP", self.job.work_dir)
    ret = ret.replace("$JOB_HOME", self.job.home_dir)
    ret = ret.replace("$PRIMARY_MACHINE", self.job.machine.hostname)
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

  def _RunRemotely(self, command, fail_msg):
    exit_code = self._executer.RunCommand(command,
                                          self.job.machine.hostname,
                                          self.job.machine.username,
                                          command_terminator=self._terminator,
                                          command_timeout=18000)
    if exit_code:
      raise job.JobFailure(fail_msg, exit_code)

  def _RunLocally(self, command, fail_msg):
    exit_code = self._executer.RunCommand(command,
                                          command_terminator=self._terminator,
                                          command_timeout=18000)
    if exit_code:
      raise job.JobFailure(fail_msg, exit_code)

  def Kill(self):
    self._terminator.Terminate()

  def CleanUpWorkDir(self):
    self._RunRemotely(
        cmd.RmTree(self.job.work_dir), "Cleanup workdir failed.")

  def CleanUpHomeDir(self):
    self._RunLocally(
        cmd.RmTree(self.job.home_dir), "Cleanup homedir failed.")

  def _PrepareJobFolders(self):
    self._RunRemotely(
        cmd.MakeDir(self.job.work_dir, self.job.logs_dir, self.job.results_dir),
        "Creating new job directory failed.")

  def _SatisfyFolderDependencies(self):
    for dependency in self.job.folder_dependencies:
      to_folder = os.path.join(self.job.work_dir, dependency.dest)
      from_folder = os.path.join(dependency.job.work_dir, dependency.src)
      from_machine = dependency.job.machine

      if from_machine == self.job.machine and dependency.read_only:
        # No need to make a copy, just symlink it
        self._RunRemotely(
            cmd.MakeSymlink(from_folder, to_folder),
            "Failed to create symlink to required directory.")
      else:
        self._RunRemotely(
            cmd.RemoteCopyFrom(from_machine.hostname, from_folder, to_folder,
                               username=from_machine.username),
            "Failed to copy required files.")

  def _LaunchJobCommand(self):
    command = self._FormatCommand(self.job.command)

    self._RunRemotely("%s; %s" % ("PS1=. TERM=linux source ~/.bashrc",
                                  cmd.Wrapper(command, cwd=self.job.work_dir)),
                      "Command failed to execute: '%s'." % command)

  def _CopyJobResults(self):
    """Copy test results back to directory."""
    self._RunLocally(
        cmd.RemoteCopyFrom(self.job.machine.hostname,
                           self.job.results_dir,
                           self.job.home_dir,
                           username=self.job.machine.username),
        "Failed to copy results.")

  def run(self):
    self.job.status = job.STATUS_SETUP
    self.job.machines = self.machines
    self.job.logger.LogOutput(
        "Executing job with ID '%s' on machine '%s' in directory '%s'" % (
            self.job.id, self.job.machine.hostname, self.job.work_dir))

    try:
      self.CleanUpWorkDir()

      self._PrepareJobFolders()

      self.job.status = job.STATUS_COPYING

      self._SatisfyFolderDependencies()

      self.job.status = job.STATUS_RUNNING

      self._LaunchJobCommand()
      self._CopyJobResults()

      # If we get here, the job succeeded.
      self.job.status = job.STATUS_SUCCEEDED
    except job.JobFailure as ex:
      self.job.logger.LogError(
          "Job failed. Exit code %s. %s" % (ex.exit_code, ex.message))
      if self._terminator.IsTerminated():
        self.job.logger.LogOutput("Job %s was killed" % self.job.id)

      self.job.status = job.STATUS_FAILED

    self.job.logger.Flush()

    for listener in self.listeners:
      listener.NotifyJobComplete(self.job)
