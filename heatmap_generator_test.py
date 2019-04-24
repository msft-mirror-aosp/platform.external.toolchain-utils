#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for heatmap_generator.py."""

from __future__ import division, print_function

import os
import unittest

import heatmap_generator


def _write_perf_mmap(pid, tid, addr, size, fp):
  print(
      '0 0 0 0 PERF_RECORD_MMAP2 %d/%d: '
      '[%x(%x) @ 0x0 0:0 0 0] '
      'r-xp /opt/google/chrome/chrome\n' % (pid, tid, addr, size),
      file=fp)


def _write_perf_fork(pid_from, tid_from, pid_to, tid_to, fp):
  print(
      '0 0 0 0 PERF_RECORD_FORK(%d:%d):(%d:%d)\n' % (pid_to, tid_to, pid_from,
                                                     tid_from),
      file=fp)


def _write_perf_exit(pid_from, tid_from, pid_to, tid_to, fp):
  print(
      '0 0 0 0 PERF_RECORD_EXIT(%d:%d):(%d:%d)\n' % (pid_to, tid_to, pid_from,
                                                     tid_from),
      file=fp)


def _write_perf_sample(pid, tid, addr, fp):
  print(
      '0 0 0 0 PERF_RECORD_SAMPLE(IP, 0x2): '
      '%d/%d: %x period: 100000 addr: 0' % (pid, tid, addr),
      file=fp)
  print(' ... thread: chrome:%d' % tid, file=fp)
  print(' ...... dso: /opt/google/chrome/chrome\n', file=fp)


def _heatmap(file_name, page_size=4096):
  generator = heatmap_generator.HeatmapGenerator(
      file_name, page_size, '', log_level='none')  # Don't log to stdout
  generator.draw()


def _cleanup(file_name):
  os.remove(file_name)
  os.remove('out.txt')
  os.remove('inst-histo.txt')
  os.remove('heat_map.png')
  os.remove('timeline.png')


