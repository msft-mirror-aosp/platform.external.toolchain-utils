# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions for unit testing."""

from __future__ import print_function

from contextlib import contextmanager
from tempfile import mkstemp
import json
import os


# FIXME: Migrate modules with similar helper to use this module.
def CallCountsToMockFunctions(mock_function):
  """A decorator that passes a call count to the function it decorates.

  Examples:
    @CallCountsToMockFunctions
    def foo(call_count):
      return call_count
    ...
    ...
    [foo(), foo(), foo()]
    [0, 1, 2]

  NOTE: This decorator will not handle recursive functions properly.
  """

  counter = [0]

  def Result(*args, **kwargs):
    ret_value = mock_function(counter[0], *args, **kwargs)
    counter[0] += 1
    return ret_value

  return Result


def WritePrettyJsonFile(file_name, json_object):
  """Writes the contents of the file to the json object.

  Args:
    file_name: The file that has contents to be used for the json object.
    json_object: The json object to write to.
  """

  json.dump(file_name, json_object, indent=4, separators=(',', ': '))


@contextmanager
def CreateTemporaryJsonFile():
  """Makes a temporary .json file."""

  # Create a temporary file to simulate a .json file.
  fd, temp_file_path = mkstemp()

  temp_json_file = '%s.json' % temp_file_path

  os.close(fd)
  os.remove(temp_file_path)

  try:
    yield temp_json_file

  finally:
    # Make sure that the file was created.
    if os.path.isfile(temp_json_file):
      os.remove(temp_json_file)
