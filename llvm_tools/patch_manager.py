#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A manager for patches."""

from __future__ import print_function

import argparse
import json
import os
import subprocess

from collections import namedtuple
from failure_modes import FailureModes


def is_directory(dir_path):
  """Validates that the argument passed into 'argparse' is a directory."""

  if not os.path.isdir(dir_path):
    raise ValueError('Path is not a directory: %s' % dir_path)

  return dir_path


def is_patch_metadata_file(patch_metadata_file):
  """Valides the argument into 'argparse' is a patch file."""

  if not os.path.isfile(patch_metadata_file):
    raise ValueError(
        'Invalid patch metadata file provided: %s' % patch_metadata_file)

  if not patch_metadata_file.endswith('.json'):
    raise ValueError('Patch metadata file does not end in \'.json\': %s' %
                     patch_metadata_file)

  return patch_metadata_file


def GetCommandLineArgs():
  """Get the required arguments from the command line."""

  # Create parser and add optional command-line arguments.
  parser = argparse.ArgumentParser(description='A manager for patches.')

  # Add argument for the LLVM version to use for patch management.
  parser.add_argument(
      '--svn_version',
      type=int,
      required=True,
      help='the LLVM svn version to use for patch management')

  # Add argument for the patch metadata file that is in $FILESDIR.
  parser.add_argument(
      '--patch_metadata_file',
      required=True,
      type=is_patch_metadata_file,
      help='the absolute path to the .json file in \'$FILESDIR/\' of the '
      'package which has all the patches and their metadata if applicable')

  # Add argument for the absolute path to the ebuild's $FILESDIR path.
  # Example: '.../sys-devel/llvm/files/'.
  parser.add_argument(
      '--filesdir_path',
      required=True,
      type=is_directory,
      help='the absolute path to the ebuild \'files/\' directory')

  # Add argument for the absolute path to the unpacked sources.
  parser.add_argument(
      '--src_path',
      required=True,
      type=is_directory,
      help='the absolute path to the unpacked LLVM sources')

  # Add argument for the mode of the patch manager when handling failing
  # applicable patches.
  parser.add_argument(
      '--failure_mode',
      default=FailureModes.FAIL.value,
      choices=[mode.value for mode in FailureModes],
      help='the mode of the patch manager when handling failed patches ' \
          '(default: %(default)s)')

  # Parse the command line.
  args_output = parser.parse_args()

  return args_output


def GetPathToPatch(filesdir_path, rel_patch_path):
  """Gets the absolute path to a patch in $FILESDIR.

  Args:
    filesdir_path: The absolute path to $FILESDIR.
    rel_patch_path: The relative path to the patch in '$FILESDIR/'.

  Returns:
    The absolute path to the patch in $FILESDIR.

  Raises:
    ValueError: Unable to find the path to the patch in $FILESDIR.
  """

  if not os.path.isdir(filesdir_path):
    raise ValueError('Invalid path to $FILESDIR provided: %s' % filesdir_path)

  # Combine $FILESDIR + relative path of patch to $FILESDIR.
  patch_path = os.path.join(filesdir_path, rel_patch_path)

  if not os.path.isfile(patch_path):
    raise ValueError('The absolute path %s to the patch %s does not exist' %
                     (patch_path, rel_patch_path))

  return patch_path


def GetPatchMetadata(patch_dict):
  """Gets the patch's metadata.

  Args:
    patch_dict: A dictionary that has the patch metadata.

  Returns:
    A tuple that contains the metadata values.
  """

  # Get the metadata values of a patch if possible.
  start_version = patch_dict.get('start_version', 0)
  end_version = patch_dict.get('end_version', None)
  is_critical = patch_dict.get('is_critical', False)

  return start_version, end_version, is_critical


def ApplyPatch(src_path, patch_path):
  """Attempts to apply the patch.

  Args:
    src_path: The absolute path to the unpacked sources of the package.
    patch_path: The absolute path to the patch in $FILESDIR/

  Returns:
    A boolean where 'True' means that the patch applied fine or 'False' means
    that the patch failed to apply.
  """

  if not os.path.isdir(src_path):
    raise ValueError('Invalid src path provided: %s' % src_path)

  if not os.path.isfile(patch_path):
    raise ValueError('Invalid patch file provided: %s' % patch_path)

  # Test the patch with '--dry-run' before actually applying the patch.
  test_patch_cmd = [
      'patch', '--dry-run', '-d', src_path, '-f', '-p1', '-E',
      '--no-backup-if-mismatch', '-i', patch_path
  ]

  # Cmd to apply a patch in the src unpack path.
  apply_patch_cmd = [
      'patch', '-d', src_path, '-f', '-p1', '-E', '--no-backup-if-mismatch',
      '-i', patch_path
  ]

  try:
    subprocess.check_output(test_patch_cmd)

  # If the mode is 'continue', then catching the exception makes sure that
  # the program does not exit on the first failed applicable patch.
  except subprocess.CalledProcessError:
    # Test run on the patch failed to apply.
    return False

  # Test run succeeded on the patch.
  subprocess.check_output(apply_patch_cmd)

  return True


