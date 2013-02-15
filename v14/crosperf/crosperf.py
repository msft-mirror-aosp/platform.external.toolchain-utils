#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The driver script for running performance benchmarks on ChromeOS.

Current actions:
RUN: Run the benchmark on the device.
TABLE: Display a table of performance results.
"""

import atexit
import optparse
import os
import sys
from action_runner import ActionRunner
from action_runner import MockActionRunner
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from help import Help
from settings_factory import GlobalSettings
from utils import logger


DEFAULT_ACTION = "do"
l = logger.GetLogger()


def SetupParserOptions(parser):
  """Add all options to the parser."""
  parser.add_option("--full_help",
                    dest="full_help",
                    help=("Display full help instructions."),
                    action="store_true",
                    default=False)
  parser.add_option("--dry_run",
                    dest="dry_run",
                    help=("Parse the experiment file and "
                          "show what will be done"),
                    action="store_true",
                    default=False)
  # Allow each of the global fields to be overridden by passing in
  # options. Add each global field as an option.
  option_settings = GlobalSettings("")
  for field_name in option_settings.fields:
    field = option_settings.fields[field_name]
    parser.add_option("--%s" % field.name,
                      dest=field.name,
                      help=field.description,
                      action="store")


def ConvertOptionsToSettings(options):
  """Convert options passed in into global settings."""
  option_settings = GlobalSettings("option_settings")
  for option_name in options.__dict__:
    if (options.__dict__[option_name] is not None and
        option_name in option_settings.fields):
      option_settings.SetField(option_name, options.__dict__[option_name])
  return option_settings


def Usage(parser, reason):
  """Return script usage and exit with the given reason."""
  l.LogError(reason)
  parser.print_help()
  sys.exit(1)


def Cleanup(experiment):
  """Handler function which is registered to the atexit handler."""
  experiment.Cleanup()


def Main(argv):
  parser = optparse.OptionParser(usage=Help().GetUsage())
  SetupParserOptions(parser)
  options, args = parser.parse_args(argv)
  if options.full_help:
    parser.usage = Help().GetHelp()
    parser.print_help()
    sys.exit(0)

  # Convert the relevant options that are passed in into a settings
  # object which will override settings in the experiment file.
  option_settings = ConvertOptionsToSettings(options)

  if len(args) == 2:
    action = DEFAULT_ACTION
    experiment_filename = args[1]
  elif len(args) == 3:
    action = args[1]
    experiment_filename = args[2]
  else:
    Usage(parser, "Invalid number arguments.")

  working_directory = os.getcwd()
  experiment_file = ExperimentFile(open(experiment_filename, "rb"))
  experiment = ExperimentFactory().GetExperiment(experiment_file,
                                                 option_settings,
                                                 working_directory)
  atexit.register(Cleanup, experiment)

  if options.dry_run:
    runner = MockActionRunner(experiment)
  else:
    runner = ActionRunner(experiment)
  runner.RunAction(action)

if __name__ == "__main__":
  Main(sys.argv)
