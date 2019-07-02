#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the latest llvm version's hash."""

from __future__ import print_function

from pipes import quote
import argparse
import os
import re
import shutil
import tempfile

from cros_utils import command_executer
from get_google3_llvm_version import LLVMVersion


class LLVMHash(object):
  """Provides two methods to retrieve a llvm hash."""

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
    """Clones the llvm repo."""

    clone_cmd = 'git clone %s %s' % (quote(self._llvm_url), quote(temp_dir))

    ret, _, err = self._ce.RunCommandWOutput(clone_cmd, print_to_console=False)

    if ret:  # failed to create repo
      raise ValueError('Failed to clone the llvm repo: %s' % err)

  def _ParseCommitMessages(self, subdir, hash_vals, llvm_version):
    """Parses the hashes that match the llvm version.

    Args:
      subdir: The directory where the git history resides.
      hash_vals: All the hashes that match the llvm version.
      llvm_version: The version to compare to in the commit message.

    Returns:
      The hash that matches the llvm version.

    Raises:
      Exception: Failed to parse a commit message.
    """

    # create regex
    llvm_svn_pattern = re.compile(r'llvm-svn: ([0-9]+)')

    # For each hash, grab the last "llvm-svn:" line
    # and compare the llvm version of that line against
    # the llvm version we are looking for and return
    # that hash only if they match.
    for cur_commit in hash_vals.splitlines():
      cur_hash = cur_commit.split()[0]  # get hash

      # cmd to output the commit body
      find_llvm_cmd = 'git -C %s log --format=%%B -n 1 %s' % \
          (quote(subdir), cur_hash)

      ret, out, err = self._ce.RunCommandWOutput(
          find_llvm_cmd, print_to_console=False)

      if ret:  # failed to parse the commit message
        raise ValueError('Failed to parse commit message: %s' % err)

      # find all "llvm-svn:" instances
      llvm_versions = llvm_svn_pattern.findall(out)

      # check the last llvm version against the llvm version we are looking for
      if llvm_versions and int(llvm_versions[-1]) == llvm_version:
        return cur_hash

    # failed to find the commit hash
    raise ValueError('Could not find commit hash.')

  def GetGitHashForVersion(self, llvm_git_dir, llvm_version):
    """Finds the commit hash(es) of the llvm version in the git log history.

    Args:
      llvm_git_dir: The LLVM git directory.
      llvm_version: The version to search for in the git log history.

    Returns:
      A string of the hash corresponding to the llvm version.

    Raises:
      Exception: The hash was not found in the git log history.
    """

    # base directory to search the git log history
    subdir = os.path.join(llvm_git_dir, 'llvm')

    hash_cmd = """git -C %s log --oneline --no-abbrev --grep \"llvm-svn: %d\"
               """ % (quote(subdir), llvm_version)

    ret, hash_vals, err = self._ce.RunCommandWOutput(
        hash_cmd, print_to_console=False)

    if ret:  # failed to find hash
      raise ValueError('Hash not found: %s' % err)

    return self._ParseCommitMessages(subdir, hash_vals, llvm_version)

  def GetLLVMHash(self, llvm_version):
    """Retrieves the llvm hash corresponding to the llvm version passed in.

    Args:
      llvm_version: The llvm version to use as a delimiter.

    Returns:
      The hash as a string that corresponds to the llvm version.
    """

    try:
      # create a temporary directory for the LLVM repo
      llvm_git_dir = self._CreateTempDirectory()

      # clone the "llvm-project" repo
      self._CloneLLVMRepo(llvm_git_dir)

      # find the hash
      hash_value = self.GetGitHashForVersion(llvm_git_dir, llvm_version)
    finally:
      # delete temporary directory
      self._DeleteTempDirectory(llvm_git_dir)

    return hash_value

  def GetGoogle3LLVMHash(self):
    """Retrieves the google3 llvm hash."""

    google3_llvm = LLVMVersion(self._ce.GetLogLevel())
    google3_llvm_version = google3_llvm.GetGoogle3LLVMVersion()

    return self.GetLLVMHash(google3_llvm_version)


def main():
  """Prints the google3 llvm version.

  Parses the command line for the optional command line
  arguments.
  """

  # create parser and add optional command-line arguments
  parser = argparse.ArgumentParser(description='Finds the llvm hash.')
  parser.add_argument(
      '--log_level',
      default='none',
      choices=['none', 'quiet', 'average', 'verbose'],
      help='the level for the logs (default: %(default)s)')
  parser.add_argument('--llvm_version', type=int,
                      help='the llvm version to use as the delimiter ' \
                      '(default: uses the google3 llvm version)')

  # parse command-line arguments
  args_output = parser.parse_args()

  cur_log_level = args_output.log_level  # get log level
  cur_llvm_version = args_output.llvm_version  # get llvm version

  new_llvm_hash = LLVMHash(log_level=cur_log_level)

  if cur_llvm_version:  # passed in a specific llvm version
    print(new_llvm_hash.GetLLVMHash(cur_llvm_version))
  else:  # find the google3 llvm hash
    print(new_llvm_hash.GetGoogle3LLVMHash())


if __name__ == '__main__':
  main()
