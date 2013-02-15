#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import optparse
import pickle
import sys
import traceback
import xmlrpclib

from automation.common import job_group
from utils import logger
from automation.clients.helper import crosstool


class CrosstoolNightlyClient(object):
  VALID_TARGETS = ['gcc-4.4.3-glibc-2.11.1-armv7a-vfpv3.d16-hard',
                   'gcc-4.4.3-glibc-2.11.1-armv7a-vfpv3.d16-softfp',
                   'gcc-4.6.x-glibc-2.11.1-grte',
                   'gcc-4.6.x-glibc-2.11.1-powerpc']

  VALID_VERSIONS = ['v14', 'v15']

  def __init__(self, targets, crosstool_version, run_tests):
    assert crosstool_version in self.VALID_VERSIONS
    assert targets
    assert all(target in self.VALID_TARGETS for target in targets)

    self.targets = targets
    self.crosstool_version = crosstool_version
    self.run_tests = run_tests

  def Run(self):
    server = xmlrpclib.Server('http://localhost:8000')
    server.ExecuteJobGroup(pickle.dumps(self.CreateJobGroup()))

  def CreateJobGroup(self):
    factory = crosstool.JobsFactory(self.crosstool_version)

    p4_crosstool_job, checkout_dir = factory.CheckoutCrosstool()

    all_jobs = [p4_crosstool_job]

    for target in self.targets:
      # Build crosstool target
      release_job, build_tree_dir = factory.BuildRelease(checkout_dir, target)

      all_jobs.append(release_job)

      # Perform crosstool tests
      if self.run_tests:
        all_jobs.append(factory.RunTests(checkout_dir, build_tree_dir, target))

    return job_group.JobGroup('crosstool_nightly', all_jobs, True, False)


def InterceptAndLog(fun):
  def _Interceptor(*args, **kwargs):
    try:
      return fun(*args, **kwargs)
    except StandardError:
      logger.GetLogger().LogError(
          'Uncaught exception:\n%s' % traceback.format_exc())

  return _Interceptor


@InterceptAndLog
def Main(argv):
  valid_targets_string = ', '.join(CrosstoolNightlyClient.VALID_TARGETS)
  valid_versions_string = ', '.join(CrosstoolNightlyClient.VALID_VERSIONS)

  parser = optparse.OptionParser()
  parser.add_option('-t',
                    '--targets',
                    dest='targets',
                    action='append',
                    choices=CrosstoolNightlyClient.VALID_TARGETS,
                    default=[],
                    help='Target to build: %s.' % valid_targets_string)
  parser.add_option('-c',
                    '--crosstool-version',
                    dest='crosstool_version',
                    default='v15',
                    action='store',
                    choices=CrosstoolNightlyClient.VALID_VERSIONS,
                    help='Crosstool version: %s.' % valid_versions_string)
  parser.add_option('-T',
                    '--run-tests',
                    dest='run_tests',
                    default=False,
                    action='store_true',
                    help='Run DejaGNU tests against built components?')
  options, _ = parser.parse_args(argv)

  if not options.targets:
    parser.print_help()
    sys.exit('\nPlease provide at least one target.')

  option_list = [opt.dest for opt in parser.option_list if opt.dest]

  kwargs = dict((option, getattr(options, option)) for option in option_list)

  client = CrosstoolNightlyClient(**kwargs)
  client.Run()


if __name__ == '__main__':
  Main(sys.argv)
