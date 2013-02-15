#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import StringIO
import unittest
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from settings_factory import GlobalSettings
from utils.file_utils import FileUtils


EXPERIMENT_FILE_1 = """
  board: x86-alex
  remote: chromeos-alex3

  benchmark: PageCycler {
    iterations: 3
  }

  image1 {
    chromeos_image: /usr/local/google/cros_image1.bin
  }

  image2 {
    chromeos_image: /usr/local/google/cros_image2.bin
  }
  """


class ExperimentFactoryTest(unittest.TestCase):
  def testLoadExperimentFile1(self):
    experiment_file = ExperimentFile(StringIO.StringIO(EXPERIMENT_FILE_1))
    experiment = ExperimentFactory().GetExperiment(experiment_file,
                                                   GlobalSettings(""),
                                                   "/tmp/")
    self.assertEqual(experiment.board, "x86-alex")
    self.assertEqual(experiment.remote, ["chromeos-alex3"])

    self.assertEqual(len(experiment.benchmarks), 1)
    self.assertEqual(experiment.benchmarks[0].name, "PageCycler")
    self.assertEqual(experiment.benchmarks[0].autotest_name, "PageCycler")
    self.assertEqual(experiment.benchmarks[0].iterations, 3)

    self.assertEqual(len(experiment.labels), 2)
    self.assertEqual(experiment.labels[0].chromeos_image,
                     "/usr/local/google/cros_image1.bin")


if __name__ == "__main__":
  FileUtils.Configure(True)
  unittest.main()
