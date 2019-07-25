#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests when handling patches."""

from __future__ import print_function

import json
import mock
import os
import patch_manager
import subprocess
import unittest

from failure_modes import FailureModes
from test_helpers import CallCountsToMockFunctions
from test_helpers import CreateTemporaryJsonFile
from test_helpers import WritePrettyJsonFile


class PatchManagerTest(unittest.TestCase):
  """Test class when handling patches of packages."""

  # Simulate behavior of 'os.path.isdir()' when the path is not a directory.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testInvalidDirectoryPassedAsCommandLineArgument(self, mock_isdir):
    # Verify the exception is raised when the command line argument for
    # '--filesdir_path' or '--src_path' is not a directory.
    with self.assertRaises(ValueError) as err:
      patch_manager.is_directory('/some/path/that/is/not/a/directory')

    self.assertEqual(
        err.exception.message, 'Path is not a directory: '
        '/some/path/that/is/not/a/directory')

    mock_isdir.assert_called_once()

  # Simulate the behavior of 'os.path.isdir()' when a path to a directory is
  # passed as the command line argument for '--filesdir_path' or '--src_path'.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  def testValidDirectoryPassedAsCommandLineArgument(self, mock_isdir):
    self.assertEqual(
        patch_manager.is_directory('/some/path/that/is/a/directory'),
        '/some/path/that/is/a/directory')

    mock_isdir.assert_called_once()

  # Simulate behavior of 'os.path.isfile()' when the patch metadata file is does
  # not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testInvalidPathToPatchMetadataFilePassedAsCommandLineArgument(
      self, mock_isfile):

    # Verify the exception is raised when the command line argument for
    # '--patch_metadata_file' does not exist or is not a file.
    with self.assertRaises(ValueError) as err:
      patch_manager.is_patch_metadata_file('/abs/path/to/PATCHES.json')

    self.assertEqual(
        err.exception.message, 'Invalid patch metadata file provided: '
        '/abs/path/to/PATCHES.json')

    mock_isfile.assert_called_once()

  # Simulate the behavior of 'os.path.isfile()' when the path to the patch
  # metadata file exists and is a file.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testPatchMetadataFileDoesNotEndInJson(self, mock_isfile):
    # Verify the exception is raises when the command line argument for
    # '--patch_metadata_file' exists and is a file but does not end in
    # '.json'.
    with self.assertRaises(ValueError) as err:
      patch_manager.is_patch_metadata_file('/abs/path/to/PATCHES')

    self.assertEqual(
        err.exception.message, 'Patch metadata file does not end in \'.json\': '
        '/abs/path/to/PATCHES')

    mock_isfile.assert_called_once()

  # Simulate the behavior of 'os.path.isfile()' when the command line argument
  # for '--patch_metadata_file' exists and is a file.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testValidPatchMetadataFilePassedAsCommandLineArgument(self, mock_isfile):
    self.assertEqual(
        patch_manager.is_patch_metadata_file('/abs/path/to/PATCHES.json'),
        '/abs/path/to/PATCHES.json')

    mock_isfile.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the path to $FILESDIR
  # does not exist.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testInvalidPathToFilesDirWhenConstructingPathToPatch(self, mock_isdir):
    # Verify the exception is raised when the the absolute path to $FILESDIR of
    # a package is not a directory.
    with self.assertRaises(ValueError) as err:
      patch_manager.GetPathToPatch('/abs/path/to/filesdir',
                                   'cherry/fixes_stdout.patch')

    self.assertEqual(
        err.exception.message, 'Invalid path to $FILESDIR provided: '
        '/abs/path/to/filesdir')

    mock_isdir.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the absolute path to the
  # $FILESDIR of a package exists and is a directory.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate the behavior of 'os.path.isfile()' when the absolute path to the
  # patch does not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testConstructedPathToPatchDoesNotExist(self, mock_isfile, mock_isdir):
    # Verify the exception is raised when the absolute path to the patch does
    # not exist.
    with self.assertRaises(ValueError) as err:
      patch_manager.GetPathToPatch('/abs/path/to/filesdir',
                                   'cherry/fixes_stdout.patch')

    self.assertEqual(
        err.exception.message, 'The absolute path /abs/path/to/filesdir/cherry/'
        'fixes_stdout.patch to the patch '
        'cherry/fixes_stdout.patch does not exist')

    mock_isdir.assert_called_once()

    mock_isfile.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the absolute path to the
  # $FILESDIR of a package exists and is a directory.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  # Simulate behavior of 'os.path.isfile()' when the absolute path to the
  # patch exists and is a file.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testConstructedPathToPatchSuccessfully(self, mock_isfile, mock_isdir):
    self.assertEqual(
        patch_manager.GetPathToPatch('/abs/path/to/filesdir',
                                     'cherry/fixes_stdout.patch'),
        '/abs/path/to/filesdir/cherry/fixes_stdout.patch')

    mock_isdir.assert_called_once()

    mock_isfile.assert_called_once()

  def testSuccessfullyGetPatchMetadataForPatchWithNoMetadata(self):
    expected_patch_metadata = 0, None, False

    test_patch = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_stdout.patch"
    }

    self.assertEqual(
        patch_manager.GetPatchMetadata(test_patch), expected_patch_metadata)

  def testSuccessfullyGetPatchMetdataForPatchWithSomeMetadata(self):
    expected_patch_metadata = 0, 1000, False

    test_patch = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_stdout.patch",
        "end_version": 1000
    }

    self.assertEqual(
        patch_manager.GetPatchMetadata(test_patch), expected_patch_metadata)

  def testFailedToApplyPatchWhenInvalidSrcPathIsPassedIn(self):
    # Verify the exception is raised when the absolute path to the unpacked
    # sources of a package is not a directory.
    with self.assertRaises(ValueError) as err:
      patch_manager.ApplyPatch(
          '/abs/path/to/src', '/abs/path/to/filesdir/cherry/fixes_stdout.patch')

    self.assertEqual(err.exception.message,
                     'Invalid src path provided: /abs/path/to/src')

  # Simulate behavior of 'os.path.isdir()' when the absolute path to the
  # unpacked sources of the package is valid and exists.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  def testFailedToApplyPatchWhenPatchPathIsInvalid(self, mock_isdir):
    # Verify the exception is raised when the absolute path to the patch does
    # not exist or is not a file.
    with self.assertRaises(ValueError) as err:
      patch_manager.ApplyPatch(
          '/abs/path/to/src', '/abs/path/to/filesdir/cherry/fixes_stdout.patch')

    self.assertEqual(
        err.exception.message, 'Invalid patch file provided: '
        '/abs/path/to/filesdir/cherry/fixes_stdout.patch')

    mock_isdir.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the absolute path to the
  # unpacked sources of the package is valid and exists.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(os.path, 'isfile', return_value=True)
  # Simulate behavior of 'os.path.isfile()' when the absolute path to the
  # patch exists and is a file.
  @mock.patch.object(subprocess, 'check_output')
  def testFailedToApplyPatchInDryRun(self, mock_dry_run, mock_isfile,
                                     mock_isdir):

    # Simulate behavior of 'subprocess.check_output()' when '--dry-run'
    # fails on the applying patch.
    def FailedToApplyPatch(test_patch_cmd):
      # First argument is the return error code, the second argument is the
      # command that was run, and the third argument is the output.
      raise subprocess.CalledProcessError(1, test_patch_cmd, None)

    mock_dry_run.side_effect = FailedToApplyPatch

    self.assertEqual(
        patch_manager.ApplyPatch(
            '/abs/path/to/src', '/abs/path/to/filesdir/cherry/'
            'fixes_stdout.patch'), False)

    mock_isdir.assert_called_once()

    mock_isfile.assert_called_once()

    mock_dry_run.assert_called_once()

  # Simulate behavior of 'os.path.isdir()' when the absolute path to the
  # unpacked sources of the package is valid and exists.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(os.path, 'isfile', return_value=True)
  # Simulate behavior of 'os.path.isfile()' when the absolute path to the
  # patch exists and is a file.
  @mock.patch.object(subprocess, 'check_output')
  def testSuccessfullyAppliedPatch(self, mock_dry_run, mock_isfile, mock_isdir):

    self.assertEqual(
        patch_manager.ApplyPatch(
            '/abs/path/to/src', '/abs/path/to/filesdir/cherry/'
            'fixes_stdout.patch'), True)

    mock_isdir.assert_called_once()

    mock_isfile.assert_called_once()

    self.assertEqual(mock_dry_run.call_count, 2)

  def testFailedToUpdatePatchMetadataFileWhenPatchFileNotEndInJson(self):
    patch = [{
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 10
    }]

    # Verify the exception is raised when the absolute path to the patch
    # metadata file does not end in '.json'.
    with self.assertRaises(ValueError) as err:
      patch_manager.UpdatePatchMetadataFile('/abs/path/to/filesdir/PATCHES',
                                            patch)

    self.assertEqual(
        err.exception.message, 'File does not end in \'.json\': '
        '/abs/path/to/filesdir/PATCHES')

  def testSuccessfullyUpdatedPatchMetadataFile(self):
    test_updated_patch_metadata = [{
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 10
    }]

    expected_patch_metadata = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 10
    }

    with CreateTemporaryJsonFile() as json_test_file:
      patch_manager.UpdatePatchMetadataFile(json_test_file,
                                            test_updated_patch_metadata)

      # Make sure the updated patch metadata was written into the temporary
      # .json file.
      with open(json_test_file) as patch_file:
        patch_contents = patch_manager._ConvertToASCII(json.load(patch_file))

        self.assertEqual(len(patch_contents), 1)

        self.assertDictEqual(patch_contents[0], expected_patch_metadata)

  @mock.patch.object(patch_manager, 'GetPathToPatch')
  def testExceptionThrownWhenHandlingPatches(self, mock_get_path_to_patch):
    # Simulate behavior of 'GetPathToPatch()' when the absolute path to the
    # patch does not exist.
    def PathToPatchDoesNotExist(filesdir_path, rel_patch_path):
      raise ValueError('The absolute path to /abs/path/to/filesdir/cherry/'
                       'fix_output.patch does not exist')

    # Use the test function to simulate the behavior of 'GetPathToPatch()'.
    mock_get_path_to_patch.side_effect = PathToPatchDoesNotExist

    test_patch_metadata = [{
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 10
    }]

    with CreateTemporaryJsonFile() as json_test_file:
      # Write the test patch metadata to the temporary .json file.
      with open(json_test_file, 'w') as json_file:
        WritePrettyJsonFile(test_patch_metadata, json_file)

      # Verify the exception is raised when the absolute path to a patch does
      # not exist.
      with self.assertRaises(ValueError) as err:
        patch_manager.HandlePatches(1000, json_test_file,
                                    '/abs/path/to/filesdir',
                                    '/some/path/to/src', FailureModes.FAIL)

    self.assertEqual(
        err.exception.message,
        'The absolute path to /abs/path/to/filesdir/cherry/'
        'fix_output.patch does not exist')

    mock_get_path_to_patch.assert_called_once_with('/abs/path/to/filesdir',
                                                   'cherry/fixes_output.patch')

  @mock.patch.object(patch_manager, 'GetPathToPatch')
  # Simulate behavior for 'ApplyPatch()' when an applicable patch failed to
  # apply.
  @mock.patch.object(patch_manager, 'ApplyPatch', return_value=False)
  def testExceptionThrownOnAFailedPatchInFailMode(self, mock_apply_patch,
                                                  mock_get_path_to_patch):
    # Simulate behavior for 'GetPathToPatch()' when successfully constructed the
    # absolute path to the patch and the patch exists.
    mock_get_path_to_patch.return_value = ('/abs/path/to/filesdir/cherry/'
                                           'fixes_output.patch')

    test_patch_metadata = [{
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 1000
    }]

    with CreateTemporaryJsonFile() as json_test_file:
      # Write the test patch metadata to the temporary .json file.
      with open(json_test_file, 'w') as json_file:
        WritePrettyJsonFile(test_patch_metadata, json_file)

      # Verify the exception is raised when the mode is 'fail' and an applicable
      # patch fails to apply.
      with self.assertRaises(ValueError) as err:
        patch_manager.HandlePatches(1000, json_test_file,
                                    '/abs/path/to/filesdir',
                                    '/some/path/to/src', FailureModes.FAIL)

    self.assertEqual(err.exception.message,
                     'Failed to apply patch: fixes_output.patch')

    mock_get_path_to_patch.assert_called_once_with('/abs/path/to/filesdir',
                                                   'cherry/fixes_output.patch')

    mock_apply_patch.assert_called_once_with(
        '/some/path/to/src', '/abs/path/to/filesdir/cherry/'
        'fixes_output.patch')

  @mock.patch.object(patch_manager, 'GetPathToPatch')
  @mock.patch.object(patch_manager, 'ApplyPatch')
  def testSomePatchesFailedToApplyInContinueMode(self, mock_apply_patch,
                                                 mock_get_path_to_patch):
    # Simulate behavior for 'GetPathToPatch()' when successfully constructed the
    # absolute path to the patch and the patch exists.
    @CallCountsToMockFunctions
    def MultipleCallsToGetPatchPath(call_count, filesdir_path, rel_patch_path):
      # First patch to call 'GetPathToPatch()'.
      if call_count == 0:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_output.patch')

        return '/abs/path/to/filesdir/cherry/fixes_output.patch'

      # Second patch to call 'GetPathToPatch()'.
      if call_count == 1:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_input.patch')

        return '/abs/path/to/filesdir/cherry/fixes_input.patch'

      # Third patch to call 'GetPathToPatch()'.
      if call_count == 2:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_warning.patch')

        return '/abs/path/to/filesdir/add_warning.patch'

      # Fourth (and last) patch to call 'GetPathToPatch()'.
      if call_count == 3:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_helper.patch')

        return '/abs/path/to/filesdir/add_helper.patch'

      # 'GetPathToPatch()' was called more times than expected (4 times).
      assert False, 'Unexpectedly called more than 4 times.'

    # Simulate behavior for 'ApplyPatch()' when applying multiple applicable
    # patches.
    @CallCountsToMockFunctions
    def MultipleCallsToApplyPatches(call_count, src_path, path_to_patch):
      # First applicable patch that tries to apply patch.
      if call_count == 0:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/cherry/fixes_output.patch')

        return True

      # Second applicable patch that tries to apply patch.
      if call_count == 1:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/cherry/fixes_input.patch')

        return False

      # Third applicable patch that tries to apply patch.
      if call_count == 2:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/add_warning.patch')

        return False

      # 'ApplyPatch()' was called more times than expected (3 times).
      assert False, 'Unexpectedly called more than 3 times.'

    # Use test functions to simulate behavior.
    mock_get_path_to_patch.side_effect = MultipleCallsToGetPatchPath
    mock_apply_patch.side_effect = MultipleCallsToApplyPatches

    test_patch_1 = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 1000,
        "end_version": 1250
    }

    test_patch_2 = {
        "comment": "Fixes input",
        "rel_patch_path": "cherry/fixes_input.patch",
        "start_version": 1000
    }

    test_patch_3 = {
        "comment": "Adds a warning",
        "rel_patch_path": "add_warning.patch",
        "start_version": 750,
        "end_version": 1500
    }

    test_patch_4 = {
        "comment": "Adds a helper function",
        "rel_patch_path": "add_helper.patch",
        "start_version": 20,
        "end_version": 900
    }

    test_patch_metadata = [
        test_patch_1, test_patch_2, test_patch_3, test_patch_4
    ]

    expected_applied_patches = ['fixes_output.patch']
    expected_failed_patches = ['fixes_input.patch', 'add_warning.patch']
    expected_non_applicable_patches = ['add_helper.patch']

    expected_patch_info_dict = {
        'applied_patches': expected_applied_patches,
        'failed_patches': expected_failed_patches,
        'non_applicable_patches': expected_non_applicable_patches,
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    with CreateTemporaryJsonFile() as json_test_file:
      # Write the test patch metadata to the temporary .json file.
      with open(json_test_file, 'w') as json_file:
        WritePrettyJsonFile(test_patch_metadata, json_file)

      patch_info = patch_manager.HandlePatches(
          1000, json_test_file, '/abs/path/to/filesdir', '/some/path/to/src',
          FailureModes.CONTINUE)

    self.assertDictEqual(patch_info._asdict(), expected_patch_info_dict)

    self.assertEqual(mock_get_path_to_patch.call_count, 4)

    self.assertEqual(mock_apply_patch.call_count, 3)

  @mock.patch.object(patch_manager, 'GetPathToPatch')
  @mock.patch.object(patch_manager, 'ApplyPatch')
  def testSomePatchesAreDisabled(self, mock_apply_patch,
                                 mock_get_path_to_patch):
    # Simulate behavior for 'GetPathToPatch()' when successfully constructed the
    # absolute path to the patch and the patch exists.
    @CallCountsToMockFunctions
    def MultipleCallsToGetPatchPath(call_count, filesdir_path, rel_patch_path):
      # First patch to call 'GetPathToPatch()'.
      if call_count == 0:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_output.patch')

        return '/abs/path/to/filesdir/cherry/fixes_output.patch'

      # Second patch to call 'GetPathToPatch()'.
      if call_count == 1:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_input.patch')

        return '/abs/path/to/filesdir/cherry/fixes_input.patch'

      # Third patch to call 'GetPathToPatch()'.
      if call_count == 2:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_warning.patch')

        return '/abs/path/to/filesdir/add_warning.patch'

      # Fourth (and last) patch to call 'GetPathToPatch()'.
      if call_count == 3:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_helper.patch')

        return '/abs/path/to/filesdir/add_helper.patch'

      # 'GetPathToPatch()' was called more times than expected (4 times).
      assert False, 'Unexpectedly called more than 4 times.'

    # Simulate behavior for 'ApplyPatch()' when applying multiple applicable
    # patches.
    @CallCountsToMockFunctions
    def MultipleCallsToApplyPatches(call_count, src_path, path_to_patch):
      # First applicable patch that tries to apply patch.
      if call_count == 0:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/cherry/fixes_input.patch')

        return False

      # Second applicable patch that tries to apply patch.
      if call_count == 1:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/add_warning.patch')

        return True

      # Third applicable patch that tries to apply patch.
      if call_count == 2:
        self.assertEqual(path_to_patch,
                         '/abs/path/to/filesdir/add_helper.patch')

        return False

      # 'ApplyPatch()' was called more times than expected (3 times).
      assert False, 'Unexpectedly called more than 3 times.'

    # Use test functions to simulate behavior.
    mock_get_path_to_patch.side_effect = MultipleCallsToGetPatchPath
    mock_apply_patch.side_effect = MultipleCallsToApplyPatches

    test_patch_1 = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 1000,
        "end_version": 1190
    }

    test_patch_2 = {
        "comment": "Fixes input",
        "rel_patch_path": "cherry/fixes_input.patch",
        "start_version": 1000
    }

    test_patch_3 = {
        "comment": "Adds a warning",
        "rel_patch_path": "add_warning.patch",
        "start_version": 750,
        "end_version": 1500
    }

    test_patch_4 = {
        "comment": "Adds a helper function",
        "rel_patch_path": "add_helper.patch",
        "start_version": 20,
        "end_version": 2000
    }

    test_patch_metadata = [
        test_patch_1, test_patch_2, test_patch_3, test_patch_4
    ]

    expected_applied_patches = ['add_warning.patch']
    expected_failed_patches = ['fixes_input.patch', 'add_helper.patch']
    expected_disabled_patches = ['fixes_input.patch', 'add_helper.patch']
    expected_non_applicable_patches = ['fixes_output.patch']

    # Assigned 'None' for now, but it is expected that the patch metadata file
    # will be modified, so the 'expected_patch_info_dict's' value for the
    # key 'modified_metadata' will get updated to the temporary .json file once
    # the file is created.
    expected_modified_metadata_file = None

    expected_patch_info_dict = {
        'applied_patches': expected_applied_patches,
        'failed_patches': expected_failed_patches,
        'non_applicable_patches': expected_non_applicable_patches,
        'disabled_patches': expected_disabled_patches,
        'removed_patches': [],
        'modified_metadata': expected_modified_metadata_file
    }

    with CreateTemporaryJsonFile() as json_test_file:
      # Write the test patch metadata to the temporary .json file.
      with open(json_test_file, 'w') as json_file:
        WritePrettyJsonFile(test_patch_metadata, json_file)

      expected_patch_info_dict['modified_metadata'] = json_test_file

      patch_info = patch_manager.HandlePatches(
          1200, json_test_file, '/abs/path/to/filesdir', '/some/path/to/src',
          FailureModes.DISABLE_PATCHES)

      self.assertDictEqual(patch_info._asdict(), expected_patch_info_dict)

      # 'test_patch_1' and 'test_patch_3' were not modified/disabled, so their
      # dictionary is the same, but 'test_patch_2' and 'test_patch_4' were
      # disabled, so their 'end_version' would be set to 1200, which was the
      # value passed into 'HandlePatches()' for the 'svn_version'.
      test_patch_2['end_version'] = 1200
      test_patch_4['end_version'] = 1200

      expected_json_file = [
          test_patch_1, test_patch_2, test_patch_3, test_patch_4
      ]

      # Make sure the updated patch metadata was written into the temporary
      # .json file.
      with open(json_test_file) as patch_file:
        new_json_file_contents = patch_manager._ConvertToASCII(
            json.load(patch_file))

        self.assertEqual(len(new_json_file_contents), 4)

        for i in range(4):
          self.assertDictEqual(new_json_file_contents[i], expected_json_file[i])

    self.assertEqual(mock_get_path_to_patch.call_count, 4)

    self.assertEqual(mock_apply_patch.call_count, 3)

  @mock.patch.object(patch_manager, 'GetPathToPatch')
  @mock.patch.object(patch_manager, 'ApplyPatch')
  def testSomePatchesAreRemoved(self, mock_apply_patch, mock_get_path_to_patch):
    # Simulate behavior for 'GetPathToPatch()' when successfully constructed the
    # absolute path to the patch and the patch exists.
    @CallCountsToMockFunctions
    def MultipleCallsToGetPatchPath(call_count, filesdir_path, rel_patch_path):
      # First patch to call 'GetPathToPatch()'.
      if call_count == 0:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_output.patch')

        return '/abs/path/to/filesdir/cherry/fixes_output.patch'

      # Second patch to call 'GetPathToPatch()'.
      if call_count == 1:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'cherry/fixes_input.patch')

        return '/abs/path/to/filesdir/cherry/fixes_input.patch'

      # Third patch to call 'GetPathToPatch()'.
      if call_count == 2:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_warning.patch')

        return '/abs/path/to/filesdir/add_warning.patch'

      # Fourth (and last) patch to call 'GetPathToPatch()'.
      if call_count == 3:
        self.assertEqual(filesdir_path, '/abs/path/to/filesdir')
        self.assertEqual(rel_patch_path, 'add_helper.patch')

        return '/abs/path/to/filesdir/add_helper.patch'

      # 'GetPathToPatch()' was called more times than expected (4 times).
      assert False, 'Unexpectedly called more than 4 times.'

    # Use the test function to simulate behavior of 'GetPathToPatch()'.
    mock_get_path_to_patch.side_effect = MultipleCallsToGetPatchPath

    # For the 'remove_patches' mode, this patch is expected to be in the
    # 'non_applicable_patches' list and 'removed_patches' list because
    # the 'svn_version' (1500) >= 'end_version' (1190).
    test_patch_1 = {
        "comment": "Redirects output to stdout",
        "rel_patch_path": "cherry/fixes_output.patch",
        "start_version": 1000,
        "end_version": 1190
    }

    # For the 'remove_patches' mode, this patch is expected to be in the
    # 'applicable_patches' list (which is the list that the .json file will be
    # updated with) because the 'svn_version' < 'inf' (this patch does not have
    # an 'end_version' value which implies 'end_version' == 'inf').
    test_patch_2 = {
        "comment": "Fixes input",
        "rel_patch_path": "cherry/fixes_input.patch",
        "start_version": 1000
    }

    # For the 'remove_patches' mode, this patch is expected to be in the
    # 'non_applicable_patches' list and 'removed_patches' list because
    # the 'svn_version' (1500) >= 'end_version' (1500).
    test_patch_3 = {
        "comment": "Adds a warning",
        "rel_patch_path": "add_warning.patch",
        "start_version": 750,
        "end_version": 1500
    }

    # For the 'remove_patches' mode, this patch is expected to be in the
    # 'non_applicable_patches' list and 'removed_patches' list because
    # the 'svn_version' (1500) >= 'end_version' (1400).
    test_patch_4 = {
        "comment": "Adds a helper function",
        "rel_patch_path": "add_helper.patch",
        "start_version": 20,
        "end_version": 1400
    }

    test_patch_metadata = [
        test_patch_1, test_patch_2, test_patch_3, test_patch_4
    ]

    expected_applied_patches = []
    expected_failed_patches = []
    expected_disabled_patches = []
    expected_non_applicable_patches = [
        'fixes_output.patch', 'add_warning.patch', 'add_helper.patch'
    ]
    expected_removed_patches = [
        '/abs/path/to/filesdir/cherry/fixes_output.patch',
        '/abs/path/to/filesdir/add_warning.patch',
        '/abs/path/to/filesdir/add_helper.patch'
    ]

    # Assigned 'None' for now, but it is expected that the patch metadata file
    # will be modified, so the 'expected_patch_info_dict's' value for the
    # key 'modified_metadata' will get updated to the temporary .json file once
    # the file is created.
    expected_modified_metadata_file = None

    expected_patch_info_dict = {
        'applied_patches': expected_applied_patches,
        'failed_patches': expected_failed_patches,
        'non_applicable_patches': expected_non_applicable_patches,
        'disabled_patches': expected_disabled_patches,
        'removed_patches': expected_removed_patches,
        'modified_metadata': expected_modified_metadata_file
    }

    with CreateTemporaryJsonFile() as json_test_file:
      # Write the test patch metadata to the temporary .json file.
      with open(json_test_file, 'w') as json_file:
        WritePrettyJsonFile(test_patch_metadata, json_file)

      expected_patch_info_dict['modified_metadata'] = json_test_file

      patch_info = patch_manager.HandlePatches(
          1500, json_test_file, '/abs/path/to/filesdir', '/some/path/to/src',
          FailureModes.REMOVE_PATCHES)

      self.assertDictEqual(patch_info._asdict(), expected_patch_info_dict)

      # 'test_patch_2' was an applicable patch, so this patch will be the only
      # patch that is in temporary .json file. The other patches were not
      # applicable (they failed the applicable check), so they will not be in
      # the .json file.
      expected_json_file = [test_patch_2]

      # Make sure the updated patch metadata was written into the temporary
      # .json file.
      with open(json_test_file) as patch_file:
        new_json_file_contents = patch_manager._ConvertToASCII(
            json.load(patch_file))

        self.assertEqual(len(new_json_file_contents), 1)

        self.assertDictEqual(new_json_file_contents[0], expected_json_file[0])

    self.assertEqual(mock_get_path_to_patch.call_count, 4)

    mock_apply_patch.assert_not_called()


if __name__ == '__main__':
  unittest.main()
