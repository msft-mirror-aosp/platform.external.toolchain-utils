#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from autotest_runner import MockAutotestRunner
from benchmark_run import BenchmarkRun
from machine_manager import MockMachineManager
from perf_processor import MockPerfProcessor
from results_cache import MockResultsCache


class BenchmarkRunTest(unittest.TestCase):
  def testDryRun(self):
    m = MockMachineManager()
    m.AddMachine("chromeos-alex1")
    b = BenchmarkRun("test run",
                     "PageCycler",
                     "",
                     "/tmp/test",
                     "/tmp/test/image",
                     "x86-alex",
                     1,
                     False,
                     False,
                     False,
                     0.2,
                     m,
                     MockResultsCache(),
                     MockAutotestRunner(),
                     MockPerfProcessor())
    b.start()


if __name__ == "__main__":
  unittest.main()
