#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to build ChromeOS benchmarks

Inputs: 
    chromeos_root
    toolchain_root
    board
    [chromeos/cpu/<benchname>|chromeos/browser/[pagecycler|sunspider]|chromeos/startup]
    
    This script assumes toolchain has already been built in toolchain_root.

    chromeos/cpu/<benchname>
       - Execute bench.py script within chroot to build benchmark
       - Copy build results to perflab-bin

    chromeos/startup
       - Call build_chromeos to build image. 
       - Copy image to perflab-bin
       
    chromeos/browser/*
       - Call build_chromebrowser to build image with new browser
       - Copy image to perflab-bin

"""

__author__ = "bjanakiraman@google.com (Bhaskar Janakiraman)"

import optparse
import os
import sys
import re
import tc_enter_chroot
import build_chromeos
from utils import command_executer
from utils import logger
from utils import utils


KNOWN_BENCHMARKS = [
  'chromeos/startup',
  'chromeos/browser/pagecycler',
  'chromeos/browser/sunspider',
  'chromeos/cpu/bikjmp' ]

# Commands to build CPU benchmarks. 
CPU_BUILDCMD = "cd /usr/local/toolchain_root/v14/third_party/android_bench/v2_0/CLOSED_SOURCE/%s;\
python ../../scripts/bench.py --toolchain=/usr/bin --action=clean;\
python ../../scripts/bench.py --toolchain=/usr/bin --add_cflags=%s --add_ldflags=%s --makeopts=%s --action=build"



def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def Main(argv):
  """Build ChromeOS."""
  # Common initializations

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("--clobber_chroot", dest="clobber_chroot",
                    action="store_true", help=
                    "Delete the chroot and start fresh", default=False)
  parser.add_option("--clobber_board", dest="clobber_board",
                    action="store_true",
                    help="Delete the board and start fresh", default=False)
  parser.add_option("--cflags", dest="cflags", default="",
                    help="CFLAGS for the ChromeOS packages")
  parser.add_option("--cxxflags", dest="cxxflags",default="",
                    help="CXXFLAGS for the ChromeOS packages")
  parser.add_option("--ldflags", dest="ldflags", default="",
                    help="LDFLAGS for the ChromeOS packages")
  parser.add_option("--makeopts", dest="makeopts", default="",
                    help="Make options for the ChromeOS packages")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")

  (options,args) = parser.parse_args(argv[1:])

  # validate args
  for arg in args:
    if arg not in KNOWN_BENCHMARKS:
     utils.AssertTrue(False, "Bad benchmark %s specified" % arg)


       
  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.toolchain_root is None:
    Usage(parser, "--toolchain_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  found_err = 0
  for arg in args:
    # CPU benchmarks
    if re.match('chromeos/cpu', arg):
      comps = re.split('/', arg)
      build_chromeos.ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                            CPU_BUILDCMD % (comps[2], options.cflags, 
                                            options.ldflags, options.makeopts))
    elif re.match('chromeos/startup', arg):
      build_args = [os.path.dirname(os.path.abspath(__file__)) + "/build_chromeos.py",
      "--chromeos_root=" + options.chromeos_root,
      "--toolchain_root=" + options.toolchain_root,
      "--board=" + options.board,
      "--cflags=" + options.cflags,
      "--cxxflags=" + options.cxxflags,
      "--ldflags=" + options.ldflags,
      "--clobber_board"
      ]
      retval = build_chromeos.Main(build_args)
      if retval != 0:
         print "ERROR: Building chromeOS"
         found_err = 1
    elif re.match('chromeos/browser', arg):
      # For now, re-build os. TBD: Change to call build_browser 
      build_args = [os.path.dirname(os.path.abspath(__file__)) + "/build_chromeos.py",
      "--chromeos_root=" + options.chromeos_root,
      "--toolchain_root=" + options.toolchain_root,
      "--board=" + options.board,
      "--cflags=" + options.cflags,
      "--cxxflags=" + options.cxxflags,
      "--ldflags=" + options.ldflags,
      "--clobber_board" 
      ]
      retval = build_chromeos.Main(build_args)
      if retval != 0:
         print "ERROR: Building Chrome Browser"
         found_err = 1

  return found_err

if __name__ == "__main__":
  Main(sys.argv)
