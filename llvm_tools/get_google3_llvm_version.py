#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gets the latest google3 llvm version"""

from __future__ import print_function

from pipes import quote
import argparse
import traceback
import os

from cros_utils import command_executer


class LLVMVersion(object):
  """Provides a method to retrieve the latest google3 llvm version."""

  def __init__(self, log_level="none"):
    self._ce = command_executer.GetCommandExecuter(log_level=log_level)

  def _DeleteClient(self):
    """Deletes a created client."""

    # delete client
    delete_cmd = 'g4 citc -d my_local_client'
    ret, _, err = self._ce.RunCommandWOutput(delete_cmd, print_to_console=False)

    if ret:  # failed to delete client
      raise ValueError("Failed to delete client: %s" % err)

  def _CreateClient(self):
    """Creates a client returns a path to the google3 directory.

    Args:
      ce: A CommandExecuter object for executing commands

    Returns:
      A string that is the path to the google3 directory.

    Raises:
      Exception: Failed to create a client.
    """

    # number of tries to create client
    num_tries = 2

    # cmd to create client
    client_cmd = 'p4 g4d -f my_local_client'

    # try to create client
    for _ in range(num_tries):
      ret, google3_path, err = self._ce.RunCommandWOutput(
          client_cmd, print_to_console=False)

      if not ret: # created client
        return google3_path

      try: # delete client and re-try
        self._DeleteClient()
      except ValueError:
        traceback.print_exc()

    raise Exception('Failed to create a client: %s' % err)

  def GetGoogle3LLVMVersion(self):
    """Gets the latest google3 llvm version.

    Creates a client to retrieve the llvm version.
    The client is then deleted after the llvm version is retrieved.

    Returns:
      The latest llvm version as an integer.

    Raises:
      Exception: An invalid path has been provided to the cat command.
    """

    # create a client and get the path
    google3_path = self._CreateClient()

    try:
      # remove '\n' at the end
      google3_path = google3_path.strip()

      # cmd to retrieve latest version
      llvm_version_path = 'third_party/crosstool/v18/stable/' \
          'installs/llvm/revision'

      path_to_version = os.path.join(google3_path, llvm_version_path)
      cat_cmd = 'cat %s' % quote(path_to_version)

      # get latest version
      ret, g3_version, err = self._ce.RunCommandWOutput(
          cat_cmd, print_to_console=False)
      # check return code
      if ret:  # failed to get latest version
        raise Exception('Failed to get google3 llvm version: %s' % err)
    finally:
      # no longer need the client
      self._DeleteClient()

    # change type to an integer
    return int(g3_version.strip())


def main():
  """Prints the google3 llvm version.

  Parses the command line for the optional command line
  argument.
  """

  # create parser and add optional command-line argument
  parser = argparse.ArgumentParser(description='Get the google3 llvm version.')
  parser.add_argument(
      '--log_level',
      default='none',
      choices=['none', 'quiet', 'average', 'verbose'],
      help='the level for the logs (default: %(default)s)')

  # parse command-line arguments
  args_output = parser.parse_args()

  cur_log_level = args_output.log_level  # get log level

  print(LLVMVersion(log_level=cur_log_level).GetGoogle3LLVMVersion())


if __name__ == '__main__':
  main()
