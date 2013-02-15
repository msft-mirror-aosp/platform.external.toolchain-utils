#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The driver script for running performance benchmarks on ChromeOS.

Current actions:
RUN: Run the benchmark on the device.
TABLE: Display a table of performance results.
"""

import optparse
import os
import sys
import time
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from experiment_status import ExperimentStatus
from utils import logger
from utils.email_sender import EmailSender


DEFAULT_ACTION = "do"
l = logger.GetLogger()


def Usage(reason):
  """Return script usage."""
  l.LogError(reason)
  l.LogError("%s [OPTIONS] [ACTION] EXPERIMENT_FILE" % sys.argv[0])
  sys.exit(1)


def Run(experiment):
  status = ExperimentStatus(experiment)
  experiment.start()
  while not experiment.complete:
    border = "=============================="
    l.LogOutput(border)
    l.LogOutput(status.GetProgressString())
    l.LogOutput(status.GetStatusString())
    logger.GetLogger().LogOutput(border)
    time.sleep(30)


def Table(experiment):
  if experiment.success:
    l.LogOutput(experiment.table)
  else:
    l.LogError("Experiment did not complete successfully.")


def Email(experiment):
  if experiment.success:
    benchmark_names = []
    for benchmark_run in experiment.benchmark_runs:
      benchmark_names.append(benchmark_run.full_name)
    subject = "%s: %s" % (experiment.board, ", ".join(benchmark_names))
    EmailSender().SendEmailToUser(subject, experiment.table)
  else:
    l.LogError("Experiment did not complete successfully.")


def Main(argv):
  parser = optparse.OptionParser()
  _, args = parser.parse_args(argv)

  if len(args) == 2:
    action = DEFAULT_ACTION
    experiment_filename = args[1]
  elif len(args) == 3:
    action = args[1]
    experiment_filename = args[2]
  else:
    Usage("Invalid number arguments.")

  working_directory = os.getcwd()
  experiment_file = ExperimentFile(open(experiment_filename, "rb"))
  experiment = ExperimentFactory().GetExperiment(experiment_file,
                                                 working_directory)

  if action == "run":
    Run(experiment)
  elif action == "table":
    Table(experiment)
  elif action == "email":
    Email(experiment)
  elif action == "do":
    Run(experiment)
    Table(experiment)
    Email(experiment)
  else:
    Usage("Invalid action.")

if __name__ == "__main__":
  Main(sys.argv)


