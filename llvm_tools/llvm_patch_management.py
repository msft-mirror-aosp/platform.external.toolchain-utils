#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Creates the arguments for the patch manager for LLVM."""

from __future__ import print_function

from pipes import quote
import argparse
import os
import patch_manager
import re

from assert_not_in_chroot import VerifyOutsideChroot
from cros_utils import command_executer
from failure_modes import FailureModes
from get_google3_llvm_version import LLVMVersion

ce = command_executer.GetCommandExecuter()


def GetCommandLineArgs():
  """Parses the commandline for the optional commandline arguments.

  Returns:
    An argument parser object that contains all the commandline arguments.
  """

  # Default path to the chroot if a path is not specified.
  cros_root = os.path.expanduser('~')
  cros_root = os.path.join(cros_root, 'chromiumos')

  # Create parser and add optional command-line arguments.
  parser = argparse.ArgumentParser(description='Patch management for packages.')

  # Add argument for a specific chroot path.
  parser.add_argument(
      '--chroot_path',
      type=patch_manager.is_directory,
      default=cros_root,
      help='the absolute path to the chroot (default: %(default)s)')

  # Add argument for which packages to manage their patches.
  parser.add_argument(
      '--packages',
      required=False,
      nargs='+',
      default=['sys-devel/llvm'],
      help='the packages to manage their patches (default: %(default)s)')

  # Add argument for the log level.
  parser.add_argument(
      '--log_level',
      default='none',
      choices=['none', 'quiet', 'average', 'verbose'],
      help='the level for the logs (default: %(default)s)')

  # Add argument for the LLVM version to use for patch management.
  parser.add_argument(
      '--llvm_version',
      type=int,
      help='the LLVM version to use for patch management ' \
          '(default: uses the google3 LLVM version)')

  # Add argument for the mode of the patch management when handling patches.
  parser.add_argument(
      '--failure_mode',
      default=FailureModes.FAIL.value,
      choices=[mode.value for mode in FailureModes],
      help='the mode of the patch manager when handling failed patches ' \
          '(default: %(default)s)')

  # Add argument for the patch metadata file in $FILESDIR of LLVM.
  parser.add_argument(
      '--patch_metadata_file',
      default='PATCHES.json',
      help='the .json file in $FILESDIR that has all the patches and their '
      'metadata if applicable (default: %(default)s)')

  # Parse the command line.
  args_output = parser.parse_args()

  # Set the log level for the command executer.
  ce.SetLogLevel(log_level=args_output.log_level)

  unique_packages = list(set(args_output.packages))

  # Duplicate packages were passed into the command line
  if len(unique_packages) != len(args_output.packages):
    raise ValueError('Duplicate packages were passed in: %s' % ' '.join(
        args_output.packages))

  args_output.packages = unique_packages

  return args_output


def GetPathToFilesDirectory(chroot_path, package):
  """Gets the absolute path to $FILESDIR of the package.

  Args:
    chroot_path: The absolute path to the chroot.
    package: The package to find its absolute path to $FILESDIR.

  Returns:
    The  absolute path to $FILESDIR.

  Raises:
    ValueError: An invalid chroot path has been provided.
  """

  if not os.path.isdir(chroot_path):
    raise ValueError('Invalid chroot provided: %s' % chroot_path)

  # Get the absolute chroot path to the ebuild.
  ret, chroot_ebuild_path, err = ce.ChrootRunCommandWOutput(
      chromeos_root=chroot_path,
      command='equery w %s' % package,
      print_to_console=False)

  if ret:  # Failed to get the absolute chroot path to package's ebuild.
    raise ValueError(
        'Failed to get the absolute chroot path of the package %s: %s' %
        (package, err))

  # Get the absolute chroot path to $FILESDIR's parent directory.
  filesdir_parent_path = os.path.dirname(chroot_ebuild_path.strip())

  # Get the relative path to $FILESDIR's parent directory.
  rel_path = _GetRelativePathOfChrootPath(filesdir_parent_path)

  # Construct the absolute path to the package's 'files' directory.
  return os.path.join(chroot_path, rel_path, 'files/')


def _GetRelativePathOfChrootPath(chroot_path):
  """Gets the relative path of the chroot path passed in.

  Args:
    chroot_path: The chroot path to get its relative path.

  Returns:
    The relative path after '/mnt/host/source/'.

  Raises:
    ValueError: The prefix of 'chroot_path' did not match '/mnt/host/source/'.
  """

  chroot_prefix = '/mnt/host/source/'

  if not chroot_path.startswith(chroot_prefix):
    raise ValueError('Invalid prefix for the chroot path: %s' % chroot_path)

  return chroot_path[len(chroot_prefix):]


def _CheckPatchMetadataPath(patch_metadata_path):
  """Checks that the patch metadata path is valid.

  Args:
    patch_metadata_path: The absolute path to the .json file that has the
    patches and their metadata.

  Raises:
    ValueError: The file does not exist or the file does not end in '.json'.
  """

  if not os.path.isfile(patch_metadata_path):
    raise ValueError('Invalid file provided: %s' % patch_metadata_path)

  if not patch_metadata_path.endswith('.json'):
    raise ValueError('File does not end in \'.json\': %s' % patch_metadata_path)


