# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from datetime import date
from datetime import timedelta
import logging
import os.path

from django.template import Context
from django.template import Template

from models import Build
from models import RESULT_GROUPS
from models import RESULT_NAME
from models import RESULT_REVMAP
from models import TestResult
from models import TestResultRewriteRule
from models import TestResultSummary
from models import TestRun

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))


class Report(object):
  def __init__(self, build_name, boards=None, day=None):
    self._build_name = build_name
    self._boards = boards or []
    self._day = day or date.today()
    self._template_filename = os.path.join(ROOT_PATH, 'report.html')

  @staticmethod
  def PrepareSummary(res_types, summary):
    def GetResultCount(res_type):
      return summary.get(RESULT_REVMAP[res_type], 0)

    return [(RESULT_NAME[rt], GetResultCount(rt)) for rt in res_types]

  @staticmethod
  def PrepareTestList(res_types, tests):
    def GetTestsByResult(res_type):
      return [(test.name, test.variant or '')
              for test, result in tests.items()
              if result == RESULT_REVMAP[res_type]]

    return [(RESULT_NAME[rt], GetTestsByResult(rt)) for rt in res_types]

  def Generate(self):
    with open(self._template_filename) as template_file:
      template_content = template_file.read()

    template = Template(template_content)
    context = Context({'test_runs': []})

    builds = Build.objects.filter(name=self._build_name)

    if self._boards:
      builds = builds.filter(board__in=self._boards)

    test_runs = TestRun.objects.filter(
        build__in=builds,
        date__gte=self._day,
        date__lt=self._day + timedelta(days=1))

    if not test_runs:
      logging.error('No test run matching your criteria found.')
      return

    for test_run in test_runs:
      logging.info('Generating report for: %s.', test_run)

      # Extract all useful data from database
      result_summary = TestResultSummary.objects.filter(test_run=test_run)
      test_results = TestResult.objects.filter(test_run=test_run)
      rewrite_rules = TestResultRewriteRule.objects.filter(build=test_run.build)

      # Reorganize extracted data for conveniency and performance reasons
      summary = dict((s.result, s.count) for s in result_summary)
      tests = dict((r.test, r.result) for r in test_results)

      # Modify test results accordingly to rewrite rules.
      for rule in rewrite_rules:
        if rule.expires and test_run.date > rule.expires:
          continue

        # Check if there's a test result (at most one) for which the rewrite
        # rule should be applied (i.e. test result should be modified for
        # reporting purposes). Refer to dejagnu.models.TestResultRewriteRule.
        if rule.test in tests:
          if tests[rule.test] == rule.old_result:
            tests[rule.test] = rule.new_result
            summary[rule.old_result] -= 1
            summary[rule.new_result] += 1

      # Generate summary and test list for each result group
      groups = {}

      for res_group, res_types in RESULT_GROUPS.items():
        groups[res_group] = {
            'summary': Report.PrepareSummary(res_types, summary),
            'tests': Report.PrepareTestList(res_types, tests)}

      context['test_runs'].append({
          'id': test_run.id,
          'name': '%s @%s' % (test_run.build.tool, test_run.build.board),
          'groups': groups})

    logging.info('Rendering report in HTML format.')

    return template.render(context)
