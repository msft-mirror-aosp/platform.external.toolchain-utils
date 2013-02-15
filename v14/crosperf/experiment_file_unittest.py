#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import StringIO
import unittest
from experiment_file import ExperimentFile

EXPERIMENT_FILE_1 = """
  board: x86-alex
  remote: chromeos-alex3

  benchmark: PageCycler {
    iterations: 3
  }

  image1 {
    image: /usr/local/google/cros_image1.bin
  }

  image2 {
    image: /usr/local/google/cros_image2.bin
  }
  """

EXPERIMENT_FILE_2 = """
  board: x86-alex
  remote: chromeos-alex3

  benchmark: PageCycler {
    remote: chromeos-alex1
    iterations: 3
  }

  benchmark: AndroidBench {
    remote: chromeos-alex3
    iterations: 2
  }

  image1 {
    image:/usr/local/google/cros_image1.bin
  }

  image2 {
    image: /usr/local/google/cros_image2.bin
  }
  """


class ExperimentFileTest(unittest.TestCase):
  def testLoadExperimentFile1(self):
    input_file = StringIO.StringIO(EXPERIMENT_FILE_1)
    experiment_file = ExperimentFile(input_file)
    global_settings = experiment_file.GetGlobalSettings()
    self.assertEqual(global_settings.GetField("board"), "x86-alex")
    self.assertEqual(global_settings.GetField("remote"), "chromeos-alex3")

    benchmark_settings = experiment_file.GetSettings("benchmark")
    self.assertEqual(len(benchmark_settings), 1)
    self.assertEqual(benchmark_settings[0].name, "PageCycler")
    self.assertEqual(benchmark_settings[0].GetField("iterations"), "3")

    label_settings = experiment_file.GetSettings("")
    self.assertEqual(len(label_settings), 2)
    self.assertEqual(label_settings[0].name, "image1")
    self.assertEqual(label_settings[0].GetField("image"),
                     "/usr/local/google/cros_image1.bin")

  def testOverrideSetting(self):
    input_file = StringIO.StringIO(EXPERIMENT_FILE_2)
    experiment_file = ExperimentFile(input_file)
    global_settings = experiment_file.GetGlobalSettings()
    self.assertEqual(global_settings.GetField("board"), "x86-alex")
    self.assertEqual(global_settings.GetField("remote"), "chromeos-alex3")

    benchmark_settings = experiment_file.GetSettings("benchmark")
    self.assertEqual(len(benchmark_settings), 2)
    self.assertEqual(benchmark_settings[0].name, "PageCycler")
    self.assertEqual(benchmark_settings[0].GetField("remote"), "chromeos-alex1")
    self.assertEqual(benchmark_settings[1].name, "AndroidBench")
    self.assertEqual(benchmark_settings[1].GetField("remote"), "chromeos-alex3")

if __name__ == "__main__":
  unittest.main()
