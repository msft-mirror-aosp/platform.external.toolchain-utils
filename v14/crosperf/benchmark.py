#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


class Benchmark(object):
  """Class representing a benchmark to be run.

  Contains details of the autotest, arguments to pass to the autotest,
  iterations to run the autotest and so on. Note that the benchmark name
  can be different to the autotest name. For example, you may want to have
  two different benchmarks which run the same autotest with different
  arguments.
  """

  def __init__(self, name, autotest_name, autotest_args, iterations,
               outlier_range, key_results_only, rm_chroot_tmp, perf_args):
    self.name = name
    self.autotest_name = autotest_name
    self.autotest_args = autotest_args
    self.iterations = iterations
    self.outlier_range = outlier_range
    self.perf_args = perf_args
    self.key_results_only = key_results_only
    self.rm_chroot_tmp = rm_chroot_tmp
    self.iteration_adjusted = False
