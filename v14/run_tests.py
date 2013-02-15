#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to wrap run_remote_tests.sh script.

This script calls run_remote_tests.sh with standard tests.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import os
import re
import sys
from utils import command_executer
from utils import logger
from utils import utils
import build_chromeos


def Main(argv):
  """The main function."""
  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="ChromeOS root checkout directory.")
  parser.add_option("-r", "--remote", dest="remote",
                    help="The IP address of the remote ChromeOS machine.")
  parser.add_option("-b", "--board", dest="board",
                    help="The board of the target.")

  (options, args) = parser.parse_args(argv)

  tests = ""

  if options.board is None or options.remote is None:
    parser.print_help()
    return -1

  if options.chromeos_root is None:
    m = "--chromeos_root not given. Setting ../../ as chromeos_root"
    logger.GetLogger().LogWarning(m)
    options.chromeos_root = "../.."

  rrt_file = "%s/src/scripts/run_remote_tests.sh" % options.chromeos_root
  if not os.path.isfile(rrt_file):
    m = "File %s not found" % rrt_file
    logger.GetLogger().LogError(m)
    return -1

  if args:
    tests = " " + " ".join(args[1:])

  case_insensitive_page = re.compile("page", re.IGNORECASE)
  tests = case_insensitive_page.sub("Page", tests)

  return RunRemoteTests(options.chromeos_root, options.remote,
                        options.board, tests)


def RunRemoteTests(chromeos_root, remote, board, tests):
  """Run the remote tests."""
  command = ("./run_remote_tests.sh"
             " --remote=%s"
             " --board=%s"
             " %s" %
             (remote,
              board,
              tests))
  retval = utils.ExecuteCommandInChroot(chromeos_root, command)
  return retval

if __name__ == "__main__":
  sys.exit(Main(sys.argv))
