#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from experiment_status import ExperimentStatus
from utils import logger
from utils.email_sender import EmailSender


class ActionRunner(object):
  def __init__(self, experiment):
    self._experiment = experiment
    self.l = logger.GetLogger()

  def Run(self, experiment):
    status = ExperimentStatus(experiment)
    experiment.start()
    try:
      while not experiment.complete:
        border = "=============================="
        self.l.LogOutput(border)
        self.l.LogOutput(status.GetProgressString())
        self.l.LogOutput(status.GetStatusString())
        logger.GetLogger().LogOutput(border)
        experiment.join(30)
    except KeyboardInterrupt:
      self.l.LogError("Ctrl-c pressed. Cleaning up...")
      experiment.terminate = True

  def Table(self, experiment):
    if not experiment.complete:
      # Run the experiment but only load the cached values.
      experiment.SetCacheConditions([])
      self.Run(experiment)
    if experiment.table and experiment.complete:
      self.l.LogOutput(experiment.table)

  def Email(self, experiment):
    if not experiment.complete:
      # Run the experiment but only load the cached values.
      experiment.SetCacheConditions([])
      self.Run(experiment)
    if experiment.table and experiment.complete:
      benchmark_names = []
      for benchmark_run in experiment.benchmark_runs:
        benchmark_names.append(benchmark_run.full_name)
      subject = "%s: %s" % (experiment.name, ", ".join(benchmark_names))
      EmailSender().SendEmailToUser(subject, experiment.table)

  def RunAction(self, action):
    action = action.lower()
    if action == "run":
      self.Run(self._experiment)
    elif action == "table":
      self.Table(self._experiment)
    elif action == "email":
      self.Email(self._experiment)
    elif action == "do":
      self.Run(self._experiment)
      self.Table(self._experiment)
      # Only email by default if a new run was completed.
      for benchmark_run in self._experiment.benchmark_runs:
        if not benchmark_run.cache_hit:
          self.Email(self._experiment)
    else:
      raise Exception("Invalid action.")


class MockActionRunner(ActionRunner):
  def __init__(self, experiment):
    super(MockActionRunner, self).__init__(experiment)

  def Run(self, experiment):
    self.l.LogOutput("Would run the following experiment: '%s'." %
                     experiment.name)

  def Table(self, experiment):
    self.l.LogOutput("Would print the experiment table.")

  def Email(self, experiment):
    self.l.LogOutput("Would send result email.")
