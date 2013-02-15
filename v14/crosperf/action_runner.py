#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from experiment_status import ExperimentStatus
from results_report import HTMLResultsReport
from results_report import TextResultsReport
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

  def PrintTable(self, experiment):
    if experiment.complete:
      self.l.LogOutput(TextResultsReport(experiment).GetReport())

  def Email(self, experiment):
    # Only email by default if a new run was completed.
    send_mail = False
    for benchmark_run in experiment.benchmark_runs:
      if not benchmark_run.cache_hit:
        send_mail = True
        break
    if not send_mail:
      return

    if experiment.complete:
      label_names = []
      for label in experiment.labels:
        label_names.append(label.name)
      subject = "%s: %s" % (experiment.name, " vs. ".join(label_names))

      text_report = TextResultsReport(experiment).GetReport()
      text_report = "<pre style='font-size: 13px'>%s</pre>" % text_report
      html_report = HTMLResultsReport(experiment).GetReport()
      attachment = EmailSender.Attachment("report.html", html_report)
      EmailSender().SendEmailToUser(subject,
                                    text_report,
                                    attachments=[attachment],
                                    msg_type="html")

  def StoreResults (self, experiment):
    experiment.StoreResults()

  def RunActions(self):
    self.Run(self._experiment)
    self.PrintTable(self._experiment)
    self.Email(self._experiment)
    self.StoreResults(self._experiment)


class MockActionRunner(ActionRunner):
  def __init__(self, experiment):
    super(MockActionRunner, self).__init__(experiment)

  def Run(self, experiment):
    self.l.LogOutput("Would run the following experiment: '%s'." %
                     experiment.name)

  def PrintTable(self, experiment):
    self.l.LogOutput("Would print the experiment table.")

  def Email(self, experiment):
    self.l.LogOutput("Would send result email.")

  def StoreResults(self, experiment):
    self.l.LogOutput("Would store the results.")
