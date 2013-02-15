#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import pickle
import sys
import xmlrpclib

from automation.common import job_group
from automation.clients.helper import chromeos


def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-c",
                    "--chromeos-version",
                    dest="chromeos_version",
                    default="weekly",
                    help="Update what version of chromeos.")
  parser.add_option("-b",
                    "--board",
                    dest="board",
                    default="x86-generic,x86-agz",
                    help="The board(s) (for updating binary builds).")
  options = parser.parse_args(argv)[0]

  jobs = chromeos.JobsFactory(board=options.board)

  update_job = jobs.RunUpdate(options.chromeos_version)
  group = job_group.JobGroup("update_client", [update_job], False, False)

  server = xmlrpclib.Server("http://localhost:8000")
  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main(sys.argv)
