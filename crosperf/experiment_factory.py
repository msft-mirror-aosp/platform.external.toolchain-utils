#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module to generate experments."""

import os
import re
import socket

from benchmark import Benchmark
import config
from experiment import Experiment
from label import Label
from label import MockLabel
from results_cache import CacheConditions
import test_flag

# Note:  Telemetry benchmark test names sometimes include a ".", causes
# difficulties in the argument parsing stage.  Therefore we use the
# translation dictionary below, so we can translate from a name the
# argument parser will accept to the actual correct benchmark name.

telemetry_perf_tests = {
    'dromaeo_domcoreattr'     : 'dromaeo.domcoreattr',
    'dromaeo_domcoremodify'   : 'dromaeo.domcoremodify',
    'dromaeo_domcorequery'    : 'dromaeo.domcorequery',
    'dromaeo_domcoretraverse' : 'dromaeo.domcoretraverse',
    'kraken'                  : 'kraken',
    'memory_top25'            : 'memory.top25',
    'octane'                  : 'octane',
    'robohornet_pro'          : 'robohornet_pro',
    'smoothness_top25'        : 'smoothness.top25',
    'sunspider'               : 'sunspider'
  }

class ExperimentFactory(object):
  """Factory class for building an Experiment, given an ExperimentFile as input.

  This factory is currently hardcoded to produce an experiment for running
  ChromeOS benchmarks, but the idea is that in the future, other types
  of experiments could be produced.
  """

  def GetExperiment(self, experiment_file, working_directory, log_dir):
    """Construct an experiment from an experiment file."""
    global_settings = experiment_file.GetGlobalSettings()
    experiment_name = global_settings.GetField("name")
    remote = global_settings.GetField("remote")
    # This is used to remove the ",' from the remote if user
    # add them to the remote string.
    new_remote = []
    for i in remote:
      c = re.sub('["\']', '', i)
      new_remote.append(c)
    remote = new_remote
    chromeos_root = global_settings.GetField("chromeos_root")
    rm_chroot_tmp = global_settings.GetField("rm_chroot_tmp")
    key_results_only = global_settings.GetField("key_results_only")
    acquire_timeout= global_settings.GetField("acquire_timeout")
    cache_dir = global_settings.GetField("cache_dir")
    config.AddConfig("no_email", global_settings.GetField("no_email"))
    share_users = global_settings.GetField("share_users")
    results_dir = global_settings.GetField("results_dir")
    chrome_src = global_settings.GetField("chrome_src")
    use_test_that = global_settings.GetField("use_test_that")
    # Default cache hit conditions. The image checksum in the cache and the
    # computed checksum of the image must match. Also a cache file must exist.
    cache_conditions = [CacheConditions.CACHE_FILE_EXISTS,
                        CacheConditions.CHECKSUMS_MATCH]
    if global_settings.GetField("rerun_if_failed"):
      cache_conditions.append(CacheConditions.RUN_SUCCEEDED)
    if global_settings.GetField("rerun"):
      cache_conditions.append(CacheConditions.FALSE)
    if global_settings.GetField("same_machine"):
      cache_conditions.append(CacheConditions.SAME_MACHINE_MATCH)
    if global_settings.GetField("same_specs"):
      cache_conditions.append(CacheConditions.MACHINES_MATCH)

    # Construct benchmarks.
    benchmarks = []
    all_benchmark_settings = experiment_file.GetSettings("benchmark")
    for benchmark_settings in all_benchmark_settings:
      benchmark_name = benchmark_settings.name
      test_name = benchmark_settings.GetField("test_name")
      if not test_name:
        test_name = benchmark_name
      test_args = benchmark_settings.GetField("test_args")
      iterations = benchmark_settings.GetField("iterations")
      outlier_range = benchmark_settings.GetField("outlier_range")
      perf_args = benchmark_settings.GetField("perf_args")
      rm_chroot_tmp = benchmark_settings.GetField("rm_chroot_tmp")
      key_results_only = benchmark_settings.GetField("key_results_only")
      suite = benchmark_settings.GetField("suite")
      use_test_that = benchmark_settings.GetField("use_test_that")

      if suite == 'telemetry_Crosperf':
        if test_name == 'all':
          # Create and add one benchmark for each telemetry perf test.
          for test in telemetry_perf_tests.keys():
            telemetry_test_name = telemetry_perf_tests[test]
            telemetry_benchmark = Benchmark (telemetry_test_name,
                                             telemetry_test_name,
                                             test_args, iterations,
                                             outlier_range, key_results_only,
                                             rm_chroot_tmp, perf_args, suite,
                                             use_test_that)
            benchmarks.append(telemetry_benchmark)
        else:
          # Get correct name of Telemetry benchmark test.
          test_name = telemetry_perf_tests[test_name]
          benchmark = Benchmark(test_name, test_name, test_args,
                                iterations, outlier_range,
                                key_results_only, rm_chroot_tmp,
                                perf_args, suite, use_test_that)
          benchmarks.append(benchmark)
      else:
        # Add the single benchmark.
        benchmark = Benchmark(benchmark_name, test_name, test_args,
                              iterations, outlier_range,
                              key_results_only, rm_chroot_tmp,
                              perf_args, suite, use_test_that)
        benchmarks.append(benchmark)

    # Construct labels.
    labels = []
    all_label_settings = experiment_file.GetSettings("label")
    all_remote = list(remote)
    for label_settings in all_label_settings:
      label_name = label_settings.name
      image = label_settings.GetField("chromeos_image")
      chromeos_root = label_settings.GetField("chromeos_root")
      board = label_settings.GetField("board")
      my_remote = label_settings.GetField("remote")
      new_remote = []
      for i in my_remote:
        c = re.sub('["\']', '', i)
        new_remote.append(c)
      my_remote = new_remote

      image_md5sum = label_settings.GetField("md5sum")
      cache_dir = label_settings.GetField("cache_dir")
      chrome_src = label_settings.GetField("chrome_src")

    # TODO(yunlian): We should consolidate code in machine_manager.py
    # to derermine whether we are running from within google or not
      if ("corp.google.com" in socket.gethostname() and
          (not my_remote
           or my_remote == remote
           and global_settings.GetField("board") != board)):
        my_remote = self.GetDefaultRemotes(board)
      if global_settings.GetField("same_machine") and len(my_remote) > 1:
        raise Exception("Only one remote is allowed when same_machine "
                        "is turned on")
      all_remote += my_remote
      image_args = label_settings.GetField("image_args")
      if test_flag.GetTestMode():
        label = MockLabel(label_name, image, chromeos_root, board, my_remote,
                          image_args, image_md5sum, cache_dir, chrome_src)
      else:
        label = Label(label_name, image, chromeos_root, board, my_remote,
                      image_args, image_md5sum, cache_dir, chrome_src)
      labels.append(label)

    email = global_settings.GetField("email")
    all_remote = list(set(all_remote))
    experiment = Experiment(experiment_name, all_remote,
                            working_directory, chromeos_root,
                            cache_conditions, labels, benchmarks,
                            experiment_file.Canonicalize(),
                            email, acquire_timeout, log_dir, share_users,
                            results_dir)

    return experiment

  def GetDefaultRemotes(self, board):
    default_remotes_file = os.path.join(os.path.dirname(__file__),
                                        "default_remotes")
    try:
      with open(default_remotes_file) as f:
        for line in f:
          key, v = line.split(":")
          if key.strip() == board:
            remotes = v.strip().split(" ")
            if remotes:
              return remotes
            else:
              raise Exception("There is not remote for {0}".format(board))
    except IOError:
      raise Exception("IOError while reading file {0}"
                      .format(default_remotes_file))
    else:
      raise Exception("There is not remote for {0}".format(board))
