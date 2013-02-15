#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine pools file.

A pool is a list of machines.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


machines = { "chrome-dev1.hot": ["core2duo", 4, "linux"],
             "ahmad.mtv": ["core2duo", 4, "linux"],
             "cros1": ["atom", 1, "chromeos"],
             "cros2": ["atom", 1, "chromeos"],
}

named_pools = {"build_pool": ["chrome-dev1.hot", "ahmad.mtv"],
               "reimage_pool": ["cros1"]}

