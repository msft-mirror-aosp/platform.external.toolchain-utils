#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for retrieving the LLVM hash."""

from __future__ import print_function

import mock
import tempfile
import unittest

from cros_utils import command_executer
from get_google3_llvm_version import LLVMVersion
from get_llvm_hash import LLVMHash


class TestGetLLVMHash(unittest.TestCase):
  """The LLVMHash test class."""

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testCloneRepoSucceeds(self, mock_run_commmand_output):
    # Test function to emulate RunCommandWOutput behavior in succeeds case.
    def GoodCloneRepo(clone_cmd, print_to_console):
      # Expected argument to RunCommandWOutput.
      self.assertEqual(clone_cmd.split()[-1], '/tmp/tmpTest')

      # Returns shell error code, stdout, stderr.
      return 0, None, 0

    # Use the test function to simulate RunCommandWOutput behavior.
    mock_run_commmand_output.side_effect = GoodCloneRepo

    TestLLVMHash = LLVMHash()

    # Test the call to _CloneLLVMRepo function.
    TestLLVMHash._CloneLLVMRepo('/tmp/tmpTest')

    mock_run_commmand_output.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testCloneRepoFails(self, mock_run_command_output):
    # Test function to simulate RunCommandWOutput behavior in a failed case.
    def BadCloneRepo(clone_cmd, print_to_console):
      # Make sure an invalid argument is passed in.
      self.assertNotEqual(clone_cmd.split()[-1], '/tmp/tmpTest')

      # Returns shell error code, stdout, stderr.
      return 1, None, 'Invalid path provided'

    # Use the test function to simulate RunCommandWOutput behavior.
    mock_run_command_output.side_effect = BadCloneRepo

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when cloning the repo fails.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash._CloneLLVMRepo('/tmp/tmp1')

    self.assertEqual(err.exception.message, 'Failed to clone the llvm repo: ' \
                     'Invalid path provided')

    mock_run_command_output.assert_called_once()

  @mock.patch.object(tempfile, 'mkdtemp')
  def testCreateTempDirectory(self, mock_create_temp_dir):
    # Test function to simulate mkdtemp behavior.
    def FakeMakeDir():
      # Returns a directory in '/tmp/'.
      return '/tmp/tmpTest'

    # Use the test function to simulate mkdtemp behavior.
    mock_create_temp_dir.side_effect = FakeMakeDir

    TestLLVMHash = LLVMHash()

    self.assertEqual(TestLLVMHash._CreateTempDirectory(), '/tmp/tmpTest')

    mock_create_temp_dir.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailToParseCommitMessage(self, mock_commit_message):
    # Test function to simulate RunCommandWOutput behavior.
    def FakeCommitMessageOutput(find_llvm_cmd, print_to_console):
      # Returns shell error code, stdout, stderr.
      return 1, None, 'Unable to find the llvm version'

    # Use the test function to simulate RunCommandWOutput behavior.
    mock_commit_message.side_effect = FakeCommitMessageOutput

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when failed to parse a commit message.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash._ParseCommitMessages('/tmp/tmpTest',
                                        'a13testhash2 This is a test', 100)

    self.assertEqual(err.exception.message, 'Failed to parse commit message: ' \
                     'Unable to find the llvm version')

    mock_commit_message.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testUnableToFindCommitHash(self, mock_commit_message):
    # Test function to simulate RunCommandWOutput when parsing a
    # commit message body.
    def CustomCommitMessage(find_llvm_cmd, print_to_console):
      commit_message = ('[Test] Test sentence.\n\n'
                        'A change was made.\n\n'
                        'llvm-svn: 1000')

      # Returns shell error code, stdout, stderr.
      return 0, commit_message, 0

    # Use test function to simulate RunCommandWOutput behavior.
    mock_commit_message.side_effect = CustomCommitMessage

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when failed to find the commit hash.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash._ParseCommitMessages('/tmp/tmpTest',
                                        'a13testhash2 This is a test', 100)

    self.assertEqual(err.exception.message, 'Could not find commit hash.')

    mock_commit_message.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFindCommitHashSuccessfully(self, mock_commit_message):
    # Test function will be called 3 times, so
    # 'loop_counter' determines which commit message to return
    loop_counter = [0]

    # Test function to simulate RunCommandWOutput when
    # returning a commit message.
    def MultipleCommitMessages(find_llvm_cmd, print_to_console):
      if loop_counter[0] == 0:  # first iteration
        commit_message_1 = ('[Test] Test sentence.\n\n'
                            'A change was made.\n\n'
                            'llvm-svn: 1001')

        loop_counter[0] += 1

        # Returns shell error code, stdout, stderr.
        return 0, commit_message_1, 0
      if loop_counter[0] == 1:  # second iteration
        # nested commit message containing two 'llvm-svn'
        commit_message_2 = ('[Revert] Reverted commit.\n\n'
                            'This reverts r1000:\n\n'
                            '  [Test2] Update.\n\n'
                            '    This updates stuff.\n\n'
                            '    llvm-svn: 1000\n\n'
                            'llvm-svn: 58')

        loop_counter[0] += 1

        # Returns shell error code, stdout, stderr.
        return 0, commit_message_2, 0
      if loop_counter[0] == 2:  # third iteration
        # nested commit message containing two 'llvm-svn'
        commit_message_3 = ('[Revert] Reverted commit.\n\n'
                            'This reverts r958:\n\n'
                            '  [Test2] Update.\n\n'
                            '    This updates stuff.\n\n'
                            '    llvm-svn: 958\n\n'
                            'llvm-svn: 1000')

        # Returns shell error code, stdout, stderr.
        return 0, commit_message_3, 0

      # Testing function was called more times than expected (3 times)
      assert False, 'RunCommandWOutput was called more than 3 times.'

    # Use test function to simulate RunCommandWOutput behavior.
    mock_commit_message.side_effect = MultipleCommitMessages

    TestLLVMHash = LLVMHash()

    # Test hashes used for parsing.
    #
    # Format:
    #   [Hash] [Commit Summary]
    hash_vals = ('a13testhash2 [Test] Test sentence.\n'
                 'a13testhash3 [Revert] Reverted commit.\n'
                 'a13testhash4 [Revert] Reverted commit.')

    self.assertEqual(
        TestLLVMHash._ParseCommitMessages('/tmp/tmpTest', hash_vals, 1000),
        'a13testhash4')

    self.assertEqual(mock_commit_message.call_count, 3)

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testUnableToGetGitHash(self, mock_hash_val_output):
    # Test function to simulate RunCommandWOuput when unable to
    # find the 'llvm-svn' passed in.
    def FailedHashValOutput(hash_cmd, print_to_console):
      # Returns shell error code, stdout, stderr.
      return 1, None, 'Failed to find specific llvm-svn'

    # Use test function to simulate RunCommandWOutput behavior.
    mock_hash_val_output.side_effect = FailedHashValOutput

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when unable to get the hash for the llvm
    # version.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash.GetGitHashForVersion('/tmp/tmpTest', 100)

    self.assertEqual(err.exception.message,
                     'Hash not found: Failed to find specific llvm-svn')

    mock_hash_val_output.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  @mock.patch.object(LLVMHash, '_ParseCommitMessages')
  def testGetGitHashSuccess(self, mock_return_hash_val, mock_hash_val_output):
    # Test function to simulate RunCommandWOutput when parsing the git log
    # history.
    #
    # Format:
    #   [Hash] [Commit Summary]
    def CustomHashValsOutput(hash_cmd, print_to_console):
      hash_val = 'a13testhash2 [Test] Test sentence.'

      # Returns shell error code, stdout, stderr.
      return 0, hash_val, 0

    # Test function to simulate _ParseCommitMessages when a commit hash is
    # returned.
    def CustomReturnHash(subdir, hash_vals, llvm_version):
      return 'a13testhash2'

    # Use test functions to simulate behavior.
    mock_hash_val_output.side_effect = CustomHashValsOutput
    mock_return_hash_val.side_effect = CustomReturnHash

    TestLLVMHash = LLVMHash()

    self.assertEqual(
        TestLLVMHash.GetGitHashForVersion('/tmp/tmpTest', 100), 'a13testhash2')

    mock_return_hash_val.assert_called_once_with(
        '/tmp/tmpTest/llvm', 'a13testhash2 [Test] Test sentence.', 100)
    mock_hash_val_output.assert_called_once()

  @mock.patch.object(LLVMHash, '_CloneLLVMRepo')
  @mock.patch.object(LLVMHash, '_DeleteTempDirectory')
  @mock.patch.object(LLVMHash, '_CreateTempDirectory')
  def testExceptionWhenGetLLVMHash(self, mock_create_temp_dir,
                                   mock_del_temp_dir, mock_clone_repo):

    # Test function to simulate _CloneLLVMRepo when exception is thrown.
    def FailedCloneRepo(llvm_git_dir):
      raise ValueError('Failed to clone LLVM repo.')

    # Test function to simulate _DeleteTempDirectory when successfully
    # deleted the temp directory.
    def DeletedTempDirectory(llvm_git_dir):
      return True

    # Test function to simulate _CreateTempDirectory when temp directory
    # is returned.
    def CreatedTempDirectory():
      return '/tmp/tmpTest'

    # Use test functions to simulate the behavior.
    mock_clone_repo.side_effect = FailedCloneRepo
    mock_del_temp_dir.side_effect = DeletedTempDirectory
    mock_create_temp_dir.side_effect = CreatedTempDirectory

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when an exception is thrown
    # within the 'try' block
    #
    # Cloning the repo will raise the exception.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash.GetLLVMHash(100)

    self.assertEqual(err.exception.message, 'Failed to clone LLVM repo.')

    mock_del_temp_dir.assert_called_once_with('/tmp/tmpTest')
    mock_clone_repo.assert_called_once()
    mock_create_temp_dir.assert_called_once()

  @mock.patch.object(LLVMHash, '_CloneLLVMRepo')
  @mock.patch.object(LLVMHash, '_DeleteTempDirectory')
  @mock.patch.object(LLVMHash, '_CreateTempDirectory')
  @mock.patch.object(LLVMHash, 'GetGitHashForVersion')
  def testReturnWhenGetLLVMHash(self, mock_get_git_hash, mock_create_temp_dir,
                                mock_del_temp_dir, mock_clone_repo):

    # Test function to simulate _CloneLLVMRepo when successfully cloned the
    # repo.
    def ClonedRepo(llvm_git_dir):
      return True

    # Test function to simulate _DeleteTempDirectory when successfully
    # deleted the temp directory.
    def DeletedTempDirectory(llvm_git_dir):
      return True

    # Test function to simulate _CreateTempDirectory when successfully
    # created the temp directory.
    def CreatedTempDirectory():
      return '/tmp/tmpTest'

    # Test function to simulate GetGitHashForVersion when a hash is returned
    # of its llvm version.
    def ReturnGitHashForVersion(llvm_git_dir, llvm_version):
      return 'a13testhash2'

    # Use test functions to simulate behavior.
    mock_clone_repo.side_effect = ClonedRepo
    mock_del_temp_dir.side_effect = DeletedTempDirectory
    mock_create_temp_dir.side_effect = CreatedTempDirectory
    mock_get_git_hash.side_effect = ReturnGitHashForVersion

    TestLLVMHash = LLVMHash()

    self.assertEqual(TestLLVMHash.GetLLVMHash(100), 'a13testhash2')

    mock_create_temp_dir.assert_called_once()
    mock_clone_repo.assert_called_once_with('/tmp/tmpTest')
    mock_get_git_hash.assert_called_once_with('/tmp/tmpTest', 100)
    mock_del_temp_dir.assert_called_once()

  @mock.patch.object(LLVMHash, 'GetLLVMHash')
  @mock.patch.object(LLVMVersion, 'GetGoogle3LLVMVersion')
  def testReturnGoogle3LLVMHash(self, mock_google3_llvm_version,
                                mock_get_llvm_hash):

    # Test function to simulate GetLLVMHash that returns
    # the hash of the google3 llvm version.
    def ReturnGoogle3LLVMHash(google3_llvm_version):
      return 'a13testhash3'

    # Test function to simulate GetGoogle3LLVMVersion that returns
    # the google3 llvm version.
    def ReturnGoogle3LLVMVersion():
      return 1000

    # Use test functions to simulate behavior.
    mock_get_llvm_hash.side_effect = ReturnGoogle3LLVMHash
    mock_google3_llvm_version.side_effect = ReturnGoogle3LLVMVersion

    TestLLVMHash = LLVMHash()

    self.assertEqual(TestLLVMHash.GetGoogle3LLVMHash(), 'a13testhash3')

    mock_get_llvm_hash.assert_called_once_with(1000)
    mock_google3_llvm_version.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToGetHashFromTopOfTrunk(self, mock_run_cmd):
    # Simulate the behavior of 'RunCommandWOutput()' when failed to get the
    # latest git hash from top of tree of LLVM.
    #
    # Returns shell error code, stdout, stderr.
    mock_run_cmd.return_value = (1, None, 'Could not get git hash from HEAD.')

    TestLLVMHash = LLVMHash()

    # Verify the exception is raised when failed to get the git hash of HEAD
    # from LLVM.
    with self.assertRaises(ValueError) as err:
      TestLLVMHash.GetTopOfTrunkGitHash()

    self.assertEqual(
        err.exception.message,
        'Failed to get the latest git hash from the top of trunk '
        'of LLVM: Could not get git hash from HEAD.')

    mock_run_cmd.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyGetGitHashFromToTOfLLVM(self, mock_run_cmd):
    # Simulate the behavior of 'RunCommandWOutput()' when successfully retrieved
    # the git hash from top of tree of LLVM.
    #
    # Returns shell error code, stdout, stderr.
    mock_run_cmd.return_value = (0, 'a123testhash1 path/to/master\n', 0)

    TestLLVMHash = LLVMHash()

    self.assertEqual(TestLLVMHash.GetTopOfTrunkGitHash(), 'a123testhash1')

    mock_run_cmd.assert_called_once()


if __name__ == '__main__':
  unittest.main()