class Tests(unittest.TestCase):
  """All of our tests for heatmap_generator."""

  def test_with_one_mmap_one_sample(self):
    """Tests one perf record and one sample."""
    fname = 'test.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x100, f)
      _write_perf_sample(101, 101, 0xABCD101, f)
    _heatmap(fname)
    self.assertIn('out.txt', os.listdir('.'))
    with open('out.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 1)
      self.assertIn('101/101: 1 0', lines[0])
    _cleanup(fname)

  def test_with_one_mmap_multiple_samples(self):
    """Tests one perf record and three samples."""
    fname = 'test.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x100, f)
      _write_perf_sample(101, 101, 0xABCD101, f)
      _write_perf_sample(101, 101, 0xABCD102, f)
      _write_perf_sample(101, 101, 0xABCE102, f)
    _heatmap(fname)
    self.assertIn('out.txt', os.listdir('.'))
    with open('out.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 3)
      self.assertIn('101/101: 1 0', lines[0])
      self.assertIn('101/101: 2 0', lines[1])
      self.assertIn('101/101: 3 4096', lines[2])
    _cleanup(fname)

  def test_with_fork_and_exit(self):
    """Tests perf fork and perf exit."""
    fname = 'test_fork.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x100, f)
      _write_perf_fork(101, 101, 202, 202, f)
      _write_perf_sample(101, 101, 0xABCD101, f)
      _write_perf_sample(202, 202, 0xABCE101, f)
      _write_perf_exit(202, 202, 202, 202, f)
    _heatmap(fname)
    self.assertIn('out.txt', os.listdir('.'))
    with open('out.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 2)
      self.assertIn('101/101: 1 0', lines[0])
      self.assertIn('202/202: 2 4096', lines[1])
    _cleanup(fname)

  def test_hugepage_creates_two_chrome_mmaps(self):
    """Test two chrome mmaps for the same process."""
    fname = 'test_hugepage.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x1000, f)
      _write_perf_fork(101, 101, 202, 202, f)
      _write_perf_mmap(202, 202, 0xABCD000, 0x100, f)
      _write_perf_mmap(202, 202, 0xABCD300, 0xD00, f)
      _write_perf_sample(101, 101, 0xABCD102, f)
      _write_perf_sample(202, 202, 0xABCD102, f)
    _heatmap(fname)
    self.assertIn('out.txt', os.listdir('.'))
    with open('out.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 2)
      self.assertIn('101/101: 1 0', lines[0])
      self.assertIn('202/202: 2 0', lines[1])
    _cleanup(fname)

  def test_hugepage_creates_two_chrome_mmaps_fail(self):
    """Test two chrome mmaps for the same process."""
    fname = 'test_hugepage.txt'
    # Cases where first_mmap.size < second_mmap.size
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x1000, f)
      _write_perf_fork(101, 101, 202, 202, f)
      _write_perf_mmap(202, 202, 0xABCD000, 0x10000, f)
    with self.assertRaises(AssertionError) as msg:
      _heatmap(fname)
    self.assertIn('Original MMAP size', str(msg.exception))

    # Cases where first_mmap.address > second_mmap.address
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x1000, f)
      _write_perf_fork(101, 101, 202, 202, f)
      _write_perf_mmap(202, 202, 0xABCC000, 0x10000, f)
    with self.assertRaises(AssertionError) as msg:
      _heatmap(fname)
    self.assertIn('Original MMAP starting address', str(msg.exception))

    # Cases where first_mmap.address + size <
    # second_mmap.address + second_mmap.size
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x1000, f)
      _write_perf_fork(101, 101, 202, 202, f)
      _write_perf_mmap(202, 202, 0xABCD100, 0x10000, f)
    with self.assertRaises(AssertionError) as msg:
      _heatmap(fname)
    self.assertIn('exceeds the end of original MMAP', str(msg.exception))

  def test_histogram(self):
    """Tests if the tool can generate correct histogram.

    In the tool, histogram is generated from statistics
    of perf samples (saved to out.txt). The histogram is
    generated by perf-to-inst-page.sh and saved to
    inst-histo.txt. It will be used to draw heat maps.
    """
    fname = 'test_histo.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x100, f)
      for i in range(0, 100):
        _write_perf_sample(101, 101, 0xABCD000 + i, f)
        _write_perf_sample(101, 101, 0xABCE000 + i, f)
        _write_perf_sample(101, 101, 0xABFD000 + i, f)
        _write_perf_sample(101, 101, 0xAFCD000 + i, f)
    _heatmap(fname)
    self.assertIn('inst-histo.txt', os.listdir('.'))
    with open('inst-histo.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 4)
      self.assertIn('100 0', lines[0])
      self.assertIn('100 4096', lines[1])
      self.assertIn('100 196608', lines[2])
      self.assertIn('100 4194304', lines[3])
    _cleanup(fname)

  def test_histogram_two_mb_page(self):
    """Tests handling of 2MB page."""
    fname = 'test_histo.txt'
    with open(fname, 'w') as f:
      _write_perf_mmap(101, 101, 0xABCD000, 0x100, f)
      for i in range(0, 100):
        _write_perf_sample(101, 101, 0xABCD000 + i, f)
        _write_perf_sample(101, 101, 0xABCE000 + i, f)
        _write_perf_sample(101, 101, 0xABFD000 + i, f)
        _write_perf_sample(101, 101, 0xAFCD000 + i, f)
    _heatmap(fname, page_size=2 * 1024 * 1024)
    self.assertIn('inst-histo.txt', os.listdir('.'))
    with open('inst-histo.txt') as f:
      lines = f.readlines()
      self.assertEqual(len(lines), 2)
      self.assertIn('300 0', lines[0])
      self.assertIn('100 4194304', lines[1])
    _cleanup(fname)


if __name__ == '__main__':
  unittest.main()
