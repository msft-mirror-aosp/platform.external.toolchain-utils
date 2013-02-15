#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to run ChromeOS benchmarks

Inputs:
    chromeos_root
    toolchain_root
    board
    [chromeos/cpu/<benchname>|chromeos/browser/[pagecycler|sunspider]|chromeos/startup]
    hostname/IP of Chromeos machine

    chromeos/cpu/<benchname>
       - Read run script rules from bench.mk perflab-bin, copy benchmark to host, run
       and return results.

    chromeos/startup
       - Re-image host with image in perflab-bin
       - Call run_tests to run startup test, gather results.
       - Restore host back to what it was.

    chromeos/browser/*
       - Call build_chromebrowser to build image with new browser
       - Copy image to perflab-bin

"""

__author__ = "bjanakiraman@google.com (Bhaskar Janakiraman)"

import optparse
import re
import sys
from utils import command_executer
from utils import utils


KNOWN_BENCHMARKS = [
    "chromeos/startup",
    "chromeos/browser/pagecycler",
    "chromeos/browser/sunspider",
    "chromeos/cpu/bikjmp"]

# Run command template


# Common initializations
cmd_executer = command_executer.GetCommandExecuter()


def Usage(parser, message):
  print "ERROR: " + message
  parser.print_help()
  sys.exit(0)


def RunBrowserBenchmark(bench, workdir, machine):
  """Run browser benchmarks.

  Args:
    bench: Name of benchmark (chromeos/browser/*)
    workdir: Directory containing benchmark directory
    machine: name of chromeos machine
  """
  # TODO(bjanakiraman): Implement function
  return 0


def RunStartupBenchmark(bench, workdir, machine):
  """Run browser benchmarks.

  Args:
    bench: Name of benchmark (chromeos/browser/*)
    workdir: Directory containing benchmark directory
    machine: name of chromeos machine
  """
  # TODO(bjanakiraman): Implement function
  return 0


def RunCpuBenchmark(bench, workdir, machine):
  """Run CPU benchmark.

  Args:
    bench: Name of benchmark
    workdir: directory containing benchmark directory
    machine: name of chromeos machine

  Returns:
    status: 0 on success
  """

  benchname = re.split('/', bench)[2]
  benchdir = '%s/%s' % (workdir, benchname)

  # Delete any existing run directories on machine.
  # Since this has exclusive access to the machine,
  # we do not worry about duplicates.
  args = 'chronos@%s ' % machine
  args += 'rm -rf /tmp/%s' % benchname
  retval = utils.ssh_cmd(args)
  if retval:
    return retval

  # Copy benchmark directory.
  args = ' -r %s ' % benchdir
  args += 'chronos@%s:/tmp' % machine
  retval = utils.scp_cmd(args)
  if retval:
    return retval

  # Parse bench.mk to extract run flags.

  benchmk_file = open('%s/bench.mk' % benchdir, 'r')
  for line in benchmk_file:
    line.rstrip()
    if re.match('^run_cmd', line):
      line = re.sub('^run_cmd.*\${PERFLAB_PATH}', '.', line)
      line = re.sub('\${PERFLAB_INPUT}', './data', line)
      run_cmd = line
      break

  # Execute on remote machine
  # Capture output and process it.
  sshargs = 'chronos@%s ' % machine
  sshargs += 'cd /tmp/%s\;' % benchname
  sshargs += 'time -p %s' % run_cmd
  print sshargs
  utils.ssh_cmd(sshargs)

  return retval


def Main(argv):
  """Build ChromeOS."""
  # Common initializations

  parser = optparse.OptionParser()
  parser.add_option("-c", "--chromeos_root", dest="chromeos_root",
                    help="Target directory for ChromeOS installation.")
  parser.add_option("-t", "--toolchain_root", dest="toolchain_root",
                    help="The gcctools directory of your P4 checkout.")
  parser.add_option("-m", "--machine", dest="machine",
                    help="The chromeos host machine.")
  parser.add_option("--workdir", dest="workdir", default="./perflab-bin",
                    help="Work directory for perflab outputs.")
  parser.add_option("--board", dest="board",
                    help="ChromeOS target board, e.g. x86-generic")

  (options, args) = parser.parse_args(argv[1:])

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

  if options.machine is None:
    Usage(parser, "--machine must be set")

  found_err = 0
  retval = 0
  for arg in args:
    # CPU benchmarks
    if re.match('chromeos/cpu', arg):
      comps = re.split('/', arg)
      benchname = comps[2]
      print "RUNNING %s" % benchname
      retval = RunCpuBenchmark(arg, options.workdir, options.machine)
      if not found_err:
        found_err = retval
    elif re.match('chromeos/startup', arg):
      print "RUNNING %s" % arg
      retval = RunStartupBenchmark(arg, options.workdir, options.machine)
      if not found_err:
        found_err = retval
    elif re.match('chromeos/browser', arg):
      print "RUNNING %s" % arg
      retval = RunBrowserBenchmark(arg, options.workdir, options.machine)
      if not found_err:
        found_err = retval

  return found_err

if __name__ == "__main__":
  Main(sys.argv)
