#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build the ChromeOS toolchain.

This script sets up the toolchain if you give it the gcctools directory.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"

import optparse
import sys
from utils import utils

# Common initializations
(rootdir, basename) = utils.GetRoot(sys.argv[0])
utils.InitLogger(rootdir, basename)

parser = optparse.OptionParser()
parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                  help="ChromeOS root checkout directory.")
parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                  help="Toolchain root directory.")
parser.add_option("-b", "--board", dest="board",
                  help="board is the argument to the setup_board command.")

(options, args) = parser.parse_args()

if options.toolchain_root is None or options.board is None:
  parser.print_help()
  sys.exit()

command = (rootdir + "/tc-enter-chroot.sh")
if options.chromeos_root is not None:
  command += " --chromeos_root=" + options.chromeos_root
if options.toolchain_root is not None:
  command += " --toolchain_root=" + options.toolchain_root
command += (" -- ./setup_board --nousepkg --board=" + options.board +
            " --gcc_version=9999")

retval = utils.RunCommand(command)
assert retval == 0, "Retval should have been 0!"