def UpdatePatchMetadataFile(patch_metadata_file, patches):
  """Updates the .json file with unchanged and at least one changed patch.

  Args:
    patch_metadata_file: The absolute path to the .json file that has all the
    patches and its metadata.
    patches: A list of patches whose metadata were or were not updated.

  Raises:
    ValueError: The patch metadata file does not have the correct extension.
  """

  if not patch_metadata_file.endswith('.json'):
    raise ValueError('File does not end in \'.json\': %s' % patch_metadata_file)

  with open(patch_metadata_file, 'w') as patch_file:
    json.dump(patches, patch_file, indent=4, separators=(',', ': '))


def _ConvertToASCII(obj):
  """Convert an object loaded from JSON to ASCII; JSON gives us unicode."""

  # Using something like `object_hook` is insufficient, since it only fires on
  # actual JSON objects. `encoding` fails, too, since the default decoder always
  # uses unicode() to decode strings.
  if isinstance(obj, unicode):
    return str(obj)
  if isinstance(obj, dict):
    return {_ConvertToASCII(k): _ConvertToASCII(v) for k, v in obj.iteritems()}
  if isinstance(obj, list):
    return [_ConvertToASCII(v) for v in obj]
  return obj


def HandlePatches(svn_version, patch_metadata_file, filesdir_path, src_path,
                  mode):
  """Handles the patches in the .json file for the package.

  Args:
    svn_version: The LLVM version to use for patch management.
    patch_metadata_file: The absolute path to the .json file in '$FILESDIR/'
    that has all the patches and their metadata.
    filesdir_path: The absolute path to $FILESDIR.
    src_path: The absolute path to the unpacked destination of the package.
    mode: The action to take when an applicable patch failed to apply.
      Ex: 'FailureModes.FAIL'

  Returns:
    Depending on the mode, 'None' would be returned if everything went well or
    the .json file was not updated. Otherwise, a list or multiple lists would
    be returned that indicates what has changed.

  Raises:
    ValueError: The patch metadata file does not exist or does not end with
    '.json' or the absolute path to $FILESDIR does not exist or the unpacked
    path does not exist or if the mode is 'fail', then an applicable patch
    failed to apply.
  """

  # A flag for whether the mode specified would possible modify the patches.
  can_modify_patches = False

  # 'fail' or 'continue' mode would not modify a patch's metadata, so the .json
  # file would stay the same.
  if mode != FailureModes.FAIL and mode != FailureModes.CONTINUE:
    can_modify_patches = True

  # A flag that determines whether at least one patch's metadata was
  # updated due to the mode that is passed in.
  updated_patch = False

  # A list of patches that will be in the updated .json file.
  applicable_patches = []

  # A list of patches that successfully applied.
  applied_patches = []

  # A list of patches that were disabled.
  disabled_patches = []

  # A list of non applicable patches.
  non_applicable_patches = []

  # A list of patches that will not be included in the updated .json file
  removed_patches = []

  # Whether the patch metadata file was modified where 'None' means that the
  # patch metadata file was not modified otherwise the absolute path to the
  # patch metadata file is stored.
  modified_metadata = None

  # A list of patches that failed to apply.
  failed_patches = []

  with open(patch_metadata_file) as patch_file:
    patch_file_contents = _ConvertToASCII(json.load(patch_file))

    # Patch format:
    # {
    #   "rel_patch_path" : "[REL_PATCH_PATH_FROM_$FILESDIR]"
    #   [PATCH_METADATA] if available.
    # }
    #
    # For each patch, find the path to it in $FILESDIR and get its metadata if
    # available, then check if the patch is applicable.
    for cur_patch_dict in patch_file_contents:
      # Get the absolute path to the patch in $FILESDIR.
      path_to_patch = GetPathToPatch(filesdir_path,
                                     cur_patch_dict['rel_patch_path'])

      # Get the patch's metadata.
      #
      # Index information of 'patch_metadata':
      #   [0]: start_version
      #   [1]: end_version
      #   [2]: is_critical
      patch_metadata = GetPatchMetadata(cur_patch_dict)

      if not patch_metadata[1]:
        # Patch does not have an 'end_version' value which implies 'end_version'
        # == 'inf' ('svn_version' will always be less than 'end_version'), so
        # the patch is applicable if 'svn_version' >= 'start_version'.
        patch_applicable = svn_version >= patch_metadata[0]
      else:
        # Patch is applicable if 'svn_version' >= 'start_version' &&
        # "svn_version" < "end_version".
        patch_applicable = (svn_version >= patch_metadata[0] and \
                            svn_version < patch_metadata[1])

      if can_modify_patches:
        # Add to the list only if the mode can potentially modify a patch
        # or if the mode is 'remove_patches', then all patches that are
        # applicable will be added to the updated .json file and all patches
        # that are not applicable will be added to the remove patches list which
        # will not be included in the updated .json file.
        if patch_applicable or mode != FailureModes.REMOVE_PATCHES:
          applicable_patches.append(cur_patch_dict)
        elif mode == FailureModes.REMOVE_PATCHES:
          removed_patches.append(path_to_patch)

          if not modified_metadata:
            # At least one patch will be removed from the .json file.
            modified_metadata = patch_metadata_file

      if not patch_applicable:
        non_applicable_patches.append(os.path.basename(path_to_patch))

      # There is no need to apply patches in 'remove_patches' mode.
      if patch_applicable and mode != FailureModes.REMOVE_PATCHES:
        patch_applied = ApplyPatch(src_path, path_to_patch)

        if not patch_applied:  # Failed to apply patch.
          failed_patches.append(os.path.basename(path_to_patch))

          # Check the mode to determine what action to take on the failing
          # patch.
          if mode == FailureModes.DISABLE_PATCHES:
            # Set the patch's 'end_version' to 'svn_version' so the patch
            # would not be applicable anymore (i.e. the patch's 'end_version'
            # would not be greater than 'svn_version').

            # Last element in 'applicable_patches' is the current patch.
            applicable_patches[-1]['end_version'] = svn_version

            disabled_patches.append(os.path.basename(path_to_patch))

            if not updated_patch:
              # At least one patch has been modified, so the .json file
              # will be updated with the new patch metadata.
              updated_patch = True

              modified_metadata = patch_metadata_file
          elif mode == FailureModes.BISECT_PATCHES:
            # TODO (saludlemus): Complete this mode.
            # Figure out where the patch's stops applying and set the patch's
            # 'end_version' to that version.
            pass
          elif mode == FailureModes.FAIL:
            if applied_patches:
              print('The following patches applied successfully up to the '
                    'failed patch:')
              print('\n'.join(applied_patches))

            # Throw an exception on the first patch that failed to apply.
            raise ValueError(
                'Failed to apply patch: %s' % os.path.basename(path_to_patch))
        else:  # Successfully applied patch
          applied_patches.append(os.path.basename(path_to_patch))

  # Create a namedtuple of the patch results.
  PatchInfo = namedtuple('PatchInfo', [
      'applied_patches', 'failed_patches', 'non_applicable_patches',
      'disabled_patches', 'removed_patches', 'modified_metadata'
  ])

  patch_info = PatchInfo(
      applied_patches=applied_patches,
      failed_patches=failed_patches,
      non_applicable_patches=non_applicable_patches,
      disabled_patches=disabled_patches,
      removed_patches=removed_patches,
      modified_metadata=modified_metadata)

  # Determine post actions after iterating through the patches.
  if mode == FailureModes.REMOVE_PATCHES:
    if removed_patches:
      UpdatePatchMetadataFile(patch_metadata_file, applicable_patches)
  elif mode == FailureModes.DISABLE_PATCHES or \
      mode == FailureModes.BISECT_PATCHES:
    if updated_patch:
      UpdatePatchMetadataFile(patch_metadata_file, applicable_patches)

  return patch_info


