#!/usr/bin/python
#
# Copyright 2014 Google Inc. All Rights Reserved.

"""Unittest for crosperf."""
import os

import mock
import unittest

import settings_factory
import settings

from utils import command_executer
from utils import logger

class BenchmarkSettingsTest(unittest.TestCase):

  def test_init(self):
    res = settings_factory.BenchmarkSettings("b_settings")
    self.assertIsNotNone(res)
    self.assertEqual(len(res.fields), 4)
    self.assertEqual(res.GetField('test_name'), '')
    self.assertEqual(res.GetField('test_args'), '')
    self.assertEqual(res.GetField('iterations'), 1)
    self.assertEqual(res.GetField('suite'), '')

class LabelSettingsTest(unittest.TestCase):

  def test_init(self):
    res = settings_factory.LabelSettings("l_settings")
    self.assertIsNotNone(res)
    self.assertEqual(len(res.fields), 7)
    self.assertEqual(res.GetField('chromeos_image'), '')
    self.assertEqual(res.GetField('chromeos_root'), '')
    self.assertEqual(res.GetField('remote'), [])
    self.assertEqual(res.GetField('image_args'), '')
    self.assertEqual(res.GetField('cache_dir'), '')
    self.assertEqual(res.GetField('chrome_src'), '')
    self.assertEqual(res.GetField('build'), '')


class GlobalSettingsTest(unittest.TestCase):

  def test_init(self):
    res = settings_factory.GlobalSettings("g_settings")
    self.assertIsNotNone(res)
    self.assertEqual(len(res.fields), 21)
    self.assertEqual(res.GetField('name'), '')
    self.assertEqual(res.GetField('board'), '')
    self.assertEqual(res.GetField('remote'), [])
    self.assertEqual(res.GetField('rerun_if_failed'), False)
    self.assertEqual(res.GetField('rm_chroot_tmp'), False)
    self.assertEqual(res.GetField('email'), [])
    self.assertEqual(res.GetField('rerun'), False)
    self.assertEqual(res.GetField('same_specs'), True)
    self.assertEqual(res.GetField('same_machine'), False)
    self.assertEqual(res.GetField('iterations'), 1)
    self.assertEqual(res.GetField('chromeos_root'), '')
    self.assertEqual(res.GetField('logging_level'), 'average')
    self.assertEqual(res.GetField('acquire_timeout'), 0)
    self.assertEqual(res.GetField('perf_args'), '')
    self.assertEqual(res.GetField('cache_dir'), '')
    self.assertEqual(res.GetField('cache_only'), False)
    self.assertEqual(res.GetField('no_email'), False)
    self.assertEqual(res.GetField('show_all_results'), False)
    self.assertEqual(res.GetField('share_cache'), '')
    self.assertEqual(res.GetField('results_dir'), '')
    self.assertEqual(res.GetField('chrome_src'), '')


class SettingsFactoryTest(unittest.TestCase):

  def test_get_settings(self):
    self.assertRaises (Exception, settings_factory.SettingsFactory.GetSettings,
                       'global', 'bad_type')


    l_settings = settings_factory.SettingsFactory().GetSettings ('label', 'label')
    self.assertIsInstance(l_settings, settings_factory.LabelSettings)
    self.assertEqual(len(l_settings.fields), 7)

    b_settings = settings_factory.SettingsFactory().GetSettings ('benchmark',
                                                                 'benchmark')
    self.assertIsInstance(b_settings, settings_factory.BenchmarkSettings)
    self.assertEqual(len(b_settings.fields), 4)

    g_settings = settings_factory.SettingsFactory().GetSettings ('global',
                                                                 'global')
    self.assertIsInstance(g_settings, settings_factory.GlobalSettings)
    self.assertEqual(len(g_settings.fields), 21)


if __name__ == "__main__":
  unittest.main()
