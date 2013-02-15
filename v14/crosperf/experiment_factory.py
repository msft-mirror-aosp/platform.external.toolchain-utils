#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from benchmark import Benchmark
from experiment import Experiment
from label import Label
from results_cache import CacheConditions


class ExperimentFactory(object):
  """Factory class for building an Experiment, given an ExperimentFile as input.

  This factory is currently hardcoded to produce an experiment for running
  ChromeOS benchmarks, but the idea is that in the future, other types
  of experiments could be produced.
  """

  def GetExperiment(self, experiment_file, option_settings,
                    working_directory):
    """Construct an experiment from an experiment file."""
    global_settings = experiment_file.GetGlobalSettings()
    # Override settings which are passed in as arguments.
    global_settings.Override(option_settings)
    experiment_name = global_settings.GetField("name")
    board = global_settings.GetField("board")
    remote = global_settings.GetField("remote")
    rerun_if_failed = global_settings.GetField("rerun_if_failed")
    chromeos_root = global_settings.GetField("chromeos_root")

    # Default cache hit conditions. The image checksum in the cache and the
    # computed checksum of the image must match. Also a cache file must exist.
    cache_conditions = [CacheConditions.CACHE_FILE_EXISTS,
                        CacheConditions.CHECKSUMS_MATCH]
    if global_settings.GetField("rerun_if_failed"):
      cache_conditions.append(CacheConditions.RUN_SUCCEEDED)
    if global_settings.GetField("rerun"):
      cache_conditions.append(CacheConditions.FALSE)
    if global_settings.GetField("exact_remote"):
      cache_conditions.append(CacheConditions.REMOTES_MATCH)

    # Construct benchmarks.
    benchmarks = []
    all_benchmark_settings = experiment_file.GetSettings("benchmark")
    for benchmark_settings in all_benchmark_settings:
      benchmark_settings.Override(option_settings)
      benchmark_name = benchmark_settings.name
      autotest_name = benchmark_settings.GetField("autotest_name")
      if not autotest_name:
        autotest_name = benchmark_name
      autotest_args = benchmark_settings.GetField("autotest_args")
      iterations = benchmark_settings.GetField("iterations")
      outlier_range = benchmark_settings.GetField("outlier_range")
      profile_counters = benchmark_settings.GetField("profile_counters")
      benchmark = Benchmark(benchmark_name, autotest_name, autotest_args,
                            iterations, outlier_range, profile_counters)
      benchmarks.append(benchmark)

    # Construct labels.
    labels = []
    all_label_settings = experiment_file.GetSettings("label")
    for label_settings in all_label_settings:
      label_settings.Override(option_settings)
      label_name = label_settings.name
      image = label_settings.GetField("chromeos_image")
      chromeos_root = label_settings.GetField("chromeos_root")
      label = Label(label_name, image, chromeos_root)
      labels.append(label)

    experiment = Experiment(experiment_name, board, remote, rerun_if_failed,
                            working_directory, False, chromeos_root,
                            cache_conditions, labels, benchmarks)

    return experiment
