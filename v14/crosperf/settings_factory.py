#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.
"""Setting files for global, benchmark and labels."""

from field import BooleanField
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
    self.AddField(IntegerField("iterations", default=1,
                               description="Number of iterations to run the "
                               "autotest."))
    self.AddField(FloatField("outlier_range", default=0.2,
                             description="The percentage of highest/lowest "
                             "values to omit when computing the average."))
    self.AddField(BooleanField("rm_chroot_tmp", default=False,
                               description="Whether remove the run_remote_test"
                               "result in the chroot"))
    self.AddField(BooleanField("key_results_only", default=True,
                               description="Whether only show the key results"
                               "of pyautoperf"))
    self.AddField(TextField("perf_args", default="",
                            description="The optional profile command. It "
                            "enables perf commands to record perforamance "
                            "related counters. It  must start with perf "
                            "command record or stat followed by arguments."))


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
    self.AddField(TextField("md5sum", default="",
                            description="The md5sum of this image"))
    self.AddField(TextField("board", required=True, description="The target "
                            "board for running experiments on, e.g. x86-alex."))
    self.AddField(ListField("remote", description=
                            "A comma-separated list of ip's of chromeos"
                            "devices to run experiments on."))
    self.AddField(TextField("image_args", required=False,
                            default="",
                            description="Extra arguments to pass to "
                            "image_chromeos.py."))


class GlobalSettings(Settings):
  def __init__(self, name):
    super(GlobalSettings, self).__init__(name, "global")
    self.AddField(TextField("name",
                            description="The name of the experiment. Just an "
                            "identifier."))
    self.AddField(TextField("board", description="The target "
                            "board for running experiments on, e.g. x86-alex."))
    self.AddField(ListField("remote",
                            description="A comma-separated list of ip's of "
                            "chromeos devices to run experiments on."))
    self.AddField(BooleanField("rerun_if_failed", description="Whether to "
                               "re-run failed autotest runs or not.",
                               default=False))
    self.AddField(BooleanField("rm_chroot_tmp", default=False,
                               description="Whether remove the run_remote_test"
                               "result in the chroot"))
    self.AddField(ListField("email", description="Space-seperated"
                            "list of email addresses to send email to."))
    self.AddField(BooleanField("rerun", description="Whether to ignore the "
                               "cache and for autotests to be re-run.",
                               default=False))
    self.AddField(BooleanField("same_specs", default=True,
                               description="Ensure cached runs are run on the "
                               "same kind of devices which are specified as a "
                               "remote."))
    self.AddField(BooleanField("same_machine", default=False,
                               description="Ensure cached runs are run on the "
                               "exact the same remote"))
    self.AddField(IntegerField("iterations", default=1,
                               description="Number of iterations to run all "
                               "autotests."))
    self.AddField(TextField("chromeos_root",
                            description="The path to a chromeos checkout which "
                            "contains a src/scripts directory. Defaults to "
                            "the chromeos checkout which contains the "
                            "chromeos_image."))
    self.AddField(BooleanField("key_results_only", default=True,
                               description="Whether only show the key results"
                               "of pyautoperf"))
    self.AddField(IntegerField("acquire_timeout", default=0,
                               description="Number of seconds to wait for "
                               "machine before exit if all the machines in "
                               "the experiment file are busy. Default is 0"))
    self.AddField(TextField("perf_args", default="",
                            description="The optional profile command. It "
                            "enables perf commands to record perforamance "
                            "related counters. It must start with perf "
                            "command record or stat followed by arguments."))
    self.AddField(TextField("cache_dir", default="",
                            description="The abs path of cache dir. "
                            "Default is /home/$(whoami)/cros_scratch."))


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
