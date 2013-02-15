#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import pickle
import sys
import xmlrpclib

from automation.common import job_group
from automation.clients import jobs_helper


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

  server = xmlrpclib.Server("http://localhost:8000")

  update_job = jobs_helper.CreateUpdateJob(options.chromeos_version,
                                           boards=options.board)

  group = job_group.JobGroup("update_client", [update_job], False, False)

  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main(sys.argv)
