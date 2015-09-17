#!/usr/bin/python

# Copyright 2015 Google Inc. All Rights Reserved.

import mock
import unittest
import StringIO

import machine_manager
import test_flag
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from experiment_runner import ExperimentRunner
from machine_manager import MockCrosMachine
from utils import command_executer
from utils.command_executer import CommandExecuter
from experiment_runner_unittest import FakeLogger
from schedv2 import Schedv2


EXPERIMENT_FILE_1 = """
  board: daisy
  remote: chromeos-daisy1.cros chromeos-daisy2.cros

  benchmark: kraken {
    suite: telemetry_Crosperf
    iterations: 3
  }

  image1 {
    chromeos_image: /chromeos/src/build/images/daisy/latest/cros_image1.bin
    remote: chromeos-daisy3.cros
  }

  image2 {
    chromeos_image: /chromeos/src/build/imaages/daisy/latest/cros_image2.bin
    remote: chromeos-daisy4.cros chromeos-daisy5.cros
  }
  """


class Schedv2Test(unittest.TestCase):

    mock_logger = FakeLogger()
    mock_cmd_exec = mock.Mock(spec=CommandExecuter)

    def _make_fake_experiment(self, expstr):
        experiment_file = ExperimentFile(StringIO.StringIO(expstr))
        experiment = ExperimentFactory().GetExperiment(
            experiment_file, working_directory="", log_dir="")
        return experiment

    def test_remote(self):
        """Test that remotes in labels are aggregated into experiment.remote."""

        self.exp = self._make_fake_experiment(EXPERIMENT_FILE_1)
        self.exp.log_level = 'verbose'
        schedv2 = Schedv2(self.exp)
        self.assertIn('chromeos-daisy1.cros', self.exp.remote)
        self.assertIn('chromeos-daisy2.cros', self.exp.remote)
        self.assertIn('chromeos-daisy3.cros', self.exp.remote)
        self.assertIn('chromeos-daisy4.cros', self.exp.remote)
        self.assertIn('chromeos-daisy5.cros', self.exp.remote)

    def test_unreachable_remote(self):
        """Test unreachable remotes are removed from experiment remote and
        label.remote."""

        def MockIsReachable(cm):
            return (cm.name != 'chromeos-daisy3.cros' and
                    cm.name != 'chromeos-daisy5.cros')

        originalIsReachable = MockCrosMachine.IsReachable

        try:
            MockCrosMachine.IsReachable = MockIsReachable
            self.exp = self._make_fake_experiment(EXPERIMENT_FILE_1)
            self.assertIn('chromeos-daisy1.cros', self.exp.remote)
            self.assertIn('chromeos-daisy2.cros', self.exp.remote)
            self.assertNotIn('chromeos-daisy3.cros', self.exp.remote)
            self.assertIn('chromeos-daisy4.cros', self.exp.remote)
            self.assertNotIn('chromeos-daisy5.cros', self.exp.remote)

            for l in self.exp.labels:
                if l.name == 'image2':
                    self.assertNotIn('chromeos-daisy5.cros', l.remote)
                    self.assertIn('chromeos-daisy4.cros', l.remote)
                elif l.name == 'image1':
                    self.assertNotIn('chromeos-daisy3.cros', l.remote)
        finally:
            MockCrosMachine.IsReachable = originalIsReachable


if __name__ == '__main__':
    test_flag.SetTestMode(True)
    unittest.main()

