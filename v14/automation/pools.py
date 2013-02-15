#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.
"""Machine pools file.

A pool is a list of machines.
"""

import machine

__author__ = "asharif@google.com (Ahmad Sharif)"

machines = []
machines.append(machine.Machine("chrome-dev1.hot", "core2duo", 4, "linux", "raymes"))
machines.append(machine.Machine("chrome-dev2.hot", "core2duo", 4, "linux", "raymes"))
machines.append(machine.Machine("cros1", "atom", 1, "chromeos", "chronos"))
machines.append(machine.Machine("cros1", "atom", 1, "chromeos", "chronos"))

