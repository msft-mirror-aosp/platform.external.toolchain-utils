#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import time
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
    while not experiment.complete:
      border = "=============================="
      self.l.LogOutput(border)
      self.l.LogOutput(status.GetProgressString())
      self.l.LogOutput(status.GetStatusString())
      logger.GetLogger().LogOutput(border)
      time.sleep(30)

  def Table(self, experiment):
    if experiment.success:
      self.l.LogOutput(experiment.table)
    else:
      self.l.LogError("Experiment did not complete successfully.")

  def Email(self, experiment):
    if experiment.success:
      benchmark_names = []
      for benchmark_run in experiment.benchmark_runs:
        benchmark_names.append(benchmark_run.full_name)
      subject = "%s: %s" % (experiment.board, ", ".join(benchmark_names))
      EmailSender().SendEmailToUser(subject, experiment.table)
    else:
      self.l.LogError("Experiment did not complete successfully.")

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
