#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from field import BooleanField
from field import EnumField
from field import FloatField
from field import IntegerField
from field import ListField
from field import TextField
from settings import Settings


class BenchmarkSettings(Settings):
  def __init__(self, name):
    super(BenchmarkSettings, self).__init__(name, "benchmark")
    self.AddField(TextField("autotest_name",
                            description="The name of the autotest to run."
                            "Defaults to the name of the benchmark."))
    self.AddField(TextField("autotest_args",
                            description="Arguments to be passed to the "
                            "autotest."))
    self.AddField(IntegerField("iterations", default=3,
                               description="Number of iterations to run the "
                               "autotest."))
    self.AddField(FloatField("outlier_range", default=0.2,
                             description="The percentage of highest/lowest "
                             "values to omit when computing the average."))
    self.AddField(ListField("profile_counters",
                            description="A list of profile counters to "
                            "collect."))
    self.AddField(EnumField("profile_type",
                            description="The type of profile to collect. "
                            "Either 'stat', 'record' or 'none'.",
                            options=["stat", "record", "none"],
                            default="none"))


class LabelSettings(Settings):
  def __init__(self, name):
    super(LabelSettings, self).__init__(name, "label")
    self.AddField(TextField("chromeos_image", required=True,
                            description="The path to the image to run tests "
                            "on."))
    self.AddField(TextField("chromeos_root",
                            description="The path to a chromeos checkout which "
                            "contains a src/scripts directory. Defaults to "
                            "the chromeos checkout which contains the "
                            "chromeos_image."))
    self.AddField(TextField("board", required=True, description="The target "
                            "board for running experiments on, e.g. x86-alex."))


class GlobalSettings(Settings):
  def __init__(self, name):
    super(GlobalSettings, self).__init__(name, "global")
    self.AddField(TextField("name", default="Experiment",
                            description="The name of the experiment. Just an "
                            "identifier."))
    self.AddField(TextField("board", description="The target "
                            "board for running experiments on, e.g. x86-alex."))
    self.AddField(ListField("remote", required=True,
                            description="A comma-separated list of ip's of "
                            "chromeos devices to run experiments on."))
    self.AddField(BooleanField("rerun_if_failed", description="Whether to "
                               "re-run failed autotest runs or not.",
                               default=False))
    self.AddField(BooleanField("rerun", description="Whether to ignore the "
                               "cache and for autotests to be re-run.",
                               default=False))
    self.AddField(BooleanField("exact_remote", default=False,
                               description="Ensure cached runs are run on the "
                               "same device that is specified as a remote."))
    self.AddField(IntegerField("iterations", default=3,
                               description="Number of iterations to run all "
                               "autotests."))
    self.AddField(TextField("chromeos_root",
                            description="The path to a chromeos checkout which "
                            "contains a src/scripts directory. Defaults to "
                            "the chromeos checkout which contains the "
                            "chromeos_image."))
    self.AddField(ListField("profile_counters",
                            description="A list of profile counters to "
                            "collect."))
    self.AddField(EnumField("profile_type",
                            description="The type of profile to collect. "
                            "Either 'stat', 'record' or 'none'.",
                            options=["stat", "record", "none"]))


class SettingsFactory(object):
  """Factory class for building different types of Settings objects.

  This factory is currently hardcoded to produce settings for ChromeOS
  experiment files. The idea is that in the future, other types
  of settings could be produced.
  """

  def GetSettings(self, name, settings_type):
    if settings_type == "label" or not settings_type:
      return LabelSettings(name)
    if settings_type == "global":
      return GlobalSettings(name)
    if settings_type == "benchmark":
      return BenchmarkSettings(name)

    raise Exception("Invalid settings type: '%s'." % settings_type)
