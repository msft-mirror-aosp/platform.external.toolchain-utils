#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from field import BooleanField
from field import FloatField
from field import IntegerField
from field import ListField
from field import TextField
from settings import Settings


class BenchmarkSettings(Settings):
  def __init__(self, name):
    super(BenchmarkSettings, self).__init__(name, "benchmark")
    self.AddField(TextField("autotest_name"))
    self.AddField(TextField("autotest_args"))
    self.AddField(IntegerField("iterations", default=3, overridable=True))
    self.AddField(FloatField("outlier_range", default=0.2))


class LabelSettings(Settings):
  def __init__(self, name):
    super(LabelSettings, self).__init__(name, "label")
    self.AddField(TextField("chromeos_image", required=True))
    self.AddField(TextField("chromeos_root"))


class GlobalSettings(Settings):
  def __init__(self, name):
    super(GlobalSettings, self).__init__(name, "global")
    self.AddField(TextField("name", default="Experiment"))
    self.AddField(TextField("board", required=True))
    self.AddField(ListField("remote", required=True))
    self.AddField(BooleanField("rerun_if_failed"))
    self.AddField(IntegerField("iterations"))


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
