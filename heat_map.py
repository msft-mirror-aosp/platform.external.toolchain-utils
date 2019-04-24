#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper to generate heat maps for chrome."""

from __future__ import print_function

import argparse
import shutil
import os
import sys
import tempfile

from cros_utils import command_executer
import heatmap_generator


def IsARepoRoot(directory):
  """Returns True if directory is the root of a repo checkout."""
  return os.path.exists(os.path.join(directory, '.repo'))


class HeatMapProducer(object):
  """Class to produce heat map."""

  def __init__(self, chromeos_root, perf_data, page_size, binary, title):
    self.chromeos_root = os.path.realpath(chromeos_root)
    self.perf_data = os.path.realpath(perf_data)
    self.page_size = page_size
    self.dir = os.path.dirname(os.path.realpath(__file__))
    self.binary = binary
    self.tempDir = ''
    self.ce = command_executer.GetCommandExecuter()
    self.loading_address = None
    self.temp_perf = ''
    self.temp_perf_inchroot = ''
    self.perf_report = ''
    self.title = title

  def copyFileToChroot(self):
    self.tempDir = tempfile.mkdtemp(
        prefix=os.path.join(self.chromeos_root, 'src/'))
    self.temp_perf = os.path.join(self.tempDir, 'perf.data')
    shutil.copy2(self.perf_data, self.temp_perf)
    self.temp_perf_inchroot = os.path.join('~/trunk/src',
                                           os.path.basename(self.tempDir))

  def getPerfReport(self):
    if os.path.isfile(os.path.join(self.tempDir, 'perf_report.txt')):
      self.perf_report = os.path.join(self.tempDir, 'perf_report.txt')
      return

    cmd = ('cd %s; perf report -D -i perf.data > perf_report.txt' %
           self.temp_perf_inchroot)
    retval = self.ce.ChrootRunCommand(self.chromeos_root, cmd)
    if retval:
      raise RuntimeError('Failed to generate perf report')
    self.perf_report = os.path.join(self.tempDir, 'perf_report.txt')

  def getHeatMap(self, top_n_pages=None):
    generator = heatmap_generator.HeatmapGenerator(self.perf_report,
                                                   self.page_size, self.title)
    generator.draw()
    # Analyze top N hottest symbols with the binary, if provided
    if self.binary:
      if top_n_pages is not None:
        generator.analyze(self.binary, top_n_pages)
      else:
        generator.analyze(self.binary)

  def RemoveFiles(self):
    shutil.rmtree(self.tempDir)
    if os.path.isfile(os.path.join(os.getcwd(), 'out.txt')):
      os.remove(os.path.join(os.getcwd(), 'out.txt'))
    if os.path.isfile(os.path.join(os.getcwd(), 'inst-histo.txt')):
      os.remove(os.path.join(os.getcwd(), 'inst-histo.txt'))


def main(argv):
  """Parse the options.

  Args:
    argv: The options with which this script was invoked.

  Returns:
    0 unless an exception is raised.
  """
  parser = argparse.ArgumentParser()

  parser.add_argument(
      '--chromeos_root',
      dest='chromeos_root',
      required=True,
      help='ChromeOS root to use for generate heatmaps.')
  parser.add_argument(
      '--perf_data', dest='perf_data', required=True, help='The raw perf data.')
  parser.add_argument(
      '--binary',
      dest='binary',
      required=False,
      help='The path to the Chrome binary.',
      default=None)
  parser.add_argument(
      '--top_n',
      dest='top_n',
      required=False,
      help='Print out top N hottest pages within/outside huge page range(30MB)',
      default=None)
  parser.add_argument(
      '--page_size',
      dest='page_size',
      required=False,
      help='The page size for heat maps.',
      default=4096)
  parser.add_argument('--title', dest='title', default='')

  options = parser.parse_args(argv)

  if not IsARepoRoot(options.chromeos_root):
    parser.error('% does not contain .repo dir.' % options.chromeos_root)

  if not os.path.isfile(options.perf_data):
    parser.error('Cannot find perf_data: %s.' % options.perf_data)

  heatmap_producer = HeatMapProducer(options.chromeos_root, options.perf_data,
                                     options.page_size, options.binary,
                                     options.title)
  try:
    heatmap_producer.copyFileToChroot()
    heatmap_producer.getPerfReport()
    heatmap_producer.getHeatMap(options.top_n)
    print('\nheat map and time histgram genereated in the current directory '
          'with name heat_map.png and timeline.png accordingly.')
  except RuntimeError, e:
    print(e)
  finally:
    heatmap_producer.RemoveFiles()


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
