#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import pickle
import sys
import xmlrpclib

from automation.common import job
from automation.common import job_group
from automation.common import machine_description
from utils import utils


def Main():
  server = xmlrpclib.Server("http://localhost:8000")

  command = "%s/../../produce_output.py" % utils.GetRoot(sys.argv[0])[0]

  pwd_job = job.Job("pwd_job", command)
  pwd_job.DependsOnMachine(machine_description.MachineSpecification(os="linux"))

  group = job_group.JobGroup("pwd_client", [pwd_job])
  server.ExecuteJobGroup(pickle.dumps(group))


if __name__ == "__main__":
  Main()
