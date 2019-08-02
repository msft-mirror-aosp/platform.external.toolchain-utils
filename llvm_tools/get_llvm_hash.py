#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the latest LLVM version's hash."""

from __future__ import print_function

from pipes import quote
import argparse
import os
import re
import shutil
import tempfile

from cros_utils import command_executer
from get_google3_llvm_version import LLVMVersion


def is_svn_option(svn_option):
  """Validates whether the argument (string) is a git hash option.

  The argument is used to find the git hash of LLVM.

  Args:
    svn_option: The option passed in as a command line argument.

  Raises:
    ValueError: Invalid svn option provided.
  """

  if svn_option.lower() in ('google3', 'tot'):
    return svn_option.lower()

  try:
    svn_version = int(svn_option)

    return svn_version

  # Unable to convert argument to an int, so the option is invalid.
  #
  # Ex: 'one'.
  except ValueError:
    pass

  raise ValueError('Invalid LLVM git hash option provided: %s' % svn_option)


class LLVMHash(object):
  """Provides three methods to retrieve a LLVM hash."""

  def __init__(self, log_level='none'):
    self._ce = command_executer.GetCommandExecuter(log_level=log_level)
    self._llvm_url = 'https://chromium.googlesource.com/external' \
        '/github.com/llvm/llvm-project'

  @staticmethod
  def _CreateTempDirectory():
    """Creates a temporary directory in /tmp."""
    return tempfile.mkdtemp()

  @staticmethod
  def _DeleteTempDirectory(temp_dir):
    """Deletes the directory created by CreateTempDirectory()."""
    shutil.rmtree(temp_dir)

  def _CloneLLVMRepo(self, temp_dir):
    """Clones the LLVM repo."""

    clone_cmd = 'git clone %s %s' % (quote(self._llvm_url), quote(temp_dir))

    ret, _, err = self._ce.RunCommandWOutput(clone_cmd, print_to_console=False)

    if ret:  # Failed to create repo.
      raise ValueError('Failed to clone the llvm repo: %s' % err)

  def GetSVNVersionFromCommitMessage(self, commit_message):
    """Gets the 'llvm-svn' from the commit message.

    A commit message may contain multiple 'llvm-svn' (reverting commits), so
    the last 'llvm-svn' is the real 'llvm-svn' for that commit message.

    Args:
      commit_message: A commit message that contains a 'llvm-svn:'.

    Returns:
      The last LLVM version as an integer or 'None' if there is no 'llvm-svn'.
    """

    # Find all "llvm-svn:" instances.
    llvm_versions = re.findall(r'llvm-svn: ([0-9]+)', commit_message)

    if llvm_versions:
      return int(llvm_versions[-1])

    return None

  def _ParseCommitMessages(self, subdir, hash_vals, llvm_version):
    """Parses the hashes that match the LLVM version.

    Args:
      subdir: The directory where the git history resides.
      hash_vals: All the hashes that match the LLVM version.
      llvm_version: The version to compare to in the commit message.

    Returns:
      The hash that matches the LLVM version.

    Raises:
      ValueError: Failed to parse a commit message or did not find a commit
      hash.
    """

    # For each hash, grab the last "llvm-svn:" line
    # and compare the llvm version of that line against
    # the llvm version we are looking for and return
    # that hash only if they match.
    for cur_commit in hash_vals.splitlines():
      cur_hash = cur_commit.split()[0]  # Get hash.

      # Cmd to output the commit body.
      find_llvm_cmd = 'git -C %s log --format=%%B -n 1 %s' % \
          (quote(subdir), cur_hash)

      ret, out, err = self._ce.RunCommandWOutput(
          find_llvm_cmd, print_to_console=False)

      if ret:  # Failed to parse the commit message.
        raise ValueError('Failed to parse commit message: %s' % err)

      commit_svn_version = self.GetSVNVersionFromCommitMessage(out)

      # Check the svn version from the commit message against the llvm version
      # we are looking for.
      if commit_svn_version and commit_svn_version == llvm_version:
        return cur_hash

    # Failed to find the commit hash.
    raise ValueError('Could not find commit hash.')

  def GetGitHashForVersion(self, llvm_git_dir, llvm_version):
    """Finds the commit hash(es) of the LLVM version in the git log history.

    Args:
      llvm_git_dir: The LLVM git directory.
      llvm_version: The version to search for in the git log history.

    Returns:
      A string of the hash corresponding to the LLVM version.

    Raises:
      Exception: The hash was not found in the git log history.
    """

    # Base directory to search the git log history.
    subdir = os.path.join(llvm_git_dir, 'llvm')

    hash_cmd = """git -C %s log --oneline --no-abbrev --grep \"llvm-svn: %d\"
               """ % (quote(subdir), llvm_version)

    ret, hash_vals, err = self._ce.RunCommandWOutput(
        hash_cmd, print_to_console=False)

    if ret:  # Failed to find hash.
      raise ValueError('Hash not found: %s' % err)

    return self._ParseCommitMessages(subdir, hash_vals, llvm_version)

  def GetLLVMHash(self, llvm_version):
    """Retrieves the LLVM hash corresponding to the LLVM version passed in.

    Args:
      llvm_version: The LLVM version to use as a delimiter.

    Returns:
      The hash as a string that corresponds to the LLVM version.
    """

    try:
      # Create a temporary directory for the LLVM repo.
      llvm_git_dir = self._CreateTempDirectory()

      # Clone the "llvm-project" repo.
      self._CloneLLVMRepo(llvm_git_dir)

      # Find the git hash.
      hash_value = self.GetGitHashForVersion(llvm_git_dir, llvm_version)
    finally:
      # Delete temporary directory.
      self._DeleteTempDirectory(llvm_git_dir)

    return hash_value

  def GetGoogle3LLVMHash(self):
    """Retrieves the google3 LLVM hash."""

    google3_llvm = LLVMVersion(self._ce.GetLogLevel())
    google3_llvm_version = google3_llvm.GetGoogle3LLVMVersion()

    return self.GetLLVMHash(google3_llvm_version)

  def GetTopOfTrunkGitHash(self):
    """Gets the latest git hash from top of trunk of LLVM."""

    llvm_url = 'https://github.com/llvm/llvm-project'

    path_to_master_branch = 'refs/heads/master'

    llvm_tot_git_hash_cmd = 'git ls-remote %s %s' % (
        quote(llvm_url), quote(path_to_master_branch))

    # Get the latest git hash of the master branch of LLVM.
    ret, llvm_tot_git_hash, err = self._ce.RunCommandWOutput(
        llvm_tot_git_hash_cmd, print_to_console=False)

    if ret:  # Failed to get the latest git hash of the master branch of LLVM.
      raise ValueError('Failed to get the latest git hash from the top of '
                       'trunk of LLVM: %s' % err)

    return llvm_tot_git_hash.rstrip().split()[0]


def main():
  """Prints the git hash of LLVM.

  Parses the command line for the optional command line
  arguments.
  """

  # Create parser and add optional command-line arguments.
  parser = argparse.ArgumentParser(description='Finds the LLVM hash.')
  parser.add_argument(
      '--log_level',
      default='none',
      choices=['none', 'quiet', 'average', 'verbose'],
      help='the level for the logs (default: %(default)s)')
  parser.add_argument(
      '--llvm_version',
      type=is_svn_option,
      required=True,
      help='which git hash of LLVM to find '
      '{google3, ToT, <svn_version>}')

  # Parse command-line arguments.
  args_output = parser.parse_args()

  cur_log_level = args_output.log_level
  cur_llvm_version = args_output.llvm_version

  new_llvm_hash = LLVMHash(log_level=cur_log_level)

  if isinstance(cur_llvm_version, int):
    # Find the git hash of the specific LLVM version.
    print(new_llvm_hash.GetLLVMHash(cur_llvm_version))
  elif cur_llvm_version == 'google3':
    print(new_llvm_hash.GetGoogle3LLVMHash())
  else:  # Find the top of trunk git hash of LLVM.
    print(new_llvm_hash.GetTopOfTrunkGitHash())


if __name__ == '__main__':
  main()
