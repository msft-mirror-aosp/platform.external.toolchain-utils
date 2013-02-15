#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Machine manager unittest.

MachineManagerTest tests MachineManager.
"""

__author__ = "asharif@google.com (Ahmad Sharif)"


import job
import jobs_helper
import unittest


class JobsHelperTest(unittest.TestCase):
  def setUp(self):
    pass


  def testCreateP4Job(self):
    p4_port = "perforce2:2666"
    p4_paths = []
    p4_paths.append(("//depot2/gcctools/chromeos/v14/...", "gcctools/chromeos/v14/..."))
    p4_paths.append(("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                 "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/..."))
    p4_revision = 1
    p4_checkoutdir = "perforce2"

    test_job = jobs_helper.CreateP4Job(p4_port, p4_paths, p4_revision,
                                       p4_checkoutdir)

    self.assertTrue("g4" in test_job.command)


if __name__ == "__main__":
  unittest.main()
