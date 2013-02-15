#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

import logging
import optparse
import os.path
import sys

from report import Report
from summary import Summary


def SummaryCommand(argv):
  parser = optparse.OptionParser(
      description=('Process DejaGNU summary files and put test results into '
                   'the database.'),
      usage='Usage: %prog summary [-B build] [file.sum] (file2.sum ...)')
  parser.add_option(
      '-B', dest='build', type='string',
      help='Name of the build for which tests were run.')

  opts, args = parser.parse_args(argv)

  if not opts.build:
    parser.print_help()
    sys.exit('\nERROR: Build option is mandatory.')

  for filename in args:
    summary = Summary(opts.build, filename)
    summary.Analyse()
    summary.Save()


def HtmlReportCommand(argv):
  parser = optparse.OptionParser(
      description=('Extract test results from database for specific BUILD, '
                   'generate HTML report and write it to the file.'),
      usage=('Usage: %prog html-report [-B build] (-b board ...) (-d day) '
             '[report.html]'))
  parser.add_option(
      '-B', dest='build', type='string',
      help='Name of the build for which tests were run.')
  parser.add_option(
      '-b', dest='boards', type='string', default=None,
      help=('Extract test results only for specified board (use -b multiple'
            ' times to specify more than one board).'))
  parser.add_option(
      '-d', dest='day', default=None,
      help=('Extract test results for test runs that were performed at'
            ' specific date (by default latest test runs are considered).'))

  opts, args = parser.parse_args(argv)

  try:
    if not opts.build:
      sys.exit('ERROR: Build option is mandatory.')

    if len(args) != 1:
      sys.exit('ERROR: Exactly one output file expected.')
  except SystemExit:
    parser.print_help()
    print ''
    raise

  report = Report(opts.build, opts.boards, opts.day)

  with open(args[0], 'w') as html_file:
    html_file.write(report.Generate())


def Main(argv):
  if not argv or argv[0] not in ['summary', 'html-report']:
    sys.exit('\n'.join([
        'Usage: %s command [options]' % os.path.basename(sys.argv[0]),
        '',
        'Commands:',
        '  summary - to put dejagnu results into database',
        '  html-report - to generate html report.']))

  command = argv.pop(0)

  if command == 'summary':
    SummaryCommand(argv)
  elif command == 'html-report':
    HtmlReportCommand(argv)

if __name__ == '__main__':
  FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.DEBUG)

  Main(sys.argv[1:])
