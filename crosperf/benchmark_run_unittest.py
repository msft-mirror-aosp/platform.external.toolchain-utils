#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testing of benchmark_run."""

import unittest

from utils import logger

from suite_runner import MockSuiteRunner
from benchmark_run import MockBenchmarkRun
from label import MockLabel
from benchmark import Benchmark
from machine_manager import MockMachineManager
from results_cache import MockResultsCache


class BenchmarkRunTest(unittest.TestCase):
  def testDryRun(self):
    my_label = MockLabel("test1", "image1", "/tmp/test_benchmark_run",
                         "x86-alex", "chromeos2-row1-rack4-host9.cros",
                         image_args="",
                         image_md5sum="",
                         cache_dir="")
    logging_level="average"
    m = MockMachineManager("/tmp/chromeos_root", 0, logging_level)
    m.AddMachine("chromeos2-row1-rack4-host9.cros")
    bench = Benchmark("page_cycler.netsim.top_10",    # name
                      "page_cycler.netsim.top_10",    # test_name
                      "",             # test_args
                      1,              # iteratins
                      0.2,            # outlier_range
                      False,          # key_results_only
                      False,          # rm_chroot_tmp
                      "",             # perf_args
                      suite="telemetry_Crosperf")     # suite
    b = MockBenchmarkRun("test run",
                         bench,
                         my_label,
                         1,
                         [],
                         m,
                         logger.GetLogger(),
                         logging_level,
                         "")
    b.cache = MockResultsCache()
    b.suite_runner = MockSuiteRunner()
    b.start()


if __name__ == "__main__":
  unittest.main()
