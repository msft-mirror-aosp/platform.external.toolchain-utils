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
  parser.add_option("-t",
                    "--toolchain",
                    dest="toolchain",
                    default="v2",
                    help="Toolchain to use {trunk|branch}")
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-generic",
                    help="Board to use for the nightly job.")
  parser.add_option("-l",
                    "--perflab-benchmarks",
                    dest="perflab_benchmarks",
                    default=",".join(["chromeos/cpu/bikjmp",
                                      "chromeos/browser/sunspider",
                                      "chromeos/browser/pagecycler"]),
                    help="Comma-separated perflab benchmarks to run")
  options = parser.parse_args(argv)[0]

  jobs = chromeos.JobsFactory(toolchain=options.toolchain,
                              board=options.board)

  # Build toolchain
  tc_job, tc_pkgs_dep, tc_objs_dep = jobs.BuildToolchain()

  # Perform the correctness tests
  build_chromeos_job = jobs.BuildAndTestChromeOS("weekly", tc_pkgs_dep)
  dejagnu_job = jobs.RunDejaGNU(tc_pkgs_dep, tc_objs_dep)

  # Perform the performance tests
  perflab_job = jobs.RunPerflab("top", options.perflab_benchmarks, tc_pkgs_dep)

  all_jobs = [tc_job, build_chromeos_job, dejagnu_job, perflab_job]
  group = job_group.JobGroup("nightly_client", all_jobs, True, False)

  server = xmlrpclib.Server("http://localhost:8000")
  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main(sys.argv)
