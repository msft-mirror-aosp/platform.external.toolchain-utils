#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs CQ dry run after updating the packages."""

from __future__ import print_function

import argparse
import datetime
import json
import os

from assert_not_in_chroot import VerifyOutsideChroot
from failure_modes import FailureModes
from get_llvm_hash import GetLLVMHashAndVersionFromSVNOption
from get_llvm_hash import is_svn_option
from subprocess_helpers import ChrootRunCommand
from subprocess_helpers import ExecCommandAndCaptureOutput
import update_chromeos_llvm_hash


def GetCommandLineArgs():
  """Parses the command line for the command line arguments.

  Returns:
    The log level to use when retrieving the LLVM hash or google3 LLVM version,
    the chroot path to use for executing chroot commands,
    a list of a package or packages to update their LLVM next hash,
    and the LLVM version to use when retrieving the LLVM hash.
  """

  # Default path to the chroot if a path is not specified.
  cros_root = os.path.expanduser('~')
  cros_root = os.path.join(cros_root, 'chromiumos')

  # Create parser and add optional command-line arguments.
  parser = argparse.ArgumentParser(
      description=
      'Runs a tryjob if successfully updated LLVM_NEXT_HASH of packages.')

  # Add argument for the absolute path to the file that contains information on
  # the previous tested svn version.
  parser.add_argument(
      '--last_tested',
      help='the absolute path to the file that contains the last tested '
      'svn version')

  # Add argument for other change lists that want to run alongside the tryjob
  # which has a change list of updating a package's git hash.
  parser.add_argument(
      '--extra_change_lists',
      type=int,
      default=[],
      nargs='+',
      help='change lists that would like to be run alongside the change list '
      'of updating the packages')

  # Add argument for a specific chroot path.
  parser.add_argument(
      '--chroot_path',
      default=cros_root,
      help='the path to the chroot (default: %(default)s)')

  # Add argument to choose between llvm and llvm-next.
  parser.add_argument(
      '--is_llvm_next',
      action='store_true',
      help='which llvm hash to update. Update LLVM_NEXT_HASH if specified. '
      'Otherwise, update LLVM_HASH')

  # Add argument to add reviewers for the created CL.
  parser.add_argument(
      '--reviewers',
      nargs='+',
      default=[],
      help='The reviewers for the package update changelist')

  # Add argument for whether to display command contents to `stdout`.
  parser.add_argument(
      '--verbose',
      action='store_true',
      help='display contents of a command to the terminal '
      '(default: %(default)s)')

  # Add argument for the LLVM version to use.
  parser.add_argument(
      '--llvm_version',
      type=is_svn_option,
      required=True,
      help='which git hash of LLVM to find '
      '{google3, ToT, <svn_version>} '
      '(default: finds the git hash of the google3 LLVM '
      'version)')

  args_output = parser.parse_args()

  return args_output


def GetLastTestedSVNVersion(last_tested_file):
  """Gets the lasted tested svn version from the file.

  Args:
    last_tested_file: The absolute path to the file that contains the last
    tested svn version.

  Returns:
    The last tested svn version or 'None' if the file did not have a last tested
    svn version (the file exists, but failed to convert the contents to an
    integer) or the file does not exist.
  """

  if not last_tested_file:
    return None

  last_svn_version = None

  # Get the last tested svn version if the file exists.
  try:
    with open(last_tested_file) as file_obj:
      # For now, the first line contains the last tested svn version.
      return int(file_obj.read().rstrip())

  except (IOError, ValueError):
    pass

  return last_svn_version


def GetCQDependString(dependent_cls):
  """Get CQ dependency string e.g. `Cq-Depend: chromium:MM, chromium:NN`."""

  if not dependent_cls:
    return None

  # Cq-Depend must start a new paragraph prefixed with "Cq-Depend".
  return '\nCq-Depend: ' + ', '.join(('chromium:%s' % i) for i in dependent_cls)


def AddReviewers(cl, reviewers, chroot_path):
  """Add reviewers for the created CL."""

  gerrit_abs_path = os.path.join(chroot_path, 'chromite/bin/gerrit')
  for reviewer in reviewers:
    cmd = [gerrit_abs_path, 'reviewers', str(cl), reviewer]

    ExecCommandAndCaptureOutput(cmd)


def StartCQDryRun(cl, dependent_cls, chroot_path):
  """Start CQ dry run for the changelist and dependencies."""

  gerrit_abs_path = os.path.join(chroot_path, 'chromite/bin/gerrit')

  cl_list = [cl]
  cl_list.extend(dependent_cls)

  for changes in cl_list:
    cq_dry_run_cmd = [gerrit_abs_path, 'label-cq', str(changes), '1']

    ExecCommandAndCaptureOutput(cq_dry_run_cmd)


def main():
  """Updates the packages' 'LLVM_NEXT_HASH' and submits tryjobs.

  Raises:
    AssertionError: The script was run inside the chroot.
  """

  VerifyOutsideChroot()

  args_output = GetCommandLineArgs()

  last_svn_version = GetLastTestedSVNVersion(args_output.last_tested)

  update_packages = [
      'sys-devel/llvm', 'sys-libs/compiler-rt', 'sys-libs/libcxx',
      'sys-libs/libcxxabi', 'sys-libs/llvm-libunwind'
  ]

  patch_metadata_file = 'PATCHES.json'

  svn_option = args_output.llvm_version

  git_hash, svn_version = GetLLVMHashAndVersionFromSVNOption(svn_option)

  # There is no need to run tryjobs when the SVN version matches the last tested
  # SVN version.
  if last_svn_version == svn_version:
    print('svn version (%d) matches the last tested svn version (%d) in %s' %
          (svn_version, last_svn_version, args_output.last_tested))
    return

  llvm_variant = update_chromeos_llvm_hash.LLVMVariant.current
  if args_output.is_llvm_next:
    llvm_variant = update_chromeos_llvm_hash.LLVMVariant.next
  update_chromeos_llvm_hash.verbose = args_output.verbose
  extra_commit_msg = GetCQDependString(args_output.extra_change_lists)

  change_list = update_chromeos_llvm_hash.UpdatePackages(
      update_packages, llvm_variant, git_hash, svn_version,
      args_output.chroot_path, patch_metadata_file,
      FailureModes.DISABLE_PATCHES, svn_option, extra_commit_msg)

  print('Successfully updated packages to %d' % svn_version)
  print('Gerrit URL: %s' % change_list.url)
  print('Change list number: %d' % change_list.cl_number)

  AddReviewers(change_list.cl_number, args_output.reviewers,
               args_output.chroot_path)
  StartCQDryRun(change_list.cl_number, args_output.extra_change_lists,
                args_output.chroot_path)

  # Updated the packages and submitted tryjobs successfully, so the file will
  # contain 'svn_version' which will now become the last tested svn version.
  if args_output.last_tested:
    with open(args_output.last_tested, 'w', encoding='utf-8') as file_obj:
      file_obj.write(str(svn_version))


if __name__ == '__main__':
  main()
