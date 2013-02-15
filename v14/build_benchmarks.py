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

CPU_BUILDCMD_CLEAN = "cd /usr/local/toolchain_root/v14/third_party/android_bench/v2_0/CLOSED_SOURCE/%s;\
python ../../scripts/bench.py --toolchain=/usr/bin --action=clean;"

CPU_BUILDCMD_BUILD = "cd /usr/local/toolchain_root/v14/third_party/android_bench/v2_0/CLOSED_SOURCE/%s;\
python ../../scripts/bench.py --toolchain=/usr/bin --add_cflags=%s --add_ldflags=%s --makeopts=%s --action=build"


# Common initializations
cmd_executer = command_executer.GetCommandExecuter()


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def CreateRunsh(destdir, benchmark):
  """Create run.sh script to run benchmark.  Perflab needs a run.sh that runs the benchmark."""
  run_cmd = os.path.dirname(os.path.abspath(__file__)) + "/run_benchmarks.py"
  contents = "#!/bin/sh\n%s $@ %s\n" % (run_cmd, benchmark)
  runshfile = destdir + '/run.sh'
  f = open(runshfile, 'w')
  f.write(contents)
  f.close()
  cmd_executer.RunCommand('chmod +x %s' % runshfile)


def CreateBinaryCopy(sourcedir, destdir):
  """Create links in perflab-bin/destdir/* to sourcedir/* for now, instead of copies"""

  # check if sourcedir exists
  if not os.path.exists(sourcedir):
    utils.AssertError(False, "benchmark results %s does not exist." % sourcedir)
    return 1

  # Deal with old copies - save off old ones for now.
  # Note - if its a link, it doesn't save anything.
  if os.path.exists(destdir):
    command = 'rm -rf %s.old' % destdir
    cmd_executer.RunCommand(command)
    command = 'mv %s %s.old' % (destdir, destdir)
    cmd_executer.RunCommand(command)
  os.makedirs(destdir)
  sourcedir = os.path.abspath(sourcedir)
  command = 'ln -s %s/* %s' % (sourcedir, destdir)
  cmd_executer.RunCommand(command)


def Main(argv):
  """Build ChromeOS."""
  # Common initializations

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("-C", "--clean", dest="clean", action="store_true",
                    default=False, help="Clean up build."),
  parser.add_option("-B", "--build", dest="build", action="store_true",
                    default=False, help="Build benchmark."),
  parser.add_option("-O", "--only_copy", dest="only_copy", action="store_true",
                    default=False, help="Only copy to perflab-bin - no builds."),
  parser.add_option("--workdir", dest="workdir", default=".",
                    help="Work directory for perflab outputs.")
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
     utils.AssertExit(False, "Bad benchmark %s specified" % arg)


  if options.chromeos_root is None:
    Usage(parser, "--chromeos_root must be set")

  if options.toolchain_root is None:
    Usage(parser, "--toolchain_root must be set")

  if options.board is None:
    Usage(parser, "--board must be set")

  found_err = 0
  retval = 0
  for arg in args:
    # CPU benchmarks
    if re.match('chromeos/cpu', arg):
      comps = re.split('/', arg)
      benchname = comps[2]
      if options.clean:
        retval = build_chromeos.ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                              CPU_BUILDCMD_CLEAN % benchname)
        utils.AssertError(retval == 0, "clean of benchmark %s failed." % arg)
      if options.build:
        retval = build_chromeos.ExecuteCommandInChroot(options.chromeos_root, options.toolchain_root,
                                              CPU_BUILDCMD_BUILD % (benchname, options.cflags,
                                              options.ldflags, options.makeopts))
        utils.AssertError(retval == 0, "Build of benchmark %s failed." % arg)
      if retval == 0 and (options.build or options.only_copy):
        benchdir = 'third_party/android_bench/v2_0/CLOSED_SOURCE/%s' % benchname
        linkdir = '%s/perflab-bin/%s' % (options.workdir, arg)
        CreateBinaryCopy(benchdir, linkdir)
        CreateRunsh(linkdir, arg)
      if not found_err:
        found_err = retval
    elif re.match('chromeos/startup', arg):
      if options.build:
      # Clean for chromeos/browser and chromeos/startup is a Nop since builds are always from scratch.
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
        utils.AssertError(retval == 0, "Build of ChromeOS failed.")
      if retval == 0 and (options.build or options.only_copy):
        benchdir = '%s/src/build/images/%s/latest' % (options.chromeos_root, options.board)
        linkdir = '%s/perflab-bin/startup/latest' % options.workdir
        CreateBinaryCopy(benchdir, linkdir)
        CreateRunsh(linkdir, arg)
      if not found_err:
        found_err = retval
    elif re.match('chromeos/browser', arg):
      if options.build:
        # For now, re-build os. TBD: Change to call build_browser
        build_args = [os.path.dirname(os.path.abspath(__file__)) + "/build_chrome_browser.py",
                      "--chromeos_root=" + options.chromeos_root,
                      "--toolchain_root=" + options.toolchain_root,
                      "--board=" + options.board,
                      "--cflags=" + options.cflags,
                      "--cxxflags=" + options.cxxflags,
                      "--ldflags=" + options.ldflags
                     ]
        retval = build_chromeos.Main(build_args)
        utils.AssertError(retval == 0, "Build of ChromeOS failed.")
      if retval == 0 and (options.build or options.only_copy):
        benchdir = '%s/src/build/images/%s/latest' % (options.chromeos_root, options.board)
        linkdir = '%s/perflab-bin/browser/latest' % options.workdir
        CreateBinaryCopy(benchdir,linkdir)
        CreateRunsh(linkdir, arg)
      if not found_err:
        found_err = retval

  return found_err

if __name__ == "__main__":
  Main(sys.argv)
