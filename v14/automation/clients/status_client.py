#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

import optparse
import pickle
import sys
import xmlrpclib


def Main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-s",
                    "--server",
                    dest="server",
                    default="localhost",
                    help="The server address (default is localhost).")
  parser.add_option("-p",
                    "--port",
                    dest="port",
                    default="8000",
                    help="The port of the server.")
  options = parser.parse_args(argv)[0]
  server = xmlrpclib.Server("http://%s:%s" % (options.server, options.port))
  job_groups = pickle.loads(server.GetAllJobGroups())
  for job_group in reversed(job_groups):
    print job_group


if __name__ == "__main__":
  Main(sys.argv)
