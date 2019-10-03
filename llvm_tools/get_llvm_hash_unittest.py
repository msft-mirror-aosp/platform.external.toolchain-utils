#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for retrieving the LLVM hash."""

from __future__ import print_function

import subprocess
import unittest

import get_llvm_hash
from get_llvm_hash import LLVMHash
import mock
import test_helpers

# We grab protected stuff from get_llvm_hash. That's OK.
# pylint: disable=protected-access


def MakeMockPopen(return_code):

  def MockPopen(*_args, **_kwargs):
    result = mock.MagicMock()
    result.returncode = return_code

    communicate_result = result.communicate.return_value
    # Communicate returns stdout, stderr.
    communicate_result.__iter__.return_value = (None, 'some stderr')
    return result

  return MockPopen


class TestGetLLVMHash(unittest.TestCase):
  """The LLVMHash test class."""

  @mock.patch.object(subprocess, 'Popen')
  def testCloneRepoSucceedsWhenGitSucceeds(self, popen_mock):
    popen_mock.side_effect = MakeMockPopen(return_code=0)
    llvm_hash = LLVMHash()

    into_tempdir = '/tmp/tmpTest'
    llvm_hash.CloneLLVMRepo(into_tempdir)
    popen_mock.assert_called_with(
        ['git', 'clone', get_llvm_hash._LLVM_GIT_URL, into_tempdir],
        stderr=subprocess.PIPE)

  @mock.patch.object(subprocess, 'Popen')
  def testCloneRepoFailsWhenGitFails(self, popen_mock):
    popen_mock.side_effect = MakeMockPopen(return_code=1)

    with self.assertRaises(ValueError) as err:
      LLVMHash().CloneLLVMRepo('/tmp/tmp1')

    self.assertIn('Failed to clone', err.exception.message)
    self.assertIn('some stderr', err.exception.message)

  @mock.patch.object(subprocess, 'check_output')
  def testParseCommitMessageWithoutAHashFails(self, check_output_mock):
    check_output_mock.return_value = ('[Test] Test sentence.\n\n'
                                      'A change was made.\n\n'
                                      'llvm-svn: 1000')

    # Verify the exception is raised when failed to find the commit hash.
    with self.assertRaises(ValueError) as err:
      LLVMHash()._ParseCommitMessages('/tmp/tmpTest',
                                      'a13testhash2 This is a test', 100)

    self.assertEqual(err.exception.message, 'Could not find commit hash.')
    check_output_mock.assert_called_once()

  @mock.patch.object(subprocess, 'check_output')
  def testParseCommitMessageIgnoresSVNMarkersInReverts(self, check_output_mock):
    output_messages = [
        '[Test] Test sentence.\n\n'
        'A change was made.\n\n'
        'llvm-svn: 1001',
        '[Revert] Reverted commit.\n\n'
        'This reverts r1000:\n\n'
        '  [Test2] Update.\n\n'
        '    This updates stuff.\n\n'
        '    llvm-svn: 1000\n\n'
        'llvm-svn: 58',
        '[Revert] Reverted commit.\n\n'
        'This reverts r958:\n\n'
        '  [Test2] Update.\n\n'
        '    This updates stuff.\n\n'
        '    llvm-svn: 958\n\n'
        'llvm-svn: 1000',
    ]

    @test_helpers.CallCountsToMockFunctions
    def MultipleCommitMessages(call_count, *_args, **_kwargs):
      return output_messages[call_count]

    check_output_mock.side_effect = MultipleCommitMessages

    hash_vals = ('a13testhash2 [Test] Test sentence.\n'
                 'a13testhash3 [Revert] Reverted commit.\n'
                 'a13testhash4 [Revert] Reverted commit.')

    self.assertEqual(
        LLVMHash()._ParseCommitMessages('/tmp/tmpTest', hash_vals, 1000),
        'a13testhash4')

    self.assertEqual(check_output_mock.call_count, 3)

  @mock.patch.object(subprocess, 'check_output')
  @mock.patch.object(LLVMHash, '_ParseCommitMessages')
  def testGetGitHashWorks(self, mock_return_hash_val, mock_check_output):
    mock_check_output.return_value = 'a13testhash2 [Test] Test sentence.'
    mock_return_hash_val.return_value = 'a13testhash2'

    self.assertEqual(LLVMHash().GetGitHashForVersion('/tmp/tmpTest', 100),
                     'a13testhash2')

    mock_return_hash_val.assert_called_once_with(
        '/tmp/tmpTest', 'a13testhash2 [Test] Test sentence.', 100)
    mock_check_output.assert_called_once()

  @mock.patch.object(LLVMHash, 'GetLLVMHash')
  @mock.patch.object(get_llvm_hash, 'GetGoogle3LLVMVersion')
  def testReturnGoogle3LLVMHash(self, mock_google3_llvm_version,
                                mock_get_llvm_hash):
    mock_get_llvm_hash.return_value = 'a13testhash3'
    mock_google3_llvm_version.return_value = 1000
    self.assertEqual(LLVMHash().GetGoogle3LLVMHash(), 'a13testhash3')
    mock_get_llvm_hash.assert_called_once_with(1000)

  @mock.patch.object(LLVMHash, 'GetLLVMHash')
  @mock.patch.object(get_llvm_hash, 'GetGoogle3LLVMVersion')
  def testReturnGoogle3UnstableLLVMHash(self, mock_google3_llvm_version,
                                        mock_get_llvm_hash):
    mock_get_llvm_hash.return_value = 'a13testhash3'
    mock_google3_llvm_version.return_value = 1000
    self.assertEqual(LLVMHash().GetGoogle3UnstableLLVMHash(), 'a13testhash3')
    mock_get_llvm_hash.assert_called_once_with(1000)

  @mock.patch.object(subprocess, 'check_output')
  def testSuccessfullyGetGitHashFromToTOfLLVM(self, mock_check_output):
    mock_check_output.return_value = 'a123testhash1 path/to/master\n'
    self.assertEqual(LLVMHash().GetTopOfTrunkGitHash(), 'a123testhash1')
    mock_check_output.assert_called_once()


if __name__ == '__main__':
  unittest.main()
