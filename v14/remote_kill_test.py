#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to wrap run_remote_tests.sh script.

Run this script and kill it. Then run ps -ef to see if sleep
is still running,. 
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import os
import re
import sys
import subprocess

from utils import command_executer


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)

def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="ChromeOS root checkout directory")
  parser.add_option("-r", "--remote", dest="remote",
                    help="Remote chromeos device.")
  options = parser.parse_args(argv)[0]
  ce = command_executer.GetCommandExecuter()
  ce.RunCommand("ls; sleep 10000",
                machine=os.uname()[1])
  return 0


if __name__ == "__main__":
  Main(sys.argv)
