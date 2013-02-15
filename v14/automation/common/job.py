#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
#

"""A module for a job in the infrastructure."""


__author__ = 'raymes@google.com (Raymes Khoury)'


import os.path
import re

from automation.common import state_machine

STATUS_NOT_EXECUTED = 'NOT_EXECUTED'
STATUS_SETUP = 'SETUP'
STATUS_COPYING = 'COPYING'
STATUS_RUNNING = 'RUNNING'
STATUS_SUCCEEDED = 'SUCCEEDED'
STATUS_FAILED = 'FAILED'


class FolderDependency(object):
  def __init__(self, job, src, dest=None):
    if not dest:
      dest = src

    # TODO(kbaclawski): rename to producer
    self.job = job
    self.src = src
    self.dest = dest
    self.read_only = dest != src


class JobStateMachine(state_machine.BasicStateMachine):
  state_machine = {
      STATUS_NOT_EXECUTED: [STATUS_SETUP],
      STATUS_SETUP: [STATUS_COPYING, STATUS_FAILED],
      STATUS_COPYING: [STATUS_RUNNING, STATUS_FAILED],
      STATUS_RUNNING: [STATUS_SUCCEEDED, STATUS_FAILED]}

  final_states = [STATUS_SUCCEEDED, STATUS_FAILED]


class JobFailure(Exception):
  def __init__(self, message, exit_code):
    Exception.__init__(self, message)
    self.exit_code = exit_code


class Job(object):
  """A class representing a job whose commands will be executed."""

  def __init__(self, label, command, baseline=''):
    self._state = JobStateMachine(STATUS_NOT_EXECUTED)
    self.children = []
    self.parents = []
    self.machine_dependencies = []
    self.folder_dependencies = []
    self.id = 0
    self.work_dir = ''
    self.home_dir = ''
    self.machines = []
    self.command = command
    self._has_primary_machine_spec = False
    self.group = None
    self.dry_run = None
    self.label = label
    self.baseline = baseline

  def _state_get(self):
    return self._state

  def _state_set(self, new_state):
    self._state.Change(new_state)

  status = property(_state_get, _state_set)

  @property
  def timeline(self):
    return self._state.timeline

  def __str__(self):
    res = []
    res.append('%d' % self.id)
    res.append('Children:')
    res.extend(['%d' % child.id for child in self.children])
    res.append('Parents:')
    res.extend(['%d' % parent.id for parent in self.parents])
    res.append('Machines:')
    res.extend(['%s' % machine for machine in self.machines])
    res.append(self.PrettyFormatCommand())
    res.append('%s' % self.status)
    res.append(self.timeline.GetTransitionEventReport())
    return '\n'.join(res)

  def GetCommand(self):
    substitutions = [
        ('$JOB_ID', str(self.id)),
        ('$JOB_TMP', self.work_dir),
        ('$JOB_HOME', self.home_dir),
        ('$PRIMARY_MACHINE', self.machine.hostname)]

    if len(self.machines) > 1:
      for num, machine in enumerate(self.machines[1:]):
        substitutions.append(
            ("$SECONDARY_MACHINES[%d]" % num, machine.hostname))

    cmd = str(self.command)

    for pattern, replacement in substitutions:
      cmd = cmd.replace(pattern, replacement)

    return cmd

  def PrettyFormatCommand(self):
    # TODO(kbaclawski): This method doesn't belong here, but rather to
    # non existing Command class. If one is created then PrettyFormatCommand
    # shall become its method.
    output = self.GetCommand()
    output = re.sub('\{ ', '', output)
    output = re.sub('; \}', '', output)
    output = re.sub('\} ', '\n', output)
    output = re.sub('\s*&&\s*', '\n', output)
    return output

  def DependsOnFolder(self, dependency):
    self.folder_dependencies.append(dependency)
    self.DependsOn(dependency.job)

  @property
  def results_dir(self):
    return os.path.join(self.work_dir, 'results')

  @property
  def logs_dir(self):
    return os.path.join(self.home_dir, 'logs')

  @property
  def log_out_filename(self):
    return os.path.join(self.logs_dir, 'job-%s.log.out' % self.id)

  @property
  def log_cmd_filename(self):
    return os.path.join(self.logs_dir, 'job-%s.log.cmd' % self.id)

  @property
  def log_err_filename(self):
    return os.path.join(self.logs_dir, 'job-%s.log.err' % self.id)

  @property
  def machine(self):
    return self.machines[0]

  def DependsOn(self, job):
    """Specifies Jobs to be finished before this job can be launched."""
    if job not in self.children:
      self.children.append(job)
    if self not in job.parents:
      job.parents.append(self)

  @property
  def is_ready(self):
    """Check that all our dependencies have been executed."""
    return all(child.status == STATUS_SUCCEEDED for child in self.children)

  def DependsOnMachine(self, machine_spec, primary=True):
    # Job will run on arbitrarily chosen machine specified by
    # MachineSpecification class instances passed to this method.
    if primary:
      if self._has_primary_machine_spec:
        raise RuntimeError('Only one primary machine specification allowed.')
      self._has_primary_machine_spec = True
      self.machine_dependencies.insert(0, machine_spec)
    else:
      self.machine_dependencies.append(machine_spec)
