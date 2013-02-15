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
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from utils import logger


DEFAULT_ACTION = "run"


def Usage(reason):
  """Return script usage."""
  l = logger.GetLogger()
  l.LogError(reason)
  l.LogError("%s [OPTIONS] [ACTION] EXPERIMENT_FILE" % sys.argv[0])
  sys.exit(1)


def Main(argv):
  l = logger.GetLogger()
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
    experiment.Run()
    l.LogOutput(experiment.GetTable())
  elif action == "table":
    l.LogOutput(experiment.GetTable())
  else:
    Usage("Invalid action.")

if __name__ == "__main__":
  Main(sys.argv)