def PrintPatchResults(patch_info):
  """Prints the results of handling the patches of a package.

  Args:
    patch_info: A namedtuple that has information on the patches.
  """

  if patch_info.applied_patches:
    print('The following patches applied successfully:')
    print('\n'.join(patch_info.applied_patches))

  if patch_info.failed_patches:
    print('The following patches failed to apply:')
    print('\n'.join(patch_info.failed_patches))

  if patch_info.non_applicable_patches:
    print('The following patches were not applicable:')
    print('\n'.join(patch_info.non_applicable_patches))

  if patch_info.modified_metadata:
    print('The patch metadata file %s has been modified' % os.path.basename(
        patch_info.modified_metadata))

  if patch_info.disabled_patches:
    print('The following patches were disabled:')
    print('\n'.join(patch_info.disabled_patches))

  if patch_info.removed_patches:
    print('The following patches were removed from the patch metadata file:')
    for cur_patch_path in patch_info.removed_patches:
      print('%s' % os.path.basename(cur_patch_path))


def main():
  """Get the arguments for the patch manager."""

  args_output = GetCommandLineArgs()

  # Get the results of handling the patches of the package.
  patch_info = HandlePatches(args_output.svn_version,
                             args_output.patch_metadata_file,
                             args_output.filesdir_path, args_output.src_path,
                             FailureModes(args_output.failure_mode))

  PrintPatchResults(patch_info)


if __name__ == '__main__':
  main()
