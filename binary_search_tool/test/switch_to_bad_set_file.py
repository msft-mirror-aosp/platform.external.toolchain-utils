#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Switch part of the objects file in working set to (possible) bad ones.

This script is meant to be specifically used with the set_file test. This uses
the set files generated by binary_search_state to do the switching.
"""


import os
import sys

from binary_search_tool.test import common


def Main(_):
    """Switch part of the objects file in working set to (possible) bad ones."""
    working_set = common.ReadWorkingSet()
    objects_file = common.ReadObjectsFile()

    if not os.path.exists(os.environ["BISECT_BAD_SET"]):
        print("Bad set file does not exist!")
        return 1

    object_index = common.ReadObjectIndex(os.environ["BISECT_BAD_SET"])

    for oi in object_index:
        working_set[int(oi)] = objects_file[oi]

    common.WriteWorkingSet(working_set)

    return 0


if __name__ == "__main__":
    retval = Main(sys.argv)
    sys.exit(retval)
