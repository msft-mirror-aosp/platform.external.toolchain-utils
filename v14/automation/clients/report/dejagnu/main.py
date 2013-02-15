#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from contextlib import contextmanager
from datetime import date
from datetime import datetime
import glob
from itertools import chain
import logging
import optparse
import os.path
import sys

from dejagnu import settings
from manifest import Manifest
from report import Report
from summary import DejaGnuTestRun


def AddBuildOption(parser):
  parser.add_option(
      '-B', dest='build', type='string',
      help=('Name of the build for which tests were run (e.g target triplet '
            '"x86_64-unknown-linux-gnu").'))


def ExpandGlobExprList(paths):
  """Returns an iterator that goes over expanded glob paths."""
  return chain.from_iterable(map(glob.glob, paths))


@contextmanager
def OptionChecker(parser):
  """Provides scoped environment for command line option checking."""
  try:
    yield
  except SystemExit as ex:
    parser.print_help()
    print ''
    sys.exit('ERROR: %s' % str(ex))


def ManifestCommand(argv):
  parser = optparse.OptionParser(
      description=(
          'Read in one or more DejaGNU summary files (.sum), parse their '
          'content and generate manifest files.  Manifest files store a list '
          'of failed tests that should be ignored.  Generated files are '
          'stored in current directory under following name: '
          '${build}-${tool}-${board}.xfail (e.g. '
          '"gcc-4.6.x-linux-gnu-x86_64-gcc-unix.xfail").'),
      usage='Usage: %prog manifest [-B build] [file.sum] (file2.sum ...)')
  AddBuildOption(parser)

  opts, args = parser.parse_args(argv[2:])

  with OptionChecker(parser):
    if not opts.build:
      sys.exit('Build option is mandatory.')

    if not args:
      sys.exit('At least one *.sum file required.')

  for filename in chain.from_iterable(map(glob.glob, args)):
    test_run = DejaGnuTestRun(opts.build)
    test_run.FromDejaGnuOutput(filename)
    test_run.CleanUpTestResults()

    manifest = Manifest.FromDejaGnuTestRun(test_run)
    manifest_filename = '%s-%s-%s.xfail' % (
        test_run.build, test_run.tool, test_run.board)

    with open(manifest_filename, 'w') as manifest_file:
      manifest_file.write(manifest.Generate())

      logging.info('Wrote manifest to "%s" file.', manifest_filename)


def ImportCommand(argv):
  parser = optparse.OptionParser(
      description=(
          'Read in one or more DejaGNU summary files (.sum), parse their '
          'content and put test results into the database.  Besides test '
          'results the scripts extracts tool name, board name, testrun date, '
          'target and host triplet.'),
      usage='Usage: %prog import [-B build] [file.sum] (file2.sum ...)')
  AddBuildOption(parser)

  opts, args = parser.parse_args(argv[2:])

  with OptionChecker(parser):
    if not opts.build:
      sys.exit('Build option is mandatory.')

    if not args:
      sys.exit('At least one *.sum file required.')

  logging.info('Using "%s" database.', settings.DATABASE_NAME)

  for filename in ExpandGlobExprList(args):
    test_run = DejaGnuTestRun(opts.build)
    test_run.FromDejaGnuOutput(filename)
    test_run.StoreInDb()


def ReportCommand(argv):
  parser = optparse.OptionParser(
      description=(
          'For selected test runs, extracts them from the database and '
          'generate a single report file in selected format (currently only '
          'HTML).'),
      usage=('Usage: %prog html-report [-B build] (-b board ...) (-d day) '
             '[report.html]'))
  AddBuildOption(parser)
  parser.add_option(
      '-b', dest='boards', type='string', action='append', default=None,
      help=('Extract test results only for specified board (use -b multiple '
            'times to specify more than one board).'))
  parser.add_option(
      '-d', dest='day', default=None,
      help=('Extract test results for test runs that were performed at '
            'specific date in MM/DD/YYYY format (default: %s)' %
            date.today().strftime('%m/%d/%Y')))
  parser.add_option(
      '-m', dest='manifests', type='string', action='append', default=None,
      help=('Suppress failures for test listed in provided manifest files. '
            '(use -m for each manifest file you want to read)'))

  opts, args = parser.parse_args(argv[2:])

  with OptionChecker(parser):
    if opts.day:
      try:
        opts.day = datetime.strptime(opts.day, '%m/%d/%Y')
      except ValueError:
        sys.exit('Date expected to be in MM/DD/YYYY format!')

    if not opts.build:
      sys.exit('Build option is mandatory.')

    if len(args) != 1:
      sys.exit('Exactly one output file expected.')

  logging.info('Using "%s" database.', settings.DATABASE_NAME)

  manifests = []

  for filename in ExpandGlobExprList(opts.manifests or []):
    logging.info('Using "%s" manifest.', filename)
    manifests.append(Manifest.FromFile(filename))

  report = Report(opts.build, opts.boards, opts.day).Generate(manifests)

  if report:
    with open(args[0], 'w') as html_file:
      html_file.write(report)
      logging.info('Wrote report to "%s" file.', args[0])


def HelpCommand(argv):
  sys.exit('\n'.join([
      'Usage: %s command [options]' % os.path.basename(argv[0]),
      '',
      'Commands:',
      '  import   - read dejagnu test results and store them in database',
      '  manifest - manage files containing a list of suppressed test failures',
      '  report   - generate report file for selected test runs']))


def Main(argv):
  try:
    cmd_name = argv[1]
  except IndexError:
    cmd_name = None

  cmd_map = {
      'import': ImportCommand,
      'manifest': ManifestCommand,
      'report': ReportCommand}
  cmd_map.get(cmd_name, HelpCommand)(argv)

if __name__ == '__main__':
  FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.INFO)

  Main(sys.argv)
