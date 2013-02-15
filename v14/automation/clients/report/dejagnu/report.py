# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from datetime import date
import logging
import os.path

from django.template import Context
from django.template import Template

from models import GetResultName
from models import TestRun
from summary import DejaGnuTestRun

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))

RESULT_GROUPS = {
    'Successes': ['PASS', 'XFAIL'],
    'Failures': ['FAIL', 'XPASS', 'UNRESOLVED'],
    'Suppressed': ['!FAIL', '!XPASS', '!UNRESOLVED', '!ERROR'],
    'Framework': ['UNTESTED', 'UNSUPPORTED', 'ERROR', 'WARNING', 'NOTE']}


class Report(object):
  def __init__(self, build_name, boards=None, day=None):
    self._build_name = build_name
    self._boards = boards or []
    self._day = day or date.today()
    self._template_filename = os.path.join(ROOT_PATH, 'report.html')

  @staticmethod
  def _PrepareSummary(res_types, summary):
    def GetResultCount(res_type):
      return summary.get(res_type, 0)

    return [(GetResultName(rt), GetResultCount(rt)) for rt in res_types]

  @staticmethod
  def _PrepareTestList(res_types, tests):
    def GetTestsByResult(res_type):
      return [(test.name, test.variant or '')
              for test in sorted(tests)
              if test.result == res_type]

    return [(GetResultName(rt), GetTestsByResult(rt))
            for rt in res_types if rt != 'PASS']

  def Generate(self, manifests):
    with open(self._template_filename) as template_file:
      template_content = template_file.read()

    template = Template(template_content)
    context = Context({'test_runs': []})

    test_runs = [DejaGnuTestRun.FromDbObject(test_run)
                 for test_run in TestRun.Select(self._build_name, self._day,
                                                self._boards)]

    if not test_runs:
      logging.error('No test run matching your criteria found.')
      return

    for test_run_id, test_run in enumerate(test_runs):
      logging.info('Generating report for: %s.', test_run)

      test_run.CleanUpTestResults()
      test_run.SuppressTestResults(manifests)

      # Generate summary and test list for each result group
      groups = {}

      for res_group, res_types in RESULT_GROUPS.items():
        summary_all = self._PrepareSummary(res_types, test_run.summary)
        tests_all = self._PrepareTestList(res_types, test_run.results)

        has_2nd = lambda tuple2: bool(tuple2[1])
        summary = filter(has_2nd, summary_all)
        tests = filter(has_2nd, tests_all)

        if summary or tests:
          groups[res_group] = {'summary': summary, 'tests': tests}

      context['test_runs'].append({
          'id': test_run_id,
          'name': '%s @%s' % (test_run.tool, test_run.board),
          'groups': groups})

    logging.info('Rendering report in HTML format.')

    return template.render(context)
