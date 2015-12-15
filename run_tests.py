#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
"""Script to wrap run_remote_tests.sh script.

This script calls run_remote_tests.sh with standard tests.
"""

__author__ = 'asharif@google.com (Ahmad Sharif)'

import optparse
import os
import re
import sys

from utils import command_executer
from utils import logger
import build_chromeos


def Main(argv):
  """The main function."""
  print 'This script is deprecated.  Use crosperf for running tests.'
  return 1


if __name__ == '__main__':
  sys.exit(Main(sys.argv))
