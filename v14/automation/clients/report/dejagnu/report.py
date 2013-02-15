# /usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

import logging
import os.path


class Report(object):
  RESULT_DESCRIPTION = {
      'ERROR': 'DejaGNU errors',
      'FAIL': 'Failed tests',
      'NOTE': 'DejaGNU notices',
      'PASS': 'Passed tests',
      'UNRESOLVED': 'Unresolved tests',
      'UNSUPPORTED': 'Unsupported tests',
      'UNTESTED': 'Not executed tests',
      'WARNING': 'DejaGNU warnings',
      'XFAIL': 'Expected test failures',
      'XPASS': 'Unexpectedly passed tests'}

  RESULT_GROUPS = {
      'Successes': ['PASS', 'XFAIL'],
      'Failures': ['FAIL', 'XPASS', 'UNRESOLVED'],
      'Suppressed': ['!FAIL', '!XPASS', '!UNRESOLVED', '!ERROR'],
      'Framework': ['UNTESTED', 'UNSUPPORTED', 'ERROR', 'WARNING', 'NOTE']}

  ROOT_PATH = os.path.dirname(os.path.abspath(__file__))

  def __init__(self, test_runs, manifests):
    self._test_runs = test_runs
    self._manifests = manifests

  def _GetResultDescription(self, name):
    if name.startswith('!'):
      name = name[1:]

    try:
      return self.RESULT_DESCRIPTION[name]
    except KeyError:
      raise ValueError('Unknown result: "%s"' % name)

  def _PrepareSummary(self, res_types, summary):
    def GetResultCount(res_type):
      return summary.get(res_type, 0)

    return [(self._GetResultDescription(rt), GetResultCount(rt))
            for rt in res_types]

  def _PrepareTestList(self, res_types, tests):
    def GetTestsByResult(res_type):
      return [(test.name, test.variant or '')
              for test in sorted(tests)
              if test.result == res_type]

    return [(self._GetResultDescription(rt), GetTestsByResult(rt))
            for rt in res_types if rt != 'PASS']

  def Generate(self):
    test_runs = []

    for test_run_id, test_run in enumerate(self._test_runs):
      logging.info('Generating report for: %s.', test_run)

      test_run.CleanUpTestResults()
      test_run.SuppressTestResults(self._manifests)

      # Generate summary and test list for each result group
      groups = {}

      for res_group, res_types in self.RESULT_GROUPS.items():
        summary_all = self._PrepareSummary(res_types, test_run.summary)
        tests_all = self._PrepareTestList(res_types, test_run.results)

        has_2nd = lambda tuple2: bool(tuple2[1])
        summary = filter(has_2nd, summary_all)
        tests = filter(has_2nd, tests_all)

        if summary or tests:
          groups[res_group] = {'summary': summary, 'tests': tests}

      test_runs.append({
          'id': test_run_id,
          'name': '%s @%s' % (test_run.tool, test_run.board),
          'groups': groups})

    logging.info('Rendering report in HTML format.')

    try:
      from django import template
      from django.template import loader
      from django.conf import settings
    except ImportError:
      logging.error('Django framework not installed!')
      logging.error('Failed to generate report in HTML format!')
      return ''

    settings.configure(DEBUG=True, TEMPLATE_DEBUG=True,
                       TEMPLATE_DIRS=(self.ROOT_PATH,))

    tmpl = loader.get_template('report.html')
    ctx = template.Context({'test_runs': test_runs})

    return tmpl.render(ctx)
