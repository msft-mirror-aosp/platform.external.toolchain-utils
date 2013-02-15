#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import os.path
import pickle
import xmlrpclib

from automation.common import command as cmd
from automation.common import job
from automation.clients.helper import jobs


def Main():
  server = xmlrpclib.Server("http://localhost:8000")

  # TODO(asharif): add a setup_chromeos job here.
  p4_port = "perforce2:2666"
  p4_paths = [("//depot2/gcctools/chromeos/v14/...",
               "gcctools/chromeos/v14/..."),
              ("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
               "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...")]
  p4_revision = 1
  p4_checkoutdir = "perforce2"

  p4_job = jobs.CreateP4Job(p4_port, p4_paths, p4_revision, p4_checkoutdir)
  p4_output = job.FolderDependency(p4_job, "perforce2")
  setup_chromeos_job = jobs.CreateSetupChromeOSJob(p4_job, "latest")
  setup_chromeos_output = job.FolderDependency(setup_chromeos_job, "chromeos")

  build_tc = cmd.Shell(
      "build_tc.py",
      path=os.path.join(p4_checkoutdir, "gcctools/chromeos/v14"),
      opts=["--toolchain_root=%s" % os.path.join(p4_checkoutdir, "gcctools"),
            "--chromeos_root=%s" % "chromeos"])
  tc_job = job.Job("build_tc", build_tc)
  tc_job.DependsOnFolder(p4_output)
  tc_job.DependsOnFolder(setup_chromeos_output)

  server.ExecuteJobGroup(pickle.dumps([p4_job, setup_chromeos_job, tc_job]))


if __name__ == "__main__":
  Main()
