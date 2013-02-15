#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to wrap run_remote_tests.sh script.

This script calls run_remote_tests.sh with standard tests.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import os
import sys
from utils import command_executer


def Main():
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="ChromeOS root checkout directory.")
  parser.add_option("-r", "--remote", dest="remote",
                    help="The IP address of the remote ChromeOS machine.")
  parser.add_option("-b", "--board", dest="board",
                    help="The board of the target.")

  tests = "BuildVerify"

  (options, args) = parser.parse_args()

  if options.board is None or options.remote is None:
    parser.print_help()
    sys.exit()

  if options.chromeos_root is None:
    options.chromeos_root = "../.."

  tests += " " + " ".join(args)
  return RunRemoteTests(options.chromeos_root, options.remote,
                        options.board, tests)


def RunRemoteTests(chromeos_root, remote, board, tests):
  """Run the remote tests."""
  command = (chromeos_root + "/src/scripts/run_remote_tests.sh" +
             " --remote=" + remote +
             " --board=" + board +
             " " + tests)

  retval = command_executer.GetCommandExecuter().RunCommand(command)
  return retval

if __name__ == "__main__":
  Main()
