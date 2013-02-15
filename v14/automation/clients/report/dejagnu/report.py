# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from datetime import date
import os.path

from django.template import Template, Context

from models import RESULT_REVMAP, RESULT_GROUPS, RESULT_NAME
from models import TestRun, TestResultSummary, TestResult, TestResultSummary

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))


class Report(object):
  def __init__(self, build_name, boards=None, day=None):
    self._build_name = build_name
    self._boards = boards or []
    self._day = day or date.today()
    self._template_filename = os.path.join(ROOT_PATH, 'report.html')

  @staticmethod
  def PrepareSummary(res_types, summaries):
    summary = []

    for res_type in res_types:
      rt_summary = summaries.filter(result=RESULT_REVMAP[res_type])

      if rt_summary:
        rt_count = rt_summary[0].count
      else:
        rt_count = 0

      summary.append((RESULT_NAME[res_type], rt_count))

    return summary

  @staticmethod
  def PrepareTestList(res_types, results):
    tests = {}

    for res_type in res_types:
      rt_tests = [result.test
                  for result in results.filter(result=RESULT_REVMAP[res_type])]

      if rt_tests:
        tests[RESULT_NAME[res_type]] = [(test.suite.name, test.file.name,
                                         test.variant) for test in rt_tests]

    return tests

  def Generate(self):
    with open(self._template_filename) as template_file:
      template_content = template_file.read()

    template = Template(template_content)
    context = Context({'test_runs': []})

    for test_run in TestRun.objects.filter(date__gte=date.today()):
      groups = {}

      for res_group, res_types in RESULT_GROUPS.items():
        groups[res_group] = {
            'summary': Report.PrepareSummary(
                res_types, TestResultSummary.objects.filter(test_run=test_run)),
            'tests': Report.PrepareTestList(
                res_types, TestResult.objects.filter(test_run=test_run))}

      context['test_runs'].append({
          'id': test_run.id,
          'name': '%s @%s' % (test_run.name, test_run.board),
          'groups': groups})

    return template.render(context)
