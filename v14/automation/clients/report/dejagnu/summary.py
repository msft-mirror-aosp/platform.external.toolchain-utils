# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from collections import namedtuple
from datetime import datetime
from itertools import groupby
import logging
import os.path
import re

from django.db import transaction

from models import Build
from models import RESULT_REVMAP
from models import Test
from models import TestResult
from models import TestResultSummary
from models import TestRun


class Summary(object):
  Result = namedtuple('Result', 'name variant result')

  def __init__(self, build_name, filename):
    self._filename = filename
    self._build = {'name': build_name,
                   'tool': os.path.basename(filename).rstrip('.sum')}
    self._test_run = {}
    self._test_results = []

    self._test_output_re = re.compile(r'^([A-Z]+):\s+([\w/\+\.\-]+)(.*)$')

  def _ParseHeader(self, line):
    fields = re.match(r'Running target (.*)', line)
    if fields:
      self._build['board'] = fields.group(1).strip()
      return 'BODY'

    fields = re.match(r'Test Run By (.*) on (.*)', line)
    if fields:
      self._test_run['date'] = datetime.strptime(
          fields.group(2).strip(), '%a %b %d %X %Y')

    fields = re.match(r'Target(\s+)is (.*)', line)
    if fields:
      self._test_run['target'] = fields.group(2).strip()

    fields = re.match(r'Host(\s+)is (.*)', line)
    if fields:
      self._test_run['host'] = fields.group(2).strip()

    return 'HEADER'

  def _ParseBody(self, line):
    if re.match(r'=== .* Summary ===', line):
      return 'END'

    fields = self._test_output_re.match(line)

    if fields:
      result, path, variant = fields.groups()

      # some of the tests are generated in build dir and are issued from there,
      # because every test run is performed in randomly named tmp directory we
      # need to remove random part
      try:
        # assume that 2nd field is a test path
        path_parts = path.split('/')

        index = path_parts.index('testsuite')
        path = '/'.join(path_parts[index + 1:])
      except ValueError:
        path = '/'.join(path_parts)

      # Remove junk from test description.
      variant = variant.strip(', ')

      substitutions = [
          # remove include paths - they contain name of tmp directory
          ('-I\S+', ''),
          # remove extranous comments
          ('\s*\(test for excess errors\)\s*', ''),
          # compress white spaces
          ('\s+', ' ')]

      for pattern, replacement in substitutions:
        variant = re.sub(pattern, replacement, variant)

      # Some tests separate last component of path by space, so actual filename
      # ends up in description instead of path part. Correct that.
      try:
        first, rest = variant.split(' ', 1)
      except ValueError:
        pass
      else:
        if first.endswith('.o'):
          path = os.path.join(path, first)
          variant = rest

      # DejaGNU framework errors don't contain path part at all, so description
      # part has to be reconstructed.
      if not any(os.path.basename(path).endswith('.%s' %suffix)
                 for suffix in ['h', 'c', 'C', 'S', 'H', 'cc', 'i', 'o']):
        variant = '%s %s' % (path, variant)
        path = ''

      # Some tests are picked up from current directory (presumably DejaGNU
      # generates some test files). Remove the prefix for these files.
      if path.startswith('./'):
        path = path[2:]

      # Save the result.
      self._test_results.append(
          self.Result(path, variant or None, RESULT_REVMAP[result]))

    return 'BODY'

  def Analyse(self):
    logging.info('Reading "%s" DejaGNU report file.', self._filename)

    with open(self._filename, 'r') as report:
      lines = [line.strip() for line in report.readlines() if line.strip()]

    part = 'HEADER'

    for line in lines:
      if part is 'HEADER':
        part = self._ParseHeader(line)
      elif part is 'BODY':
        part = self._ParseBody(line)

    logging.info('DejaGNU report file parsed successfully.')

  @transaction.commit_manually
  def Save(self):
    # Create and store new test run
    build = self._build
    build_obj, is_new = Build.objects.get_or_create(
        name=build['name'], tool=build['tool'], board=build['board'])

    if is_new:
      build_obj.save()
      logging.info('Stored new build: %s.', build_obj)

    test_run = self._test_run
    test_run_obj = TestRun(build=build_obj, date=test_run['date'],
                           host=test_run['host'], target=test_run['target'])
    test_run_obj.save()

    transaction.commit()

    # Create and store test result summary
    type_key = lambda v: v.result
    test_results_by_type = sorted(self._test_results, key=type_key)

    for res, res_list in groupby(test_results_by_type, key=type_key):
      TestResultSummary(test_run=test_run_obj, result=res,
                        count=len(list(res_list))).save()

    transaction.commit()

    # Complete the list of test names.
    tests = dict(((test.name, test.variant), test)
                 for test in Test.objects.all())

    missing_tests = [res for res in self._test_results
                     if (res.name, res.variant) not in tests]

    if missing_tests:
      logging.info('Storing missing test names for: %s.', test_run_obj)

      for test in missing_tests:
        test_name_obj = Test(name=test.name, variant=test.variant)
        test_name_obj.save()

        logging.debug('Saved test name: %s.', test_name_obj)

        tests[(test.name, test.variant)] = test_name_obj

      transaction.commit()

    # Create and store test results
    logging.info('Storing test results for: %s.', test_run_obj)

    for res in self._test_results:
      if res.result != RESULT_REVMAP['PASS']:
        test_res_obj = TestResult(test_run=test_run_obj,
                                  test=tests[(res.name, res.variant)],
                                  result=res.result)
        logging.debug('Storing: %s.', test_res_obj)
        test_res_obj.save()

    transaction.commit()

    logging.info('Report stored successfully.')
