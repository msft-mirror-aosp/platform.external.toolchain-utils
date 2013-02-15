#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Jobs helper module unit tests."""

__author__ = "asharif@google.com (Ahmad Sharif)"

import unittest

from automation.clients.helper import jobs


class JobsHelperTest(unittest.TestCase):
  def setUp(self):
    pass

  def testGetP4Command(self):
    p4_port = "perforce2:2666"
    p4_paths = [("//depot2/gcctools/chromeos/v14/...",
                 "gcctools/chromeos/v14/..."),
                ("//depot2/gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...",
                 "gcctools/google_vendor_src_branch/gcc/gcc-4.4.3/...")]
    p4_revision = 1
    p4_checkoutdir = "perforce2"

    test_cmd = jobs.GetP4Command(p4_port, p4_paths, p4_revision, p4_checkoutdir)

    self.assertTrue("g4" in str(test_cmd))


if __name__ == "__main__":
  unittest.main()
