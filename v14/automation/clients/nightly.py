#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import pickle
import sys
import xmlrpclib

from automation.common import job
from automation.common import job_group
from automation.clients import jobs_helper


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

  server = xmlrpclib.Server("http://localhost:8000")

  tc_job = jobs_helper.CreateBuildTCJob(toolchain=options.toolchain,
                                        board=options.board)

  tc_root = jobs_helper.GetTCRootDir(options.toolchain)[1]
  tc_pkgs_dir = job.FolderDependency(tc_job, tc_root + jobs_helper.tc_pkgs_dir)
  tc_objects_dir = job.FolderDependency(tc_job,
                                        tc_root + jobs_helper.tc_objects_dir)

  # Perform the correctness tests
  build_chromeos_job = \
      jobs_helper.CreateBuildAndTestChromeOSJob("weekly",
                                                toolchain=options.toolchain,
                                                board=options.board)
  build_chromeos_job.DependsOnFolder(tc_pkgs_dir)

  dejagnu_job = jobs_helper.CreateDejaGNUJob(toolchain=options.toolchain,
                                             board=options.board)
  dejagnu_job.DependsOnFolder(tc_pkgs_dir)
  dejagnu_job.DependsOnFolder(tc_objects_dir)

  # Perform the performance tests
  perflab_job = jobs_helper.CreatePerflabJob("quarterly",
                                             options.perflab_benchmarks,
                                             toolchain=options.toolchain,
                                             board=options.board)
  perflab_job.DependsOnFolder(tc_pkgs_dir)

  all_jobs = [tc_job, build_chromeos_job, dejagnu_job, perflab_job]
  group = job_group.JobGroup("nightly_client", all_jobs, True, False)
  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main(sys.argv)
