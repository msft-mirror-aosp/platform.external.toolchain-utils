#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The driver script for running performance benchmarks on ChromeOS."""

import atexit
import optparse
import os
import sys
from experiment_runner import ExperimentRunner
from experiment_runner import MockExperimentRunner
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from help import Help
from settings_factory import GlobalSettings
from utils import logger

import test_flag


class MyIndentedHelpFormatter(optparse.IndentedHelpFormatter):
  def format_description(self, description):
    return description


def SetupParserOptions(parser):
  """Add all options to the parser."""
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


def Cleanup(experiment):
  """Handler function which is registered to the atexit handler."""
  experiment.Cleanup()


def Main(argv):
  parser = optparse.OptionParser(usage=Help().GetUsage(),
                                 description=Help().GetHelp(),
                                 formatter=MyIndentedHelpFormatter(),
                                 version="%prog 3.0")

  parser.add_option("--schedv2",
                    dest="schedv2",
                    action="store_true",
                    help="Use crosperf scheduler v2 (feature in progress).")
  parser.add_option("-l", "--log_dir",
                    dest="log_dir",
                    default="",
                    help="The log_dir, default is under <crosperf_logs>/logs")

  SetupParserOptions(parser)
  options, args = parser.parse_args(argv)

  # Convert the relevant options that are passed in into a settings
  # object which will override settings in the experiment file.
  option_settings = ConvertOptionsToSettings(options)
  log_dir = os.path.abspath(os.path.expanduser(options.log_dir))
  logger.GetLogger(log_dir)

  if len(args) == 2:
    experiment_filename = args[1]
  else:
    parser.error("Invalid number arguments.")

  working_directory = os.getcwd()
  if options.dry_run:
    test_flag.SetTestMode(True)

  experiment_file = ExperimentFile(open(experiment_filename, "rb"),
                                   option_settings)
  if not experiment_file.GetGlobalSettings().GetField("name"):
    experiment_name = os.path.basename(experiment_filename)
    experiment_file.GetGlobalSettings().SetField("name", experiment_name)
  experiment = ExperimentFactory().GetExperiment(experiment_file,
                                                 working_directory,
                                                 log_dir)

  atexit.register(Cleanup, experiment)

  if options.dry_run:
    runner = MockExperimentRunner(experiment)
  else:
    runner = ExperimentRunner(experiment, using_schedv2=options.schedv2)

  runner.Run()

if __name__ == "__main__":
  Main(sys.argv)