def UnpackLLVMPackage(chroot_path, package):
  """Unpacks the package.

  Args:
    chroot_path: The absolute path to the chroot.
    package: The package to unpack its sources.

  Returns:
    The absolute path to the unpacked sources of the package.

  Raises:
    ValueError: Invalid chroot path or failed to unpack the package or
    failed to construct the absolute path to the unpacked sources.
  """

  # Get the absolute chroot ebuild path of the package.
  ret, ebuild_path, err = ce.ChrootRunCommandWOutput(
      chromeos_root=chroot_path,
      command='equery w %s' % package,
      print_to_console=False)

  if ret:  # Failed to get the absolute chroot path to the ebuild.
    raise ValueError('Failed to get the absolute chroot path to the ebuild of '
                     '%s: %s' % (package, err))

  ebuild_path = ebuild_path.rstrip()

  # Cmd to unpack the package.
  unpack_cmd = 'sudo ebuild %s clean unpack' % quote(ebuild_path)

  ret, _, err = ce.ChrootRunCommandWOutput(
      chromeos_root=chroot_path,
      command=unpack_cmd,
      print_to_console=False,
      env=dict(os.environ, USE='llvm-next'))

  if ret:  # Failed to unpack the package.
    raise ValueError('Failed to unpack the package %s: %s' % (package, err))

  split_ebuild_path = ebuild_path.split('/')

  return _ConstructPathToSources(chroot_path, split_ebuild_path[-1],
                                 split_ebuild_path[-3])


def _ConstructPathToSources(chroot_path, ebuild_name, parent_dir_name):
  """Constructs the absolute path to the unpacked sources of the package.

  Args:
    chroot_path: The absolute path to the chroot.
    ebuild_name: The ebuild name of the package that has the revision number.
    parent_dir_name: The parent directory name of the package (Ex:
    'sys-libs'/llvm).

  Returns:
    The absolute path to the unpacked path of the sources of the package.

  Raises:
    ValueError: The ebuild name does not have '.ebuild' or does not have a
    revision number.
  """

  # Remove '.ebuild' from the name.
  package_with_revision, remove_ebuild = re.subn(
      r'\.ebuild$', '', ebuild_name, count=1)

  if not remove_ebuild:  # Failed to remove '.ebuild'.
    raise ValueError('Failed to remove \'.ebuild\' from %s.' % ebuild_name)

  # Remove the revision number from the new name.
  package_name, remove_revision_num = re.subn(
      r'\-r[0-9]+$', '', package_with_revision, count=1)

  if not remove_revision_num:  # Failed to remove the revision number.
    raise ValueError(
        'Failed to remove the revision number from %s.' % package_with_revision)

  src_path = os.path.join(chroot_path, 'chroot/var/tmp/portage/',
                          parent_dir_name, package_with_revision, 'work/',
                          package_name)

  if not os.path.isdir(src_path):
    raise ValueError('Failed to construct the absolute path to the unpacked '
                     'sources of the package %s: %s' % (package_name, src_path))

  return src_path


def UpdatePackagesPatchMetadataFile(chroot_path, svn_version,
                                    patch_metadata_file, packages, mode):
  """Updates the packages metadata file.

  Args:
    chroot_path: The absolute path to the chroot.
    svn_version: The version to use for patch management.
    patch_metadata_file: The patch metadta file where all the patches and
    their metadata are.
    packages: All the packages to update their patch metadata file.
    mode: The mode for the patch manager to use when an applicable patch
    fails to apply.
      Ex: 'FailureModes.FAIL'

  Returns:
    A dictionary where the key is the package name and the value is a dictionary
    that has information on the patches.
  """

  # A dictionary where the key is the package name and the value is a dictionary
  # that has information on the patches.
  package_info = {}

  for cur_package in packages:
    # Get the absolute path to $FILESDIR of the package.
    filesdir_path = GetPathToFilesDirectory(chroot_path, cur_package)

    # Construct the absolute path to the patch metadata file where all the
    # patches and their metadata are.
    patch_metadata_path = os.path.join(filesdir_path, patch_metadata_file)

    # Make sure the patch metadata path is valid.
    _CheckPatchMetadataPath(patch_metadata_path)

    # Unpack the package and construct the absolute path to the unpacked
    # sources of the package.
    src_path = UnpackLLVMPackage(chroot_path, cur_package)

    # Get the patch results for the current package.
    patches_info = patch_manager.HandlePatches(svn_version, patch_metadata_path,
                                               filesdir_path, src_path, mode)

    package_info[cur_package] = patches_info._asdict()

  return package_info


def main():
  """Updates the patch metadata file of each package if possible.

  Raises:
    AssertionError: The script was run inside the chroot.
  """

  VerifyOutsideChroot()

  args_output = GetCommandLineArgs()

  # Get the google3 LLVM version if a LLVM version was not provided.
  if not args_output.llvm_version:
    args_output.llvm_version = LLVMVersion(
        log_level=args_output.log_level).GetGoogle3LLVMVersion()

  UpdatePackagesPatchMetadataFile(
      args_output.chroot_path, args_output.llvm_version,
      args_output.patch_metadata_file, args_output.packages,
      FailureModes(args_output.failure_mode))


if __name__ == '__main__':
  main()
