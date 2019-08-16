#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Returns the latest LLVM version's hash."""

from __future__ import print_function

from contextlib import contextmanager
import argparse
import os
import re
import requests
import shutil
import subprocess
import tempfile


def GetGoogle3LLVMVersion():
  """Gets the latest google3 LLVM version.

  Returns:
    The latest LLVM SVN version as an integer.

  Raises:
    subprocess.CalledProcessError: An invalid path has been provided to the
    `cat` command.
  """

  path_to_google3_llvm_version = ('/google/src/head/depot/google3/third_party'
                                  '/crosstool/v18/stable/installs/llvm/'
                                  'revision')

  # Cmd to get latest google3 LLVM version.
  cat_cmd = ['cat', path_to_google3_llvm_version]

  # Get latest version.
  g3_version = subprocess.check_output(cat_cmd)

  # Change type to an integer
  return int(g3_version.rstrip())


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


def GetLLVMHashAndVersionFromSVNOption(svn_option):
  """Gets the LLVM hash and LLVM version based off of the svn option.

  Args:
    svn_option: A valid svn option obtained from the command line.
      Ex: 'google3', 'tot', or <svn_version> such as 365123.

  Returns:
    A tuple that is the LLVM git hash and LLVM version.
  """

  new_llvm_hash = LLVMHash()

  # Determine which LLVM git hash to retrieve.
  if svn_option == 'tot':
    llvm_hash = new_llvm_hash.GetTopOfTrunkGitHash()

    tot_commit_message = new_llvm_hash.GetCommitMessageForHash(llvm_hash)

    llvm_version = new_llvm_hash.GetSVNVersionFromCommitMessage(
        tot_commit_message)
  else:
    if isinstance(svn_option, int):
      llvm_version = svn_option
    else:
      llvm_version = GetGoogle3LLVMVersion()

    llvm_hash = new_llvm_hash.GetLLVMHash(llvm_version)

  return llvm_hash, llvm_version


class LLVMHash(object):
  """Provides three methods to retrieve a LLVM hash."""

  def __init__(self):
    self._llvm_url = 'https://chromium.googlesource.com/external' \
        '/github.com/llvm/llvm-project'

  @staticmethod
  @contextmanager
  def CreateTempDirectory():
    temp_dir = tempfile.mkdtemp()

    try:
      yield temp_dir
    finally:
      if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)

  def CloneLLVMRepo(self, temp_dir):
    """Clones the LLVM repo.

    Args:
      temp_dir: The temporary directory to clone the repo to.

    Raises:
      ValueError: Failed to clone the LLVM repo.
    """

    clone_cmd = ['git', 'clone', self._llvm_url, temp_dir]

    clone_cmd_obj = subprocess.Popen(clone_cmd, stderr=subprocess.PIPE)
    _, stderr = clone_cmd_obj.communicate()

    if clone_cmd_obj.returncode:
      raise ValueError('Failed to clone the LLVM repo: %s' % stderr)

  def GetCommitMessageForHash(self, git_hash):
    """Gets the commit message from the git hash.

    Args:
      git_hash: A git hash of LLVM.

    Returns:
      The commit message of the git hash.

    Raises:
      ValueError: Unable to retrieve json contents from the LLVM commit URL.
    """

    llvm_commit_url = ('https://api.github.com/repos/llvm/llvm-project/git/'
                       'commits/')

    commit_url = os.path.join(llvm_commit_url, git_hash)

    url_response = requests.get(commit_url)

    if not url_response:
      raise ValueError('Failed to get response from url %s: Status Code %d' %
                       (commit_url, url_response.status_code))

    unicode_json_contents = url_response.json()

    return str(unicode_json_contents['message'])

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
      subprocess.CalledProcessError: Failed to retrieve the commit message body.
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
      find_llvm_cmd = [
          'git', '-C', subdir, 'log', '--format=%B', '-n', '1', cur_hash
      ]

      out = subprocess.check_output(find_llvm_cmd)

      commit_svn_version = self.GetSVNVersionFromCommitMessage(out.rstrip())

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
      subprocess.CalledProcessError: Failed to retrieve git hashes that match
      'llvm_version'.
    """

    # Get all the git hashes that match 'llvm_version'.
    hash_cmd = [
        'git', '-C', llvm_git_dir, 'log', '--oneline', '--no-abbrev', '--grep',
        'llvm-svn: %d' % llvm_version
    ]

    hash_vals = subprocess.check_output(hash_cmd)

    return self._ParseCommitMessages(llvm_git_dir, hash_vals.rstrip(),
                                     llvm_version)

  def GetLLVMHash(self, llvm_version):
    """Retrieves the LLVM hash corresponding to the LLVM version passed in.

    Args:
      llvm_version: The LLVM version to use as a delimiter.

    Returns:
      The hash as a string that corresponds to the LLVM version.
    """

    with self.CreateTempDirectory() as temp_dir:
      # Clone the "llvm-project" repo.
      self.CloneLLVMRepo(temp_dir)

      # Find the git hash.
      hash_value = self.GetGitHashForVersion(temp_dir, llvm_version)

    return hash_value

  def GetGoogle3LLVMHash(self):
    """Retrieves the google3 LLVM hash."""

    return self.GetLLVMHash(GetGoogle3LLVMVersion())

  def GetTopOfTrunkGitHash(self):
    """Gets the latest git hash from top of trunk of LLVM."""

    path_to_master_branch = 'refs/heads/master'

    llvm_tot_git_hash_cmd = [
        'git', 'ls-remote', self._llvm_url, path_to_master_branch
    ]

    llvm_tot_git_hash = subprocess.check_output(llvm_tot_git_hash_cmd)

    return llvm_tot_git_hash.rstrip().split()[0]


def main():
  """Prints the git hash of LLVM.

  Parses the command line for the optional command line
  arguments.
  """

  # Create parser and add optional command-line arguments.
  parser = argparse.ArgumentParser(description='Finds the LLVM hash.')
  parser.add_argument(
      '--llvm_version',
      type=is_svn_option,
      required=True,
      help='which git hash of LLVM to find '
      '{google3, ToT, <svn_version>}')

  # Parse command-line arguments.
  args_output = parser.parse_args()

  cur_llvm_version = args_output.llvm_version

  new_llvm_hash = LLVMHash()

  if isinstance(cur_llvm_version, int):
    # Find the git hash of the specific LLVM version.
    print(new_llvm_hash.GetLLVMHash(cur_llvm_version))
  elif cur_llvm_version == 'google3':
    print(new_llvm_hash.GetGoogle3LLVMHash())
  else:  # Find the top of trunk git hash of LLVM.
    print(new_llvm_hash.GetTopOfTrunkGitHash())


if __name__ == '__main__':
  main()
