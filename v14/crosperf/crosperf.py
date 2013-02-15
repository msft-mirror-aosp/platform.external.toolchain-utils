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
from action_runner import ActionRunner
from action_runner import MockActionRunner
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from utils import logger


DEFAULT_ACTION = "do"
USAGE = "%s [OPTIONS] [ACTION] EXPERIMENT_FILE" % sys.argv[0]
parser = optparse.OptionParser(usage=USAGE)
l = logger.GetLogger()


def Usage(reason):
  """Return script usage."""
  l.LogError(reason)
  parser.get_usage()
  sys.exit(1)


def Main(argv):
  parser.add_option("--dry_run",
                    dest="dry_run",
                    help=("Parse the experiment file and "
                          "show what will be done"),
                    action="store_true",
                    default=False)
  options, args = parser.parse_args(argv)

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

  if options.dry_run:
    runner = MockActionRunner(experiment)
  else:
    runner = ActionRunner(experiment)
  runner.RunAction(action)


if __name__ == "__main__":
  Main(sys.argv)
