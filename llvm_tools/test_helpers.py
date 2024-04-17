# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions for unit testing."""

import contextlib
import inspect
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


class ArgsOutputTest:
    """Testing class to simulate a argument parser object."""

    def __init__(self, svn_option="google3"):
        self.chromeos_path = "/abs/path/to/chroot"
        self.last_tested = "/abs/path/to/last_tested_file.json"
        self.llvm_version = svn_option
        self.extra_change_lists = None
        self.options = ["latest-toolchain"]
        self.builders = ["some-builder"]


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
    """

    counter = [0]

    def Result(*args, **kwargs):
        # For some values of `counter`, the mock function would simulate
        # raising an exception, so let the test case catch the exception via
        # `unittest.TestCase.assertRaises()` and to also handle recursive
        # functions.
        prev_counter = counter[0]
        counter[0] += 1

        ret_value = mock_function(prev_counter, *args, **kwargs)

        return ret_value

    return Result


def WritePrettyJsonFile(file_name, json_object):
    """Writes the contents of the file to the json object.

    Args:
        file_name: The file that has contents to be used for the json object.
        json_object: The json object to write to.
    """

    json.dump(file_name, json_object, indent=4, separators=(",", ": "))


def CreateTemporaryJsonFile():
    """Makes a temporary .json file."""

    return CreateTemporaryFile(suffix=".json")


@contextlib.contextmanager
def CreateTemporaryFile(suffix=""):
    """Makes a temporary file."""

    fd, temp_file_path = tempfile.mkstemp(suffix=suffix)

    os.close(fd)

    try:
        yield temp_file_path

    finally:
        if os.path.isfile(temp_file_path):
            os.remove(temp_file_path)


class TempDirTestCase(unittest.TestCase):
    """Subclass for test-cases. Provides a `make_tempdir()` function."""

    def make_tempdir(self) -> Path:
        defining_file = Path(inspect.getfile(self.__class__))
        test_file_name = Path(defining_file).with_suffix("").name
        tempdir = Path(tempfile.mkdtemp(prefix=test_file_name + "_"))
        self.addCleanup(shutil.rmtree, tempdir)
        return tempdir
