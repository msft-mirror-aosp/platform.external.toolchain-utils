#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gets the latest google3 LLVM version"""

from __future__ import print_function

from pipes import quote
import argparse

from cros_utils import command_executer


class LLVMVersion(object):
  """Provides a method to retrieve the latest google3 LLVM version."""

  def __init__(self, log_level="none"):
    self._ce = command_executer.GetCommandExecuter(log_level=log_level)

  def GetGoogle3LLVMVersion(self):
    """Gets the latest google3 LLVM version.

    Returns:
      The latest LLVM version as an integer.

    Raises:
      ValueError: An invalid path has been provided to the cat command.
    """

    path_to_google3_llvm_version = ('/google/src/head/depot/google3/third_party'
                                    '/crosstool/v18/stable/installs/llvm/'
                                    'revision')

    # Cmd to get latest google3 LLVM version.
    cat_cmd = 'cat %s' % quote(path_to_google3_llvm_version)

    # Get latest version.
    ret, g3_version, err = self._ce.RunCommandWOutput(
        cat_cmd, print_to_console=False)

    if ret:  # Failed to get the latest google3 LLVM version.
      raise ValueError('Failed to get google3 LLVM version: %s' % err)

    # Change type to an integer
    return int(g3_version.rstrip())


def main():
  """Prints the google3 LLVM version.

  Parses the command line for the optional command line
  argument.
  """

  # create parser and add optional command-line argument
  parser = argparse.ArgumentParser(description='Get the google3 LLVM version.')
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
