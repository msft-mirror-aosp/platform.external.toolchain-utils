#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import os.path
import pickle
import sys
import xmlrpclib

from automation.common import job_group
from automation.clients.helper import chromeos


def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-c",
                    "--chromeos-versions",
                    dest="chromeos_versions",
                    help="Use these chromeos versions. "
                    "Example: -c latest,weekly,quarterly")
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="v1",
                    help="Toolchain to use {trunk|v1}")
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-generic",
                    help="Board to build for.")
  parser.add_option("-p",
                    "--p4-snapshot",
                    dest="p4_snapshot",
                    default="",
                    help="An existing perforce checkout for debugging.")
  parser.add_option("-d",
                    "--deja-gnu",
                    dest="dejagnu",
                    default=False,
                    action="store_true",
                    help="Should the deja-gnu tests be run?")
  parser.add_option("-l",
                    "--perflab-benchmarks",
                    dest="perflab_benchmarks",
                    help="Comma-separated perflab benchmarks to run")
  options = parser.parse_args(argv)[0]

  if not len(options.board.split(",")) == 1:
    sys.exit("Exactly one board accepted.")

  if not options.chromeos_versions:
    sys.exit("No ChromeOS version list provided")

  jobs = chromeos.JobsFactory(toolchain=options.toolchain,
                              board=options.board,
                              p4_snapshot=options.p4_snapshot)

  tc_job, tc_pkgs_dep, tc_objs_dep = jobs.BuildToolchain()
  all_jobs = [tc_job]

  versions = options.chromeos_versions.strip()

  for version in versions.split(","):
    all_jobs.append(jobs.BuildAndTestChromeOS(version, tc_pkgs_dep))

    for benchmark in options.perflab_benchmarks.split(","):
      all_jobs.append(jobs.RunPerflab(version, benchmark, tc_pkgs_dep))

  if options.dejagnu:
    all_jobs.append(jobs.RunDejaGNU(tc_pkgs_dep, tc_objs_dep))

  group = job_group.JobGroup("test_client", all_jobs, False, False)

  server = xmlrpclib.Server("http://localhost:8000")
  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main(sys.argv)
