#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""
This simulates a real job by producing a lot of output.

"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import os
import re
import sys
import time
from utils import command_executer


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()

  (options, args) = parser.parse_args(argv)

  for j in range(10):
    for i in range(10000):
      print str(j) + "The quick brown fox jumped over the lazy dog." + str(i)
    time.sleep(60)

  return 0


if __name__ == "__main__":
  Main(sys.argv)
