#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

from benchmark import Benchmark
from experiment import Experiment
from label import Label


class ExperimentFactory(object):
  """Factory class for building an Experiment, given an ExperimentFile as input.

  This factory is currently hardcoded to produce an experiment for running
  ChromeOS benchmarks, but the idea is that in the future, other types
  of experiments could be produced.
  """

  def GetExperiment(self, experiment_file, working_directory):
    """Construct an experiment from an experiment file."""
    global_settings = experiment_file.GetGlobalSettings()
    experiment_name = global_settings.GetField("name")
    board = global_settings.GetField("board")
    remote = global_settings.GetField("remote")
    rerun_if_failed = global_settings.GetField("rerun_if_failed")
    experiment = Experiment(experiment_name, board, remote, rerun_if_failed,
                            working_directory)

    # Construct benchmarks.
    all_benchmark_settings = experiment_file.GetSettings("benchmark")
    for benchmark_settings in all_benchmark_settings:
      benchmark_name = benchmark_settings.name
      autotest_name = benchmark_settings.GetField("autotest_name")
      if not autotest_name:
        autotest_name = benchmark_name
      autotest_args = benchmark_settings.GetField("autotest_args")
      iterations = benchmark_settings.GetField("iterations")
      outlier_range = benchmark_settings.GetField("outlier_range")
      benchmark = Benchmark(benchmark_name, autotest_name, autotest_args,
                            iterations, outlier_range)
      experiment.AddBenchmark(benchmark)

    # Construct labels.
    all_label_settings = experiment_file.GetSettings("label")
    for label_settings in all_label_settings:
      label_name = label_settings.name
      image = label_settings.GetField("chromeos_image")
      chromeos_root = label_settings.GetField("chromeos_root")
      label = Label(label_name, image, chromeos_root)
      experiment.AddLabel(label)

    experiment.GenerateBenchmarkRuns()

    return experiment
