# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from collections import namedtuple
from datetime import datetime
from itertools import groupby
import os.path
import re

from django.db import transaction

from models import RESULT_REVMAP
from models import Test, TestFile, TestRun, TestResult, TestResultSummary
from models import TestSuite

_Test = namedtuple('_Test', ('suite', 'filename', 'variant', 'result'))


class Summary(object):
  def __init__(self, build_name, filename):
    self._build_name = build_name
    self._filename = filename
    self._test_run = {}
    self._test_results = []

    self._test_output_re = re.compile(r'^([A-Z]+):\s+([\w/\+\.\-]+)(.*)$')

  def _ParseHeader(self, line):
    fields = re.match(r'Running target (.*)', line)
    if fields:
      self._test_run['board'] = fields.group(1).strip()
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
      result = RESULT_REVMAP[fields.group(1)]
      path = fields.group(2)
      variant = fields.group(3)

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

      # split path into test filename and test suite
      filename = os.path.basename(path)
      suite = os.path.dirname(path)

      # Some tests are picked up from current directory. They're assigned to
      # no-name test suite.
      if suite == '.':
        suite = ''

      # Save the result.
      self._test_results.append(_Test(suite, filename, variant, result))

    return 'BODY'

  def Analyse(self):
    with open(self._filename, 'r') as report:
      lines = [line.strip() for line in report.readlines() if line.strip()]

    part = 'HEADER'

    for line in lines:
      if part is 'HEADER':
        part = self._ParseHeader(line)
      elif part is 'BODY':
        part = self._ParseBody(line)

  @transaction.commit_manually
  def Save(self):
    test_run_name = os.path.basename(self._filename).rstrip('.sum')

    test_run_obj = TestRun.objects.create(name=test_run_name,
                                          build=self._build_name,
                                          board=self._test_run['board'],
                                          date=self._test_run['date'],
                                          host=self._test_run['host'],
                                          target=self._test_run['target'])
    test_run_obj.save()

    type_key = lambda v: v.result
    test_results_by_type = sorted(self._test_results, key=type_key)

    for res, res_list in groupby(test_results_by_type, key=type_key):
      TestResultSummary(test_run=test_run_obj, result=res,
                        count=len(list(res_list))).save()

    suite_key = lambda v: v.suite
    test_results_by_suite = sorted(self._test_results, key=suite_key)

    for suite, res_list in groupby(test_results_by_suite, key=suite_key):
      suite_obj, is_new = TestSuite.objects.get_or_create(name=suite)

      if is_new:
        suite_obj.save()

      for res in res_list:
        file_obj, is_new = TestFile.objects.get_or_create(name=res.filename)

        if is_new:
          file_obj.save()

        test_obj, is_new = Test.objects.get_or_create(
            suite=suite_obj, file=file_obj, variant=res.variant)

        if is_new:
          test_obj.save()

        if res.result != RESULT_REVMAP['PASS']:
          TestResult.objects.create(test_run=test_run_obj, test=test_obj,
                                    result=res.result).save()

    transaction.commit()
