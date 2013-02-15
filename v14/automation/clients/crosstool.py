#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import optparse
import pickle
import sys
import traceback
import xmlrpclib

from automation.clients.helper import crosstool
from automation.common import job_group
from automation.common import logger


class CrosstoolNightlyClient(object):
  VALID_TARGETS = ['gcc-4.4.3-glibc-2.11.1-armv7a-vfpv3.d16-hard',
                   'gcc-4.4.3-glibc-2.11.1-armv7a-vfpv3.d16-softfp',
                   'gcc-4.6.x-ubuntu_lucid-x86_64']
  VALID_BOARDS = ['qemu', 'pandaboard']

  def __init__(self, target, boards):
    assert target in self.VALID_TARGETS
    assert all(board in self.VALID_BOARDS for board in boards)

    self._target = target
    self._boards = boards

  def Run(self):
    server = xmlrpclib.Server('http://localhost:8000')
    server.ExecuteJobGroup(pickle.dumps(self.CreateJobGroup()))

  def CreateJobGroup(self):
    factory = crosstool.JobsFactory()

    checkout_crosstool_job, checkout_dir = factory.CheckoutCrosstool()

    all_jobs = [checkout_crosstool_job]

    # Build crosstool target
    build_release_job, build_tree_dir = factory.BuildRelease(
        checkout_dir, self._target)
    all_jobs.append(build_release_job)

    test_jobs = []

    # Perform crosstool tests
    for board in self._boards:
      test_jobs.append(factory.RunTests(
          checkout_dir, build_tree_dir, self._target, board))

    all_jobs.extend(test_jobs)

    generate_report_job = factory.GenerateReport(test_jobs, self._target)
    all_jobs.append(generate_report_job)

    return job_group.JobGroup('Crosstool Nightly Build', all_jobs, True, False)


@logger.HandleUncaughtExceptions
def Main(argv):
  valid_boards_string = ', '.join(CrosstoolNightlyClient.VALID_BOARDS)

  parser = optparse.OptionParser()
  parser.add_option('-b',
                    '--board',
                    dest='boards',
                    action='append',
                    choices=CrosstoolNightlyClient.VALID_BOARDS,
                    default=[],
                    help=('Run DejaGNU tests on selected boards: %s.' %
                          valid_boards_string))
  options, args = parser.parse_args(argv)

  if len(args) == 2:
    target = args[1]
  else:
    sys.exit('Exactly one target required as a command line argument!')

  option_list = [opt.dest for opt in parser.option_list if opt.dest]

  kwargs = dict((option, getattr(options, option)) for option in option_list)

  client = CrosstoolNightlyClient(target, **kwargs)
  client.Run()


if __name__ == '__main__':
  Main(sys.argv)
