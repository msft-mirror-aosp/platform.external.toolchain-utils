#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import os
import time
from experiment_status import ExperimentStatus
from results_report import HTMLResultsReport
from results_report import TextResultsReport
from utils import logger
from utils.email_sender import EmailSender
from utils.file_utils import FileUtils


class ExperimentRunner(object):
  STATUS_TIME_DELAY = 30
  THREAD_MONITOR_DELAY = 2

  def __init__(self, experiment):
    self._experiment = experiment
    self.l = logger.GetLogger()
    self._terminated = False

  def _Run(self, experiment):
    status = ExperimentStatus(experiment)
    experiment.Run()
    last_status_time = 0
    try:
      while not experiment.IsComplete():
        if last_status_time + self.STATUS_TIME_DELAY < time.time():
          last_status_time = time.time()
          border = "=============================="
          self.l.LogOutput(border)
          self.l.LogOutput(status.GetProgressString())
          self.l.LogOutput(status.GetStatusString())
          logger.GetLogger().LogOutput(border)
        time.sleep(self.THREAD_MONITOR_DELAY)
    except KeyboardInterrupt:
      self._terminated = True
      self.l.LogError("Ctrl-c pressed. Cleaning up...")
      experiment.Terminate()

  def _PrintTable(self, experiment):
    self.l.LogOutput(TextResultsReport(experiment).GetReport())

  def _Email(self, experiment):
    # Only email by default if a new run was completed.
    send_mail = False
    for benchmark_run in experiment.benchmark_runs:
      if not benchmark_run.cache_hit:
        send_mail = True
        break
    if not send_mail:
      return

    label_names = []
    for label in experiment.labels:
      label_names.append(label.name)
    subject = "%s: %s" % (experiment.name, " vs. ".join(label_names))

    text_report = TextResultsReport(experiment).GetReport()
    text_report = "<pre style='font-size: 13px'>%s</pre>" % text_report
    html_report = HTMLResultsReport(experiment).GetReport()
    attachment = EmailSender.Attachment("report.html", html_report)
    EmailSender().SendEmail([getpass.getuser()],
                            subject,
                            text_report,
                            attachments=[attachment],
                            msg_type="html")

  def _StoreResults (self, experiment):
    if self._terminated:
      return
    results_directory = experiment.results_directory
    FileUtils().RmDir(results_directory)
    FileUtils().MkDirP(results_directory)
    self.l.LogOutput("Storing experiment file.")
    experiment_file_path = os.path.join(results_directory,
                                        "experiment.exp")
    FileUtils().WriteFile(experiment_file_path, experiment.experiment_file)

    self.l.LogOutput("Storing results report.")
    results_table_path = os.path.join(results_directory, "results.html")
    report = HTMLResultsReport(experiment).GetReport()
    FileUtils().WriteFile(results_table_path, report)

    self.l.LogOutput("Storing results of each benchmark run.")
    for benchmark_run in experiment.benchmark_runs:
      benchmark_run_name = filter(str.isalnum, benchmark_run.name)
      try:
        if benchmark_run.perf_results:
          benchmark_run_path = os.path.join(results_directory,
                                            benchmark_run_name)
          FileUtils().MkDirP(benchmark_run_path)
          FileUtils().WriteFile(os.path.join(benchmark_run_path, "perf.report"),
                                benchmark_run.perf_results.report)
          FileUtils().WriteFile(os.path.join(benchmark_run_path, "perf.out"),
                                benchmark_run.perf_results.output)
      except Exception, e:
        self.l.LogError(e)

  def Run(self):
    self._Run(self._experiment)
    self._PrintTable(self._experiment)
    if not self._terminated:
      self._StoreResults(self._experiment)
      self._Email(self._experiment)


class MockExperimentRunner(ExperimentRunner):
  def __init__(self, experiment):
    super(MockExperimentRunner, self).__init__(experiment)

  def _Run(self, experiment):
    self.l.LogOutput("Would run the following experiment: '%s'." %
                     experiment.name)

  def _PrintTable(self, experiment):
    self.l.LogOutput("Would print the experiment table.")

  def _Email(self, experiment):
    self.l.LogOutput("Would send result email.")

  def _StoreResults(self, experiment):
    self.l.LogOutput("Would store the results.")
