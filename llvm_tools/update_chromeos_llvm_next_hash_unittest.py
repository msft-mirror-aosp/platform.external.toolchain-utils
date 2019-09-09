#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for updating the LLVM next hash."""

from __future__ import print_function

from collections import namedtuple
from pipes import quote
from tempfile import mkstemp
import os
import unittest

from cros_utils import command_executer
from failure_modes import FailureModes
from test_helpers import CallCountsToMockFunctions
import llvm_patch_management
import mock
import update_chromeos_llvm_next_hash

# These are unittests; protected access is OK to a point.
# pylint: disable=protected-access


class UpdateLLVMNextHashTest(unittest.TestCase):
  """Test class for updating 'LLVM_NEXT_HASH' of packages."""

  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def testFailedToGetChrootPathForInvalidPackage(self, mock_chroot_command):

    # Emulate ChrootRunCommandWOutput behavior when an invalid package is
    # passed in.
    #
    # Returns shell error code, stdout, stderr.
    mock_chroot_command.return_value = (1, None, 'Invalid package provided.')

    # Verify the exception is raised when an invalid package is passed in.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.GetChrootBuildPaths(
          '/test/chroot/path', ['test-pckg/test'])

    self.assertEqual(
        err.exception.message,
        'Failed to get chroot path for the package (test-pckg/test): '
        'Invalid package provided.')

    mock_chroot_command.assert_called_once_with(
        chromeos_root='/test/chroot/path',
        command='equery w test-pckg/test',
        print_to_console=False)

  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def testSucceedsToGetChrootPathForPackage(self, mock_chroot_command):
    # Emulate ChrootRunCommandWOutput behavior when a chroot path is found for
    # a valid package.
    #
    # Returns shell error code, stdout, stderr.
    mock_chroot_command.return_value = (0, '/chroot/path/to/package.ebuild\n',
                                        0)

    self.assertEqual(
        update_chromeos_llvm_next_hash.GetChrootBuildPaths(
            '/test/chroot/path', ['new-test/package']),
        ['/chroot/path/to/package.ebuild'])

    mock_chroot_command.assert_called_once_with(
        chromeos_root='/test/chroot/path',
        command='equery w new-test/package',
        print_to_console=False)

  def testFailedToConvertChrootPathWithInvalidPrefixToSymlinkPath(self):
    # Verify the exception is raised when a symlink does not have the prefix
    # '/mnt/host/source/'.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash._ConvertChrootPathsToSymLinkPaths(
          '/path/to/chroot', ['/src/package.ebuild'])

    self.assertEqual(
        err.exception.message, 'Invalid prefix for the chroot path: '
        '/src/package.ebuild')

  def testSucceedsToConvertChrootPathToSymlinkPath(self):
    self.assertEqual(
        update_chromeos_llvm_next_hash._ConvertChrootPathsToSymLinkPaths(
            '/path/to/chroot', ['/mnt/host/source/src/package.ebuild']),
        ['/path/to/chroot/src/package.ebuild'])

  # Simulate 'os.path.islink' when a path is not a symbolic link.
  @mock.patch.object(os.path, 'islink', return_value=False)
  def testFailedToGetEbuildPathFromInvalidSymlink(self, mock_islink):
    # Verify the exception is raised when the argument is not a symbolic link.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.GetEbuildPathsFromSymLinkPaths(
          ['/symlink/path/src/to/package-r1.ebuild'])

    self.assertEqual(
        err.exception.message,
        'Invalid symlink provided: /symlink/path/src/to/package-r1.ebuild')

    mock_islink.assert_called_once_with(
        '/symlink/path/src/to/package-r1.ebuild')

  # Simulate 'os.path.islink' when a path is a symbolic link.
  @mock.patch.object(os.path, 'islink', return_value=True)
  @mock.patch.object(os.path, 'realpath')
  def testSucceedsToGetEbuildPathFromValidSymlink(self, mock_realpath,
                                                  mock_islink):

    # Simulate 'os.path.realpath' when a valid path is passed in.
    mock_realpath.return_value = '/abs/path/to/src/package.ebuild'

    self.assertEqual(
        update_chromeos_llvm_next_hash.GetEbuildPathsFromSymLinkPaths(
            ['/path/to/chroot/src/package-r1.ebuild']), {
                '/path/to/chroot/src/package-r1.ebuild':
                    '/abs/path/to/src/package.ebuild'
            })

    mock_realpath.assert_called_once_with(
        '/path/to/chroot/src/package-r1.ebuild')

    mock_islink.assert_called_once_with('/path/to/chroot/src/package-r1.ebuild')

  # Simulate behavior of 'os.path.isfile()' when the ebuild path to a package
  # does not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testFailedToUpdateLLVMNextHashForInvalidEbuildPath(self, mock_isfile):
    # Verify the exception is raised when the ebuild path does not exist.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UpdateBuildLLVMNextHash(
          '/some/path/to/package.ebuild', 'a123testhash1', 1000)

    self.assertEqual(
        err.exception.message,
        'Invalid ebuild path provided: /some/path/to/package.ebuild')

    mock_isfile.assert_called_once()

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testFailedToUpdateLLVMNextHash(self, mock_isfile):
    # Create a temporary file to simulate an ebuild file of a package.
    ebuild_file, file_path = mkstemp()

    os.write(
        ebuild_file, '\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'Last line in the ebuild'
        ]))

    os.close(ebuild_file)

    try:
      # Verify the exception is raised when the ebuild file does not have
      # 'LLVM_NEXT_HASH'.
      with self.assertRaises(ValueError) as err:
        update_chromeos_llvm_next_hash.UpdateBuildLLVMNextHash(
            file_path, 'a123testhash1', 1000)

      self.assertEqual(err.exception.message, 'Failed to update the LLVM hash.')
    finally:
      os.remove(file_path)

    mock_isfile.assert_called_once()

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToStageTheEbuildForCommitForLLVMNextHashUpdate(
      self, mock_stage_commit_command, mock_isfile):

    # Simulate 'RunCommandWOutput' when failed to stage the ebuild file for
    # commit.
    #
    # Returns shell error code, stdout, stderr.
    mock_stage_commit_command.return_value = (1, None, 'Failed to add file.')

    # Create a temporary file to simulate an ebuild file of a package.
    ebuild_file, file_path = mkstemp()

    os.write(
        ebuild_file, '\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'LLVM_NEXT_HASH=\"a12b34c56d78e90\" # r500',
            'Last line in the ebuild'
        ]))

    os.close(ebuild_file)

    try:
      # Verify the exception is raised when staging the ebuild file.
      with self.assertRaises(ValueError) as err:
        update_chromeos_llvm_next_hash.UpdateBuildLLVMNextHash(
            file_path, 'a123testhash1', 1000)

      self.assertEqual(
          err.exception.message, 'Failed to stage the ebuild for commit: '
          'Failed to add file.')

      expected_file_contents = [
          'First line in the ebuild\n', 'Second line in the ebuild\n',
          'LLVM_NEXT_HASH=\"a123testhash1\" # r1000\n',
          'Last line in the ebuild'
      ]

      # Verify the new file contents of the ebuild file match
      # the expected file contents.
      with open(file_path) as new_file:
        file_contents_as_a_list = [cur_line for cur_line in new_file]
        self.assertListEqual(file_contents_as_a_list, expected_file_contents)

    finally:
      os.remove(file_path)

    mock_isfile.assert_called_once()
    mock_stage_commit_command.assert_called_once()

  # Simulate 'os.path.isfile' behavior on a valid ebuild path.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyStageTheEbuildForCommitForLLVMNextHashUpdate(
      self, mock_stage_commit_command, mock_isfile):

    # Simulate 'RunCommandWOutput' when successfully staged the ebuild file for
    # commit.
    #
    # Returns shell error code, stdout, stderr.
    mock_stage_commit_command.return_value = (0, None, 0)

    # Create a temporary file to simulate an ebuild file of a package.
    ebuild_file, file_path = mkstemp()

    os.write(
        ebuild_file, '\n'.join([
            'First line in the ebuild', 'Second line in the ebuild',
            'LLVM_NEXT_HASH=\"a12b34c56d78e90\" # r500',
            'Last line in the ebuild'
        ]))

    os.close(ebuild_file)

    try:
      update_chromeos_llvm_next_hash.UpdateBuildLLVMNextHash(
          file_path, 'a123testhash1', 1000)

      expected_file_contents = [
          'First line in the ebuild\n', 'Second line in the ebuild\n',
          'LLVM_NEXT_HASH=\"a123testhash1\" # r1000\n',
          'Last line in the ebuild'
      ]

      # Verify the new file contents of the ebuild file match the expected file
      # contents.
      with open(file_path) as new_file:
        file_contents_as_a_list = [cur_line for cur_line in new_file]
        self.assertListEqual(file_contents_as_a_list, expected_file_contents)

    finally:
      os.remove(file_path)

    mock_isfile.assert_called_once()
    mock_stage_commit_command.assert_called_once()

  # Simulate behavior of 'os.path.islink()' when the argument passed in is not a
  # symbolic link.
  @mock.patch.object(os.path, 'islink', return_value=False)
  def testFailedToUprevEbuildForInvalidSymlink(self, mock_islink):
    # Verify the exception is raised when a symbolic link is not passed in.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UprevEbuild('/symlink/to/package.ebuild')

    self.assertEqual(err.exception.message,
                     'Invalid symlink provided: /symlink/to/package.ebuild')

    mock_islink.assert_called_once()

  # Simulate 'os.path.islink' when a symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  def testFailedToUprevEbuild(self, mock_islink):
    # Verify the exception is raised when the symlink does not have a revision
    # number.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UprevEbuild('/symlink/to/package.ebuild')

    self.assertEqual(err.exception.message, 'Failed to uprev the ebuild.')

    mock_islink.assert_called_once_with('/symlink/to/package.ebuild')

  # Simulate 'os.path.islink' when a valid symbolic link is passed in.
  @mock.patch.object(os.path, 'islink', return_value=True)
  # Simulate 'os.path.dirname' when returning a path to the directory of a
  # valid symbolic link.
  @mock.patch.object(os.path, 'dirname', return_value='/symlink/to')
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyUprevEbuild(self, mock_command_output, mock_dirname,
                                  mock_islink):

    # Simulate 'RunCommandWOutput' when the symbolic link was incremented by 1
    # and staged for commit.
    #
    # Returns shell error code, stdout, stderr.
    mock_command_output.return_value = (0, None, 0)

    update_chromeos_llvm_next_hash.UprevEbuild('/symlink/to/package-r1.ebuild')

    mock_islink.assert_called_once_with('/symlink/to/package-r1.ebuild')

    mock_dirname.assert_called_once_with('/symlink/to/package-r1.ebuild')

    mock_command_output.assert_called_once_with(
        'git -C /symlink/to mv '
        '/symlink/to/package-r1.ebuild /symlink/to/package-r2.ebuild',
        print_to_console=False)

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a
  # directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToCreateRepoForInvalidDirectoryPath(self, mock_isdir):
    # Verify the exception is raised when provided an invalid directory path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash._CreateRepo('/path/to/repo',
                                                 'a123testhash1')

    self.assertEqual(err.exception.message,
                     'Invalid directory path provided: /path/to/repo')

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' when the path to the repo is valid.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToCreateRepo(self, mock_command_output, mock_isdir):
    # Simulate 'RunCommandWOutput' when 'repo start' fails.
    #
    # Returns shell error code, stdout, stderr.
    mock_command_output.return_value = (1, None, 'Invalid branch name.')

    # Verify exception is raised when failed to create a repo for the changes.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash._CreateRepo('/path/to/repo',
                                                 'a123testhash1')

    self.assertEqual(
        err.exception.message,
        'Failed to create the repo (llvm-next-update-a123testhash1): '
        'Invalid branch name.')

    mock_isdir.assert_called_once_with('/path/to/repo')

    mock_command_output.assert_called_once()

  # Simulate 'os.path.isdir' when a valid repo path is provided.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyCreatedRepo(self, mock_command_output, mock_isdir):
    # Test function to simulate 'RunCommandWOutput' when 'repo start' succeeds.
    def GoodRepoStart(create_repo_cmd, _print_to_console):
      self.assertEqual(create_repo_cmd.split()[-1],
                       'llvm-next-update-a123testhash1')

      # Returns shell error code, stdout, stderr.
      return 0, None, 0

    # Use test function to simulate 'RunCommandWOutput' behavior.
    mock_command_output.side_effect = GoodRepoStart

    update_chromeos_llvm_next_hash._CreateRepo('/path/to/repo', 'a123testhash1')

    mock_isdir.assert_called_once_with('/path/to/repo')

    mock_command_output.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a
  # directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToDeleteRepoForInvalidDirectoryPath(self, mock_isdir):
    # Verify the exception is raised on an invalid repo path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash._DeleteRepo('/some/path/to/repo',
                                                 'a123testhash2')

    self.assertEqual(err.exception.message,
                     'Invalid directory path provided: /some/path/to/repo')

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' on a valid directory.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToDeleteRepo(self, mock_command_output, mock_isdir):
    # Simulate 'RunCommandWOutput' when failed to delete a branch.
    #
    # Returns shell error code, stdout, stderr.
    mock_command_output.return_value = (1, None, 'Invalid branch name.')

    # Verify exception is raised when failed to delete the repo.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash._DeleteRepo('/some/path/to/repo',
                                                 'a123testhash2')

    self.assertEqual(
        err.exception.message,
        'Failed to delete the repo (llvm-next-update-a123testhash2): '
        'Invalid branch name.')

    mock_isdir.assert_called_once_with('/some/path/to/repo')

    mock_command_output.assert_called_once()

  # Simulate 'os.path.isdir' on valid directory path.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyDeletedRepo(self, mock_command_output, mock_isdir):
    # Test function to simulate 'RunCommandWOutput' when successfully deleted a
    # repo.
    def GoodRepoDelete(create_repo_cmd, _print_to_console):
      self.assertEqual(create_repo_cmd.split()[-1],
                       'llvm-next-update-a123testhash2')

      # Returns shell error code, stdout, stderr.
      return 0, None, 0

    # Use test function to simulate 'RunCommandWOutput' behavior.
    mock_command_output.side_effect = GoodRepoDelete

    update_chromeos_llvm_next_hash._DeleteRepo('/some/path/to/repo',
                                               'a123testhash2')

    mock_isdir.assert_called_once_with('/some/path/to/repo')

    mock_command_output.assert_called_once()

  def testFailedToFindChangeListURL(self):
    repo_upload_contents = 'remote:   https://some_url'

    # Verify the exception is raised when failed to find the Gerrit URL when
    # parsing the 'repo upload' contents.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.GetGerritRepoUploadContents(
          repo_upload_contents)

    self.assertEqual(err.exception.message, 'Failed to find change list URL.')

  def testSuccessfullyGetGerritRepoUploadContents(self):
    repo_upload_contents = ('remote:   https://chromium-review.googlesource.com'
                            '/c/chromiumos/overlays/chromiumos-overlay/+/'
                            '193147 Some commit header')

    change_list = update_chromeos_llvm_next_hash.GetGerritRepoUploadContents(
        repo_upload_contents)

    self.assertEqual(
        change_list.url,
        'https://chromium-review.googlesource.com/c/chromiumos/overlays/'
        'chromiumos-overlay/+/193147')

    self.assertEqual(change_list.cl_number, 193147)

  # Simulate behavior of 'os.path.isdir()' when the path to the repo is not a
  # directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testFailedToUploadChangesForInvalidPathDirectory(self, mock_isdir):
    # Verify exception is raised when on an invalid repo path.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UploadChanges(
          '/some/path/to/repo', 'a123testhash3', '-m \"Test message\"')

    self.assertEqual(err.exception.message,
                     'Invalid directory path provided: /some/path/to/repo')

    mock_isdir.assert_called_once()

  # Simulate 'os.path.isdir' on a valid repo directory.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToCreateACommitForTheChanges(self, mock_command_output,
                                             mock_isdir):

    # Simulate 'RunCommandWOutput' when failed to create a commit for the
    # changes.
    #
    # Returns shell error code, stdout, stderr.
    mock_command_output.return_value = (1, None, 'Nothing to commit.')

    # Verify exception is raised when failed to create a commit.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UploadChanges(
          '/some/path/to/repo', 'a123testhash3', '-m \"Test message\"')

    self.assertEqual(
        err.exception.message,
        'Failed to create a commit for the changes: Nothing to commit.')

    mock_isdir.assert_called_once_with('/some/path/to/repo')

    mock_command_output.assert_called_once_with(
        'cd /some/path/to/repo && git commit -m \"Test message\"',
        print_to_console=False)

  # Simulate 'os.path.isdir' on a valid repo path.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToUploadChangesForReview(self, mock_command_output, mock_isdir):
    # Test function to simulate 'RunCommandWOutput' when attempting to create
    # a commit and upload the changes for review.
    @CallCountsToMockFunctions
    def MultipleCallsToUploadACommit(call_count, cmd, _print_to_console):
      # Creating a commit for the changes.
      if call_count == 0:  # first call to 'RunCommandWOutput'
        self.assertEqual(
            cmd, 'cd /some/path/to/repo && git commit -m \"Test message\"')

        # Returns shell error code, stdout, stderr.
        return 0, None, 0

      # Trying to upload the commit for review.
      if call_count == 1:  # second call to 'RunCommandWOutput'
        # Make sure the branch name matches expected.
        self.assertEqual(cmd.split()[-2], '--br=llvm-next-update-a123testhash3')

        # Returns shell error code, stdout, stderr.
        return 1, None, 'Branch does not exist.'

      # Testing function was called more times than expected (2 times).
      assert False, 'RunCommandWOutput was called more than 2 times.'

    # Use test function to simulate 'RunCommandWOutput' behavior.
    mock_command_output.side_effect = MultipleCallsToUploadACommit

    # Verify exception is raised when failed to upload the changes for review.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UploadChanges(
          '/some/path/to/repo', 'a123testhash3', '-m \"Test message\"')

    self.assertEqual(
        err.exception.message,
        'Failed to upload changes for review: Branch does not exist.')

    mock_isdir.assert_called_once_with('/some/path/to/repo')

    self.assertEqual(mock_command_output.call_count, 2)

  # Simulate 'os.path.isdir' when a valid repo path is passed in.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyUploadedChangesForReview(self, mock_command_output,
                                               mock_isdir):

    # Test function to simulate 'RunCommandWOutput' when creating a commit for
    # the changes and uploading the changes for review.
    @CallCountsToMockFunctions
    def MultipleCallsToUploadACommit(call_count, cmd, _print_to_console):
      # Creating a commit in the repo path.
      if call_count == 0:  # first call to 'RunCommandWOutput'
        self.assertEqual(
            cmd, 'cd /some/path/to/repo && git commit -m \"Test message\"')

        # Returns shell error code, stdout, stderr.
        return 0, None, 0
      # Uploading the changes for review.
      if call_count == 1:  # second call to 'RunCommandWOutput'
        # Make sure the branch name matches expected.
        self.assertEqual(cmd.split()[-2], '--br=llvm-next-update-a123testhash3')

        repo_upload_contents = ('remote: https://chromium-review.googlesource.'
                                'com/c/chromiumos/overlays/chromiumos-overlay/'
                                '+/193147 Fix stdout')

        # Returns shell error code, stdout, stderr.
        return 0, None, repo_upload_contents

      # Testing function was called more times than expected (2 times).
      assert False, 'RunCommandWOutput was called more than 2 times.'

    # Use test function to simulate 'RunCommandWOutput' behavior.
    mock_command_output.side_effect = MultipleCallsToUploadACommit

    change_list = update_chromeos_llvm_next_hash.UploadChanges(
        '/some/path/to/repo', 'a123testhash3', '-m \"Test message\"')

    self.assertEqual(
        change_list.url,
        'https://chromium-review.googlesource.com/c/chromiumos/overlays/'
        'chromiumos-overlay/+/193147')

    self.assertEqual(change_list.cl_number, 193147)

    mock_isdir.assert_called_once_with('/some/path/to/repo')

    self.assertEqual(mock_command_output.call_count, 2)

  @mock.patch.object(update_chromeos_llvm_next_hash, 'GetChrootBuildPaths')
  @mock.patch.object(update_chromeos_llvm_next_hash,
                     '_ConvertChrootPathsToSymLinkPaths')
  def testExceptionRaisedWhenCreatingPathDictionaryFromPackages(
      self, mock_chroot_paths_to_symlinks, mock_get_chroot_paths):

    # Test function to simulate '_ConvertChrootPathsToSymLinkPaths' when a
    # symlink does not start with the prefix '/mnt/host/source'.
    def BadPrefixChrootPath(_chroot_path, _chroot_file_paths):
      raise ValueError('Invalid prefix for the chroot path: '
                       '/some/chroot/path/to/package-r1.ebuild')

    # Simulate 'GetChrootBuildPaths' when valid packages are passed in.
    #
    # Returns a list of chroot paths.
    mock_get_chroot_paths.return_value = [
        '/some/chroot/path/to/package-r1.ebuild'
    ]

    # Use test function to simulate '_ConvertChrootPathsToSymLinkPaths'
    # behavior.
    mock_chroot_paths_to_symlinks.side_effect = BadPrefixChrootPath

    # Verify exception is raised when for an invalid prefix in the symlink.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.CreatePathDictionaryFromPackages(
          '/some/path/to/chroot', ['test-pckg/package'])

    self.assertEqual(
        err.exception.message, 'Invalid prefix for the chroot path: '
        '/some/chroot/path/to/package-r1.ebuild')

    mock_get_chroot_paths.assert_called_once_with('/some/path/to/chroot',
                                                  ['test-pckg/package'])

    mock_chroot_paths_to_symlinks.assert_called_once_with(
        '/some/path/to/chroot', ['/some/chroot/path/to/package-r1.ebuild'])

  @mock.patch.object(update_chromeos_llvm_next_hash, 'GetChrootBuildPaths')
  @mock.patch.object(update_chromeos_llvm_next_hash,
                     '_ConvertChrootPathsToSymLinkPaths')
  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'GetEbuildPathsFromSymLinkPaths')
  def testSuccessfullyCreatedPathDictionaryFromPackages(
      self, mock_ebuild_paths_from_symlink_paths, mock_chroot_paths_to_symlinks,
      mock_get_chroot_paths):

    # Simulate 'GetChrootBuildPaths' when returning a chroot path for a valid
    # package.
    #
    # Returns a list of chroot paths.
    mock_get_chroot_paths.return_value = [
        '/mnt/host/source/src/path/to/package-r1.ebuild'
    ]

    # Simulate '_ConvertChrootPathsToSymLinkPaths' when returning a symlink to
    # a chroot path that points to a package.
    #
    # Returns a list of symlink file paths.
    mock_chroot_paths_to_symlinks.return_value = [
        '/some/path/to/chroot/src/path/to/package-r1.ebuild'
    ]

    # Simulate 'GetEbuildPathsFromSymlinkPaths' when returning a dictionary of
    # a symlink that points to an ebuild.
    #
    # Returns a dictionary of a symlink and ebuild file path pair
    # where the key is the absolute path to the symlink of the ebuild file
    # and the value is the absolute path to the ebuild file of the package.
    mock_ebuild_paths_from_symlink_paths.return_value = {
        '/some/path/to/chroot/src/path/to/package-r1.ebuild':
            '/some/path/to/chroot/src/path/to/package.ebuild'
    }

    self.assertEqual(
        update_chromeos_llvm_next_hash.CreatePathDictionaryFromPackages(
            '/some/path/to/chroot', ['test-pckg/package']), {
                '/some/path/to/chroot/src/path/to/package-r1.ebuild':
                    '/some/path/to/chroot/src/path/to/package.ebuild'
            })

    mock_get_chroot_paths.assert_called_once_with('/some/path/to/chroot',
                                                  ['test-pckg/package'])

    mock_chroot_paths_to_symlinks.assert_called_once_with(
        '/some/path/to/chroot',
        ['/mnt/host/source/src/path/to/package-r1.ebuild'])

    mock_ebuild_paths_from_symlink_paths.assert_called_once_with(
        ['/some/path/to/chroot/src/path/to/package-r1.ebuild'])

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToRemovePatchFromFilesDir(self, mock_run_cmd):
    # Simulate the behavior of 'RunCommandWOutput()' when failed to remove a
    # patch whose absolute path does not exist.
    #
    # Returns shell error code, stdout, stderr.
    mock_run_cmd.return_value = (1, None, 'Patch does not exist.')

    # Verify the exception is raised when the patch does not exist and the
    # command executer attempts to remove the patch.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.RemovePatchesFromFilesDir([
          '/abs/path/to/filesdir/display_results.patch',
          '/abs/path/to/filesdir/cherry/fix_output.patch'
      ])

    self.assertEqual(
        err.exception.message, 'Failed to remove patch display_results.patch: '
        'Patch does not exist.')

    self.assertEqual(mock_run_cmd.call_count, 1)

    mock_run_cmd.assert_called_once_with(
        'git -C /abs/path/to/filesdir rm -f '
        '/abs/path/to/filesdir/display_results.patch',
        print_to_console=False)

  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyRemovedPatchesFromFilesDir(self, mock_run_cmd):
    # Simulate the behavior of 'RunCommandWOutput()' when all patches exist and
    # were removed from $FILESDIR.
    @CallCountsToMockFunctions
    def MultipleCallsToRemovePatches(call_count, rm_cmd, print_to_console):
      # First patch to remove from $FILESDIR.
      if call_count == 0:
        self.assertEqual(
            rm_cmd, 'git -C /abs/path/to/filesdir/cherry rm -f '
            '/abs/path/to/filesdir/cherry/fix_output.patch')
        self.assertFalse(print_to_console)

        # Returns shell error code, stdout, stderr.
        return 0, None, 0

      # Second (and last patch) to remove from $FILESDIR.
      if call_count == 1:
        self.assertEqual(
            rm_cmd, 'git -C /abs/path/to/filesdir rm -f '
            '/abs/path/to/filesdir/display_results.patch')
        self.assertFalse(print_to_console)

        # Returns shell error code, stdout, stderr.
        return 0, None, 0

      # 'RunCommandWOutput()' called more than times than expected (2 times).
      assert False, 'Unexpectedly called more than 2 times.'

    # Use test function to simulate 'RunCommandWOutput()' behavior.
    mock_run_cmd.side_effect = MultipleCallsToRemovePatches

    update_chromeos_llvm_next_hash.RemovePatchesFromFilesDir([
        '/abs/path/to/filesdir/cherry/fix_output.patch',
        '/abs/path/to/filesdir/display_results.patch'
    ])

    self.assertEqual(mock_run_cmd.call_count, 2)

  # Simulate behavior of 'os.path.isfile()' when the absolute path to the patch
  # metadata file does not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testInvalidPatchMetadataFileStagedForCommit(self, mock_isfile):
    # Verify the exception is raised when the absolute path to the patch
    # metadata file does not exist or is not a file.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.StagePatchMetadataFileForCommit(
          '/abs/path/to/filesdir/PATCHES')

    self.assertEqual(
        err.exception.message, 'Invalid patch metadata file provided: '
        '/abs/path/to/filesdir/PATCHES')

    mock_isfile.assert_called_once()

  # Simulate the behavior of 'os.path.isfile()' when the absolute path to the
  # patch metadata file exists.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testFailedToStagePatchMetadataFileForCommit(self, mock_run_cmd,
                                                  _mock_isfile):

    # Simulate the behavior of 'RunCommandWOutput()' when failed to stage the
    # patch metadata file for commit.
    #
    # Returns shell error code, stdout, stderr.
    mock_run_cmd.return_value = (1, None, 'No changes made to the file.')

    # Verify the exception is raised when no changes were made to the patch
    # metadata file when attempting to stage the file for commit.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.StagePatchMetadataFileForCommit(
          '/abs/path/to/filesdir/PATCHES.json')

    self.assertEqual(
        err.exception.message,
        'Failed to stage patch metadata file PATCHES.json for '
        'commit: No changes made to the file.')

    mock_run_cmd.assert_called_once_with(
        'git -C /abs/path/to/filesdir add /abs/path/to/filesdir/PATCHES.json',
        print_to_console=False)

  # Simulate the behavior of 'os.path.isfile()' when the absolute path to the
  # patch metadata file exists.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter, 'RunCommandWOutput')
  def testSuccessfullyStagedPatchMetadataFileForCommit(self, mock_run_cmd,
                                                       _mock_isfile):

    # Simulate the behavior of 'RunCommandWOutput()' when successfully staged
    # the patch metadata file for commit.
    #
    # Returns shell error code, stdout, stderr.
    mock_run_cmd.return_value = (0, None, 0)

    update_chromeos_llvm_next_hash.StagePatchMetadataFileForCommit(
        '/abs/path/to/filesdir/PATCHES.json')

    mock_run_cmd.assert_called_once_with(
        'git -C /abs/path/to/filesdir add /abs/path/to/filesdir/PATCHES.json',
        print_to_console=False)

  def testNoPatchResultsForCommit(self):
    package_1_patch_info_dict = {
        'applied_patches': ['display_results.patch'],
        'failed_patches': ['fixes_output.patch'],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    package_2_patch_info_dict = {
        'applied_patches': ['redirects_stdout.patch', 'fix_display.patch'],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    test_package_info_dict = {
        'test-packages/package1': package_1_patch_info_dict,
        'test-packages/package2': package_2_patch_info_dict
    }

    test_commit_message = ['-m %s' % quote('Updated packages')]

    self.assertListEqual(
        update_chromeos_llvm_next_hash.StagePackagesPatchResultsForCommit(
            test_package_info_dict, test_commit_message), test_commit_message)

  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'StagePatchMetadataFileForCommit')
  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'RemovePatchesFromFilesDir')
  def testAddedPatchResultsForCommit(self, mock_remove_patches,
                                     mock_stage_patches_for_commit):

    package_1_patch_info_dict = {
        'applied_patches': [],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': ['fixes_output.patch'],
        'removed_patches': [],
        'modified_metadata': '/abs/path/to/filesdir/PATCHES.json'
    }

    package_2_patch_info_dict = {
        'applied_patches': ['fix_display.patch'],
        'failed_patches': [],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': ['/abs/path/to/filesdir/redirect_stdout.patch'],
        'modified_metadata': '/abs/path/to/filesdir/PATCHES.json'
    }

    test_package_info_dict = {
        'test-packages/package1': package_1_patch_info_dict,
        'test-packages/package2': package_2_patch_info_dict
    }

    test_commit_message = ['-m %s' % quote('Updated packages')]

    expected_commit_messages = [
        '-m %s' % quote('Updated packages'),
        '-m %s' % quote('For the package test-packages/package2:'),
        '-m %s' % quote('The patch metadata file PATCHES.json was modified'),
        '-m %s' % quote('The following patches were removed:'),
        '-m %s' % quote('redirect_stdout.patch'),
        '-m %s' % quote('For the package test-packages/package1:'),
        '-m %s' % quote('The patch metadata file PATCHES.json was modified'),
        '-m %s' % quote('The following patches were disabled:'),
        '-m %s' % quote('fixes_output.patch')
    ]

    self.assertListEqual(
        update_chromeos_llvm_next_hash.StagePackagesPatchResultsForCommit(
            test_package_info_dict, test_commit_message),
        expected_commit_messages)

    mock_remove_patches.assert_called_once_with(
        ['/abs/path/to/filesdir/redirect_stdout.patch'])

    self.assertEqual(mock_stage_patches_for_commit.call_count, 2)

  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'CreatePathDictionaryFromPackages')
  @mock.patch.object(update_chromeos_llvm_next_hash, '_CreateRepo')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UpdateBuildLLVMNextHash')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UprevEbuild')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UploadChanges')
  @mock.patch.object(update_chromeos_llvm_next_hash, '_DeleteRepo')
  def testExceptionRaisedWhenUpdatingPackages(
      self, mock_delete_repo, mock_upload_changes, mock_uprev_ebuild,
      mock_update_llvm_next, mock_create_repo, mock_create_path_dict):

    # Test function to simulate '_CreateRepo' when successfully created the
    # repo on a valid repo path.
    def SuccessfullyCreateRepoForChanges(_repo_path, llvm_hash):
      self.assertEqual(llvm_hash, 'a123testhash4')
      return

    # Test function to simulate 'UpdateBuildLLVMNextHash' when successfully
    # updated the ebuild's 'LLVM_NEXT_HASH'.
    def SuccessfullyUpdatedLLVMNextHash(ebuild_path, llvm_hash, llvm_version):
      self.assertEqual(ebuild_path,
                       '/some/path/to/chroot/src/path/to/package.ebuild')
      self.assertEqual(llvm_hash, 'a123testhash4')
      self.assertEqual(llvm_version, 1000)
      return

    # Test function to simulate 'UprevEbuild' when the symlink to the ebuild
    # does not have a revision number.
    def FailedToUprevEbuild(_symlink_path):
      # Raises a 'ValueError' exception because the symlink did not have have a
      # revision number.
      raise ValueError('Failed to uprev the ebuild.')

    # Test function to fail on 'UploadChanges' if the function gets called
    # when an exception is raised.
    def ShouldNotExecuteUploadChanges(_repo_path, _llvm_hash,
                                      _commit_messages):
      # Test function should not be called (i.e. execution should resume in the
      # 'finally' block) because 'UprevEbuild()' raised an
      # exception.
      assert False, "Failed to go to 'finally' block " \
          'after the exception was raised.'

    test_package_path_dict = {
        '/some/path/to/chroot/src/path/to/package-r1.ebuild':
            '/some/path/to/chroot/src/path/to/package.ebuild'
    }

    # Simulate behavior of 'CreatePathDictionaryFromPackages()' when
    # successfully created a dictionary where the key is the absolute path to
    # the symlink of the package and value is the absolute path to the ebuild of
    # the package.
    mock_create_path_dict.return_value = test_package_path_dict

    # Use test function to simulate behavior.
    mock_create_repo.side_effect = SuccessfullyCreateRepoForChanges
    mock_update_llvm_next.side_effect = SuccessfullyUpdatedLLVMNextHash
    mock_uprev_ebuild.side_effect = FailedToUprevEbuild
    mock_upload_changes.side_effect = ShouldNotExecuteUploadChanges

    # Verify exception is raised when an exception is thrown within
    # the 'try' block by UprevEbuild function.
    with self.assertRaises(ValueError) as err:
      update_chromeos_llvm_next_hash.UpdatePackages(
          ['test-packages/package1'], 'a123testhash4', 1000,
          '/some/path/to/chroot', 'PATCHES.json', FailureModes.FAIL, 'google3')

    self.assertEqual(err.exception.message, 'Failed to uprev the ebuild.')

    mock_create_path_dict.assert_called_once_with('/some/path/to/chroot',
                                                  ['test-packages/package1'])

    mock_create_repo.assert_called_once_with('/some/path/to/chroot/src/path/to',
                                             'a123testhash4')

    mock_update_llvm_next.assert_called_once_with(
        '/some/path/to/chroot/src/path/to/package.ebuild', 'a123testhash4',
        1000)

    mock_uprev_ebuild.assert_called_once_with(
        '/some/path/to/chroot/src/path/to/package-r1.ebuild')

    mock_upload_changes.assert_not_called()

    mock_delete_repo.assert_called_once_with('/some/path/to/chroot/src/path/to',
                                             'a123testhash4')

  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'CreatePathDictionaryFromPackages')
  @mock.patch.object(update_chromeos_llvm_next_hash, '_CreateRepo')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UpdateBuildLLVMNextHash')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UprevEbuild')
  @mock.patch.object(update_chromeos_llvm_next_hash, 'UploadChanges')
  @mock.patch.object(update_chromeos_llvm_next_hash, '_DeleteRepo')
  @mock.patch.object(llvm_patch_management, 'UpdatePackagesPatchMetadataFile')
  @mock.patch.object(update_chromeos_llvm_next_hash,
                     'StagePatchMetadataFileForCommit')
  def testSuccessfullyUpdatedPackages(
      self, mock_stage_patch_file, mock_update_package_metadata_file,
      mock_delete_repo, mock_upload_changes, mock_uprev_ebuild,
      mock_update_llvm_next, mock_create_repo, mock_create_path_dict):

    # Test function to simulate '_CreateRepo' when successfully created the repo
    # for the changes to be made to the ebuild files.
    def SuccessfullyCreateRepoForChanges(_repo_path, llvm_hash):
      self.assertEqual(llvm_hash, 'a123testhash5')
      return

    # Test function to simulate 'UploadChanges' after a successfull update of
    # 'LLVM_NEXT_HASH" of the ebuild file.
    def SuccessfullyUpdatedLLVMNextHash(ebuild_path, llvm_hash, llvm_version):
      self.assertEqual(ebuild_path,
                       '/some/path/to/chroot/src/path/to/package.ebuild')
      self.assertEqual(llvm_hash, 'a123testhash5')
      self.assertEqual(llvm_version, 1000)
      return

    # Test function to simulate 'UprevEbuild' when successfully incremented
    # the revision number by 1.
    def SuccessfullyUprevedEbuild(symlink_path):
      self.assertEqual(symlink_path,
                       '/some/path/to/chroot/src/path/to/package-r1.ebuild')

      return

    # Test function to simulate 'UpdatePackagesPatchMetadataFile()' when the
    # patch results contains a disabled patch in 'disable_patches' mode.
    def RetrievedPatchResults(chroot_path, llvm_version, patch_metadata_file,
                              packages, mode):

      self.assertEqual(chroot_path, '/some/path/to/chroot')
      self.assertEqual(llvm_version, 1000)
      self.assertEqual(patch_metadata_file, 'PATCHES.json')
      self.assertListEqual(packages, ['path/to'])
      self.assertEqual(mode, FailureModes.DISABLE_PATCHES)

      PatchInfo = namedtuple('PatchInfo', [
          'applied_patches', 'failed_patches', 'non_applicable_patches',
          'disabled_patches', 'removed_patches', 'modified_metadata'
      ])

      package_patch_info = PatchInfo(
          applied_patches=['fix_display.patch'],
          failed_patches=['fix_stdout.patch'],
          non_applicable_patches=[],
          disabled_patches=['fix_stdout.patch'],
          removed_patches=[],
          modified_metadata='/abs/path/to/filesdir/%s' % patch_metadata_file)

      package_info_dict = {'path/to': package_patch_info._asdict()}

      # Returns a dictionary where the key is the package and the value is a
      # dictionary that contains information about the package's patch results
      # produced by the patch manager.
      return package_info_dict

    # Test function to simulate 'UploadChanges()' when successfully created a
    # commit for the changes made to the packages and their patches and
    # retrieved the change list of the commit.
    def SuccessfullyUploadedChanges(_repo_path, _llvm_hash, _commit_messages):
      commit_url = 'https://some_name/path/to/commit/+/12345'

      return update_chromeos_llvm_next_hash.CommitContents(
          url=commit_url, cl_number=12345)

    test_package_path_dict = {
        '/some/path/to/chroot/src/path/to/package-r1.ebuild':
            '/some/path/to/chroot/src/path/to/package.ebuild'
    }

    # Simulate behavior of 'CreatePathDictionaryFromPackages()' when
    # successfully created a dictionary where the key is the absolute path to
    # the symlink of the package and value is the absolute path to the ebuild of
    # the package.
    mock_create_path_dict.return_value = test_package_path_dict

    # Use test function to simulate behavior.
    mock_create_repo.side_effect = SuccessfullyCreateRepoForChanges
    mock_update_llvm_next.side_effect = SuccessfullyUpdatedLLVMNextHash
    mock_uprev_ebuild.side_effect = SuccessfullyUprevedEbuild
    mock_update_package_metadata_file.side_effect = RetrievedPatchResults
    mock_upload_changes.side_effect = SuccessfullyUploadedChanges

    change_list = update_chromeos_llvm_next_hash.UpdatePackages(
        ['test-packages/package1'], 'a123testhash5', 1000,
        '/some/path/to/chroot', 'PATCHES.json', FailureModes.DISABLE_PATCHES,
        'tot')

    self.assertEqual(change_list.url,
                     'https://some_name/path/to/commit/+/12345')

    self.assertEqual(change_list.cl_number, 12345)

    mock_create_path_dict.assert_called_once_with('/some/path/to/chroot',
                                                  ['test-packages/package1'])

    mock_create_repo.assert_called_once_with('/some/path/to/chroot/src/path/to',
                                             'a123testhash5')

    mock_update_llvm_next.assert_called_once_with(
        '/some/path/to/chroot/src/path/to/package.ebuild', 'a123testhash5',
        1000)

    mock_uprev_ebuild.assert_called_once_with(
        '/some/path/to/chroot/src/path/to/package-r1.ebuild')

    expected_commit_messages = ' '.join([
        '-m %s' % quote('llvm-next/tot: Update packages to r1000'),
        '-m %s' % quote('Following packages have been updated:'),
        '-m %s' % quote('path/to'),
        '-m %s' % quote('For the package path/to:'),
        '-m %s' % quote('The patch metadata file PATCHES.json was modified'),
        '-m %s' % quote('The following patches were disabled:'),
        '-m %s' % quote('fix_stdout.patch')
    ])

    mock_update_package_metadata_file.assert_called_once()

    mock_stage_patch_file.assert_called_once_with(
        '/abs/path/to/filesdir/PATCHES.json')

    mock_upload_changes.assert_called_once_with(
        '/some/path/to/chroot/src/path/to', 'a123testhash5',
        expected_commit_messages)

    mock_delete_repo.assert_called_once_with('/some/path/to/chroot/src/path/to',
                                             'a123testhash5')


if __name__ == '__main__':
  unittest.main()
