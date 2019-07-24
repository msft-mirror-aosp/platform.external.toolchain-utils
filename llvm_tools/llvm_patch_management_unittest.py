#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests when creating the arguments for the patch manager."""

from __future__ import print_function

from collections import namedtuple
import mock
import os
import unittest

from cros_utils import command_executer
from failure_modes import FailureModes
from test_helpers import CallCountsToMockFunctions
import llvm_patch_management
import patch_manager


class LlvmPatchManagementTest(unittest.TestCase):
  """Test class when constructing the arguments for the patch manager."""

  def testInvalidChrootPathWhenGetPathToFilesDir(self):
    # Verify the exception is raised when an invalid absolute path to the chroot
    # is passed in.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management.GetPathToFilesDirectory('/some/path/to/chroot',
                                                    'sys-devel/llvm')

    self.assertEqual(err.exception.message,
                     'Invalid chroot provided: /some/path/to/chroot')

  # Simulate the behavior of 'os.path.isdir()' when a valid chroot path is
  # passed in.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def testFailedToGetChrootPathToEbuildWhenGetPathToFilesDir(
      self, mock_chroot_cmd, mock_isdir):

    # Simulate behavior of 'ChrootRunCommandWOutput()' when failed to get the
    # absolute chroot path to the package's ebuild.
    #
    # Returns shell error code, stdout, stderr.
    mock_chroot_cmd.return_value = (1, None, 'Invalid package provided.')

    # Verify the exception is raised when failed to get the absolute chroot
    # path to a package's ebuild.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management.GetPathToFilesDirectory('/some/path/to/chroot',
                                                    'test/package')

    self.assertEqual(
        err.exception.message,
        'Failed to get the absolute chroot path of the package '
        'test/package: Invalid package provided.')

    mock_chroot_cmd.assert_called_once_with(
        chromeos_root='/some/path/to/chroot',
        command='equery w test/package',
        print_to_console=False)

    mock_isdir.assert_called_once()

  # Simulate the behavior of 'os.path.isdir()' when a valid chroot path is
  # passed in.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  @mock.patch.object(llvm_patch_management, '_GetRelativePathOfChrootPath')
  def testSuccessfullyGetPathToFilesDir(
      self, mock_get_relative_path_of_chroot_path, mock_chroot_cmd, mock_isdir):

    # Simulate behavior of 'ChrootRunCommandWOutput()' when successfully
    # retrieved the absolute chroot path to the package's ebuild.
    #
    # Returns shell error code, stdout, stderr.
    mock_chroot_cmd.return_value = (0,
                                    '/mnt/host/source/path/to/llvm/llvm.ebuild',
                                    0)

    # Simulate behavior of '_GetRelativePathOfChrootPath()' when successfully
    # removed '/mnt/host/source' of the absolute chroot path to the package's
    # ebuild.
    #
    # Returns relative path after '/mnt/host/source/'.
    mock_get_relative_path_of_chroot_path.return_value = 'path/to/llvm'

    self.assertEqual(
        llvm_patch_management.GetPathToFilesDirectory('/some/path/to/chroot',
                                                      'sys-devel/llvm'),
        '/some/path/to/chroot/path/to/llvm/files/')

    mock_isdir.assert_called_once()

    mock_chroot_cmd.assert_called_once()

    mock_get_relative_path_of_chroot_path.assert_called_once_with(
        '/mnt/host/source/path/to/llvm')

  def testInvalidPrefixForChrootPath(self):
    # Verify the exception is raised when the chroot path does not start with
    # '/mnt/host/source/'.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._GetRelativePathOfChrootPath('/path/to/llvm')

    self.assertEqual(err.exception.message,
                     'Invalid prefix for the chroot path: /path/to/llvm')

  def testValidPrefixForChrootPath(self):
    self.assertEqual(
        llvm_patch_management._GetRelativePathOfChrootPath(
            '/mnt/host/source/path/to/llvm'), 'path/to/llvm')

  # Simulate behavior of 'os.path.isfile()' when the patch metadata file does
  # not exist.
  @mock.patch.object(os.path, 'isfile', return_value=False)
  def testInvalidFileForPatchMetadataPath(self, mock_isfile):
    # Verify the exception is raised when the absolute path to the patch
    # metadata file does not exist.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._CheckPatchMetadataPath(
          '/abs/path/to/files/test.json')

    self.assertEqual(err.exception.message,
                     'Invalid file provided: /abs/path/to/files/test.json')

    mock_isfile.assert_called_once()

  # Simulate behavior of 'os.path.isfile()' when the absolute path to the
  # patch metadata file exists.
  @mock.patch.object(os.path, 'isfile', return_value=True)
  def testPatchMetadataFileDoesNotEndInJson(self, mock_isfile):
    # Verify the exception is raised when the patch metadata file does not end
    # in '.json'.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._CheckPatchMetadataPath(
          '/abs/path/to/files/PATCHES')

    self.assertEqual(
        err.exception.message, 'File does not end in \'.json\': '
        '/abs/path/to/files/PATCHES')

    mock_isfile.assert_called_once()

  @mock.patch.object(os.path, 'isfile')
  def testValidPatchMetadataFile(self, mock_isfile):
    # Simulate behavior of 'os.path.isfile()' when the absolute path to the
    # patch metadata file exists.
    mock_isfile.return_value = True

    llvm_patch_management._CheckPatchMetadataPath(
        '/abs/path/to/files/PATCHES.json')

    mock_isfile.assert_called_once()

  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def testFailedToUnpackPackage(self, mock_chroot_cmd):
    # Simulate the behavior of 'ChrootRunCommandWOutput()' when unpacking fails
    # on a package.
    @CallCountsToMockFunctions
    def MultipleCallsToGetSrcPath(call_count, chromeos_root, command,
                                  print_to_console):

      # First call to 'ChrootRunCommandWOutput()' which would successfully
      # get the ebuild path of the package.
      if call_count == 0:
        # Returns shell error code, stdout, stderr.
        return 0, '/mount/host/source/path/to/package/test-r1.ebuild', 0

      # Second call to 'ChrootRunCommandWOutput()' which failed to unpack the
      # package.
      if call_count == 1:
        # Returns shell error code, stdout, stderr.
        return 1, None, 'Invalid package provided.'

      # 'ChrootRunCommandWOutput()' was called more times than expected (2
      # times).
      assert False, ('Unexpectedly called more than 2 times.')

    # Use test function to simulate 'ChrootRunCommandWOutput()' behavior.
    mock_chroot_cmd.side_effect = MultipleCallsToGetSrcPath

    # Verify the exception is raised when failed to unpack a package.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management.UnpackLLVMPackage('/some/path/to/chroot',
                                              'test/package')

    self.assertEqual(
        err.exception.message, 'Failed to unpack the package test/package: '
        'Invalid package provided.')

    self.assertEqual(mock_chroot_cmd.call_count, 2)

  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  def testFailedToGetChrootPathToEbuild(self, mock_chroot_cmd):
    # Simulate the behavior of 'ChrootRunCommandWOutput()' when failed to get
    # the absolute chroot path to the package's ebuild.
    mock_chroot_cmd.return_value = (1, None, 'Invalid package provided.')

    # Verify the exception is raised when failed to get the absolute chroot
    # path to the package's ebuild.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management.UnpackLLVMPackage('/some/path/to/chroot',
                                              'test/package')

    self.assertEqual(
        err.exception.message,
        'Failed to get the absolute chroot path to the ebuild of '
        'test/package: Invalid package provided.')

    mock_chroot_cmd.assert_called_once_with(
        chromeos_root='/some/path/to/chroot',
        command='equery w test/package',
        print_to_console=False)

  @mock.patch.object(command_executer.CommandExecuter,
                     'ChrootRunCommandWOutput')
  @mock.patch.object(llvm_patch_management, '_ConstructPathToSources')
  def testSuccessfullyGetSrcPath(self, mock_construct_src_path,
                                 mock_chroot_cmd):

    # Simulate the behavior of 'ChrootRunCommandWOutput()' when successfully
    # get the absolute chroot ebuild path to the package and successfully
    # unpacked the package.
    @CallCountsToMockFunctions
    def MultipleCallsToGetSrcPath(call_count, chromeos_root, command,
                                  print_to_console):

      # First call to 'ChrootRunCommandWOutput()' which would successfully
      # get the absolute chroot path to the package's ebuild.
      if call_count == 0:
        # Returns shell error code, stdout, stderr.
        return 0, '/mount/host/source/path/to/package/test-r1.ebuild', 0

      # Second call to 'ChrootRunCommandWOutput()' which would successfully
      # unpack the package.
      if call_count == 1:
        # Returns shell error code, stdout, stderr.
        return 0, None, 0

      # 'ChrootRunCommandWOutput()' was called more times than expected (2
      # times).
      assert False, ('Unexpectedly called more than 2 times.')

    # Use the test function to simulate 'ChrootRunCommandWOutput()' behavior.
    mock_chroot_cmd.side_effect = MultipleCallsToGetSrcPath

    # Simulate the behavior of '_ConstructPathToSources()' when the ebuild name
    # has a revision number and '.ebuild' and the absolute path to the src
    # directory is valid.
    mock_construct_src_path.return_value = ('/some/path/to/chroot/chroot/var'
                                            '/tmp/portage/to/test-r1/work/'
                                            'test')

    self.assertEqual(
        llvm_patch_management.UnpackLLVMPackage('/some/path/to/chroot',
                                                'package/test'),
        '/some/path/to/chroot/chroot/var/tmp/portage/to/test-r1/work/test')

    self.assertEqual(mock_chroot_cmd.call_count, 2)

    mock_construct_src_path.assert_called_once_with('/some/path/to/chroot',
                                                    'test-r1.ebuild', 'to')

  def testFailedToRemoveEbuildPartFromTheEbuildName(self):
    # Verify the exception is raised when the ebuild name with the revision
    # number does not have '.ebuild' in the name.
    #
    # Ex: llvm-9.0_pre361749_p20190714-r4
    #
    # Does not have a '.ebuild' in the ebuild name.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._ConstructPathToSources('/some/path/to/chroot',
                                                    'test-r1', 'test-packages')

    self.assertEqual(err.exception.message,
                     'Failed to remove \'.ebuild\' from test-r1.')

  def testFailedToRemoveTheRevisionNumberFromTheEbuildName(self):
    # Verify the exception is raised when the ebuild name with the revision
    # number does not have the revision number in the name.
    #
    # Ex: llvm-9.0_pre361749_p20190714.ebuild
    #
    # Does not have a revision number in the ebuild name.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._ConstructPathToSources(
          '/some/path/to/chroot', 'test.ebuild', 'test-packages')

    self.assertEqual(err.exception.message,
                     'Failed to remove the revision number from test.')

  # Simulate behavior of 'os.path.isdir()' when the constructed absolute path to
  # the unpacked sources does not exist.
  @mock.patch.object(os.path, 'isdir', return_value=False)
  def testInvalidPathToUnpackedSources(self, mock_isdir):
    # Verify the exception is raised when the absolute path to the unpacked
    # sources is constructed, but the path is invalid.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management._ConstructPathToSources(
          '/some/path/to/chroot', 'test-r1.ebuild', 'test-packages')

    self.assertEqual(
        err.exception.message,
        'Failed to construct the absolute path to the unpacked '
        'sources of the package test: '
        '/some/path/to/chroot/chroot/var/tmp/portage/test-packages'
        '/test-r1/work/test')

    mock_isdir.assert_called_once()

  # Simulate the behavior of 'os.path.isdir()' when the absolute path to the
  # src directory exists.
  @mock.patch.object(os.path, 'isdir', return_value=True)
  def testSuccessfullyConstructedSrcPath(self, mock_isdir):
    self.assertEqual(
        llvm_patch_management._ConstructPathToSources(
            '/some/path/to/chroot', 'test-r1.ebuild', 'test-packages'),
        '/some/path/to/chroot/chroot/var/tmp/portage/test-packages/'
        'test-r1/work/test')

    mock_isdir.assert_called_once()

  @mock.patch.object(llvm_patch_management, 'GetPathToFilesDirectory')
  @mock.patch.object(llvm_patch_management, '_CheckPatchMetadataPath')
  def testExceptionIsRaisedWhenUpdatingAPackagesMetadataFile(
      self, mock_check_patch_metadata_path, mock_get_filesdir_path):

    # Simulate the behavior of '_CheckPatchMetadataPath()' when the patch
    # metadata file in $FILESDIR does not exist or does not end in '.json'.
    def InvalidPatchMetadataFile(patch_metadata_path):
      self.assertEqual(patch_metadata_path,
                       '/some/path/to/chroot/some/path/to/filesdir/PATCHES')

      raise ValueError('File does not end in \'.json\': '
                       '/some/path/to/chroot/some/path/to/filesdir/PATCHES')

    # Use the test function to simulate behavior of '_CheckPatchMetadataPath()'.
    mock_check_patch_metadata_path.side_effect = InvalidPatchMetadataFile

    # Simulate the behavior of 'GetPathToFilesDirectory()' when successfully
    # constructed the absolute path to $FILESDIR of a package.
    mock_get_filesdir_path.return_value = ('/some/path/to/chroot/some/path/'
                                           'to/filesdir')

    # Verify the exception is raised when a package is constructing the
    # arguments for the patch manager to update its patch metadata file and an
    # exception is raised in the process.
    with self.assertRaises(ValueError) as err:
      llvm_patch_management.UpdatePackagesPatchMetadataFile(
          '/some/path/to/chroot', 1000, 'PATCHES', ['test-packages/package1'],
          FailureModes.FAIL)

    self.assertEqual(
        err.exception.message, 'File does not end in \'.json\': '
        '/some/path/to/chroot/some/path/to/filesdir/PATCHES')

    mock_get_filesdir_path.assert_called_once_with('/some/path/to/chroot',
                                                   'test-packages/package1')

    mock_check_patch_metadata_path.assert_called_once()

  @mock.patch.object(llvm_patch_management, 'GetPathToFilesDirectory')
  @mock.patch.object(llvm_patch_management, '_CheckPatchMetadataPath')
  @mock.patch.object(llvm_patch_management, 'UnpackLLVMPackage')
  @mock.patch.object(patch_manager, 'HandlePatches')
  def testSuccessfullyRetrievedPatchResults(
      self, mock_handle_patches, mock_unpack_package,
      mock_check_patch_metadata_path, mock_get_filesdir_path):

    # Simulate the behavior of 'GetPathToFilesDirectory()' when successfully
    # constructed the absolute path to $FILESDIR of a package.
    mock_get_filesdir_path.return_value = ('/some/path/to/chroot/some/path/'
                                           'to/filesdir')

    # Simulate the behavior of 'UnpackLLVMPackage()' when successfully unpacked
    # the package and constructed the absolute path to the unpacked sources.
    mock_unpack_package.return_value = ('/some/path/to/chroot/chroot/var/tmp/'
                                        'portage/test-packages/package2-r1/work'
                                        '/package2')

    PatchInfo = namedtuple('PatchInfo', [
        'applied_patches', 'failed_patches', 'non_applicable_patches',
        'disabled_patches', 'removed_patches', 'modified_metadata'
    ])

    # Simulate the behavior of 'HandlePatches()' when successfully iterated
    # through every patch in the patch metadata file and a dictionary is
    # returned that contains information about the patches' status.
    mock_handle_patches.return_value = PatchInfo(
        applied_patches=['fixes_something.patch'],
        failed_patches=['disables_output.patch'],
        non_applicable_patches=[],
        disabled_patches=[],
        removed_patches=[],
        modified_metadata=None)

    expected_patch_results = {
        'applied_patches': ['fixes_something.patch'],
        'failed_patches': ['disables_output.patch'],
        'non_applicable_patches': [],
        'disabled_patches': [],
        'removed_patches': [],
        'modified_metadata': None
    }

    patch_info = llvm_patch_management.UpdatePackagesPatchMetadataFile(
        '/some/path/to/chroot', 1000, 'PATCHES.json',
        ['test-packages/package2'], FailureModes.CONTINUE)

    self.assertDictEqual(patch_info,
                         {'test-packages/package2': expected_patch_results})

    mock_get_filesdir_path.assert_called_once_with('/some/path/to/chroot',
                                                   'test-packages/package2')

    mock_check_patch_metadata_path.assert_called_once_with(
        '/some/path/to/chroot/some/path/to/filesdir/PATCHES.json')

    mock_unpack_package.assert_called_once_with('/some/path/to/chroot',
                                                'test-packages/package2')

    mock_handle_patches.assert_called_once_with(
        1000, '/some/path/to/chroot/some/path/to/filesdir/PATCHES.json',
        '/some/path/to/chroot/some/path/to/filesdir',
        '/some/path/to/chroot/chroot/var/tmp/portage/test-packages/'
        'package2-r1/work/package2', FailureModes.CONTINUE)


if __name__ == '__main__':
  unittest.main()
