#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for running tryjobs after updating packages."""

from __future__ import print_function

import json
import unittest
import unittest.mock as mock

from test_helpers import ArgsOutputTest
from test_helpers import CreateTemporaryFile
from update_chromeos_llvm_hash import CommitContents
import update_chromeos_llvm_hash
import update_packages_and_test_cq


class UpdatePackagesAndRunTestCQTest(unittest.TestCase):
  """Unittests for CQ dry run after updating packages."""

  def testGetCQDependString(self):
    test_no_changelists = []
    test_single_changelist = [1234]
    test_multiple_changelists = [1234, 5678]

    self.assertEqual(
        update_packages_and_test_cq.GetCQDependString(test_no_changelists),
        None)

    self.assertEqual(
        update_packages_and_test_cq.GetCQDependString(test_single_changelist),
        '\nCq-Depend: chromium:1234')

    self.assertEqual(
        update_packages_and_test_cq.GetCQDependString(
            test_multiple_changelists),
        '\nCq-Depend: chromium:1234, chromium:5678')

  # Mock ExecCommandAndCaptureOutput for the gerrit command execution.
  @mock.patch.object(
      update_packages_and_test_cq,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testStartCQDryRunNoDeps(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'
    test_cl_number = 1000

    # test with no deps cls.
    extra_cls = []
    update_packages_and_test_cq.StartCQDryRun(test_cl_number, extra_cls,
                                              chroot_path)

    expected_gerrit_message = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(test_cl_number), '1'
    ]

    mock_exec_cmd.assert_called_once_with(expected_gerrit_message)

  # Mock ExecCommandAndCaptureOutput for the gerrit command execution.
  @mock.patch.object(
      update_packages_and_test_cq,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  # test with a single deps cl.
  def testStartCQDryRunSingleDep(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'
    test_cl_number = 1000

    extra_cls = [2000]
    update_packages_and_test_cq.StartCQDryRun(test_cl_number, extra_cls,
                                              chroot_path)

    expected_gerrit_cmd_1 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(test_cl_number), '1'
    ]
    expected_gerrit_cmd_2 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(2000), '1'
    ]

    self.assertEqual(mock_exec_cmd.call_count, 2)
    self.assertEqual(mock_exec_cmd.call_args_list[0],
                     mock.call(expected_gerrit_cmd_1))
    self.assertEqual(mock_exec_cmd.call_args_list[1],
                     mock.call(expected_gerrit_cmd_2))

  # Mock ExecCommandAndCaptureOutput for the gerrit command execution.
  @mock.patch.object(
      update_packages_and_test_cq,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testStartCQDryRunMultipleDep(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'
    test_cl_number = 1000

    # test with multiple deps cls.
    extra_cls = [3000, 4000]
    update_packages_and_test_cq.StartCQDryRun(test_cl_number, extra_cls,
                                              chroot_path)

    expected_gerrit_cmd_1 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(test_cl_number), '1'
    ]
    expected_gerrit_cmd_2 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(3000), '1'
    ]
    expected_gerrit_cmd_3 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'label-cq',
        str(4000), '1'
    ]

    self.assertEqual(mock_exec_cmd.call_count, 3)
    self.assertEqual(mock_exec_cmd.call_args_list[0],
                     mock.call(expected_gerrit_cmd_1))
    self.assertEqual(mock_exec_cmd.call_args_list[1],
                     mock.call(expected_gerrit_cmd_2))
    self.assertEqual(mock_exec_cmd.call_args_list[2],
                     mock.call(expected_gerrit_cmd_3))

  # Mock ExecCommandAndCaptureOutput for the gerrit command execution.
  @mock.patch.object(
      update_packages_and_test_cq,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  # test with no reviewers.
  def testAddReviewersNone(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'
    reviewers = []
    test_cl_number = 1000

    update_packages_and_test_cq.AddReviewers(test_cl_number, reviewers,
                                             chroot_path)
    self.assertTrue(mock_exec_cmd.not_called)

  # Mock ExecCommandAndCaptureOutput for the gerrit command execution.
  @mock.patch.object(
      update_packages_and_test_cq,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  # test with multiple reviewers.
  def testAddReviewersMultiple(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'
    reviewers = ['none1@chromium.org', 'none2@chromium.org']
    test_cl_number = 1000

    update_packages_and_test_cq.AddReviewers(test_cl_number, reviewers,
                                             chroot_path)

    expected_gerrit_cmd_1 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'reviewers',
        str(test_cl_number), 'none1@chromium.org'
    ]
    expected_gerrit_cmd_2 = [
        '%s/chromite/bin/gerrit' % chroot_path, 'reviewers',
        str(test_cl_number), 'none2@chromium.org'
    ]

    self.assertEqual(mock_exec_cmd.call_count, 2)
    self.assertEqual(mock_exec_cmd.call_args_list[0],
                     mock.call(expected_gerrit_cmd_1))
    self.assertEqual(mock_exec_cmd.call_args_list[1],
                     mock.call(expected_gerrit_cmd_2))


if __name__ == '__main__':
  unittest.main()
