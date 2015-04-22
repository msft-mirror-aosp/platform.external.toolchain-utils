#!/usr/bin/python
#
# Copyright 2014 Google Inc. All Rights Reserved.

"""Unittest for crosperf."""
import atexit
import os
import optparse
import StringIO


import mock
import unittest

import crosperf
import settings_factory
import experiment_file
import experiment_runner

from help import Help

from utils import command_executer
from utils import logger

EXPERIMENT_FILE_1 = """
  board: x86-alex
  remote: chromeos-alex3
  perf_args: record -a -e cycles
  benchmark: PageCycler {
    iterations: 3
  }

  image1 {
    chromeos_image: /usr/local/google/cros_image1.bin
  }

  image2 {
    remote: chromeos-lumpy1
    chromeos_image: /usr/local/google/cros_image2.bin
  }
  """

class CrosperfTest(unittest.TestCase):

  def setUp(self):
    input_file = StringIO.StringIO(EXPERIMENT_FILE_1)
    self.exp_file = experiment_file.ExperimentFile(input_file)

  def test_setup_parser_options(self):

    parser = optparse.OptionParser(usage=Help().GetUsage(),
                                   description=Help().GetHelp(),
                                   formatter=crosperf.MyIndentedHelpFormatter(),
                                   version="%prog 3.0")
    parser.add_option("-l", "--log_dir",
                      dest="log_dir",
                      default="",
                      help="The log_dir, default is under <crosperf_logs>/logs")
    options_before = parser._get_all_options()
    self.assertEqual(len(options_before), 3)
    crosperf.SetupParserOptions(parser)
    options_after = parser._get_all_options()
    self.assertEqual(len(options_after), 26)


  def test_convert_options_to_settings(self):
    parser = optparse.OptionParser(usage=Help().GetUsage(),
                                   description=Help().GetHelp(),
                                   formatter=crosperf.MyIndentedHelpFormatter(),
                                   version="%prog 3.0")
    parser.add_option("-l", "--log_dir",
                      dest="log_dir",
                      default="",
                      help="The log_dir, default is under <crosperf_logs>/logs")
    crosperf.SetupParserOptions(parser)
    argv = ['crosperf/crosperf.py', 'temp.exp', '--rerun=True']
    options, args = parser.parse_args(argv)
    settings = crosperf.ConvertOptionsToSettings(options)
    self.assertIsNotNone(settings)
    self.assertIsInstance(settings, settings_factory.GlobalSettings)
    self.assertEqual(len(settings.fields), 22)
    self.assertTrue(settings.GetField('rerun'))
    argv = ['crosperf/crosperf.py', 'temp.exp']
    options, args = parser.parse_args(argv)
    settings = crosperf.ConvertOptionsToSettings(options)
    self.assertFalse(settings.GetField('rerun'))


if __name__ == "__main__":
  unittest.main()
