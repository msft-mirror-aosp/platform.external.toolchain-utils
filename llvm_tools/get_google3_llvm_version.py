#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gets the latest google3 LLVM version."""

from __future__ import print_function

import subprocess


class LLVMVersion(object):
  """Provides a method to retrieve the latest google3 LLVM version."""

  def GetGoogle3LLVMVersion(self):
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


def main():
  """Prints the google3 llvm version."""

  print(LLVMVersion().GetGoogle3LLVMVersion())


if __name__ == '__main__':
  main()
