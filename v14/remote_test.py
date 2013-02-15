#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to wrap run_remote_tests.sh script.

This script can login to the chromeos machine using the test private key.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import os
import re
import sys
from utils import command_executer
from utils import utils


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
  if options.chromeos_root is None:
    Usage(parser, "chromeos_root must be given")

  if options.remote is None:
    Usage(parser, "remote must be given")

  options.chromeos_root = os.path.expanduser(options.chromeos_root)

  command = "ls -lt /"
  ce = command_executer.GetCommandExecuter()
  ce.CrosRunCommand(command,
                    chromeos_root=options.chromeos_root,
                    machine=options.remote)

  version_dir = utils.GetRoot(sys.argv[0])[0]
  ce.CopyFiles(version_dir,
               "/tmp",
               dest_machine=options.remote,
               dest_cros=True,
               chromeos_root=options.chromeos_root)
  board = ce.CrosLearnBoard(options.chromeos_root, "172.18.117.239")
  print board


if __name__ == "__main__":
  Main(sys.argv)
