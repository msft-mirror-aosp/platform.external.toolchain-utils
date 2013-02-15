#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from django.db import models

models.Model.Meta = type('Meta', (object,), dict(app_label='dejagnu'))

RESULT_CHOICES = (
    ('E', 'ERROR'),
    ('F', 'FAIL'),
    ('n', 'NOTE'),
    ('P', 'PASS'),
    ('r', 'UNRESOLVED'),
    ('s', 'UNSUPPORTED'),
    ('t', 'UNTESTED'),
    ('W', 'WARNING'),
    ('f', 'XFAIL'),
    ('p', 'XPASS'))

RESULT_NAME = {
    'ERROR': 'DejaGNU error',
    'FAIL': 'Test failed',
    'NOTE': 'DejaGNU notice',
    'PASS': 'Test passed',
    'UNRESOLVED': 'Unresolved test',
    'UNSUPPORTED': 'Unsupported test',
    'UNTESTED': 'Test not run',
    'WARNING': 'DejaGNU warning',
    'XFAIL': 'Expected failure',
    'XPASS': 'Unexpected pass'}

RESULT_MAP = dict(RESULT_CHOICES)
RESULT_REVMAP = dict(zip(RESULT_MAP.values(), RESULT_MAP.keys()))
RESULT_GROUPS = {
    'success': ['PASS', 'XFAIL'],
    'failure': ['FAIL', 'XPASS', 'UNRESOLVED'],
    'framework': ['UNTESTED', 'UNSUPPORTED', 'ERROR', 'WARNING', 'NOTE']}


class Build(models.Model):
  name = models.TextField(
      help_text=('Target triplet or any other identifier (e.g. '
                 'gcc-4.6.x-ubuntu_lucid-x86_64).'))
  tool = models.TextField(
      help_text='Tool under test (e.g. gcc, g++, libstdc++).')
  # Board is included here and not in TestRun, because test results might be
  # different for two boards and TestResultFilterRule cannot refer to TestRun.
  board = models.TextField(
      help_text='Board used to execute test binaries (e.g. unix, qemu).')

  def __unicode__(self):
    return '{0}, {1} @{2}'.format(self.name, self.tool, self.board)


class TestRun(models.Model):
  build = models.ForeignKey(Build)
  date = models.DateTimeField(
      help_text='When the test run was started.')
  host = models.TextField(
      help_text='Triplet describing host machine.')
  target = models.TextField(
      help_text='Triplet describing target machine.')

  def __unicode__(self):
    return '{0} on {1}'.format(self.build, self.date)


class TestResultSummary(models.Model):
  test_run = models.ForeignKey(TestRun)
  result = models.CharField(max_length=1, choices=RESULT_CHOICES,
                            help_text='Test result (abbreviated).')
  count = models.IntegerField(help_text='Number of tests with the same result.')

  def __unicode__(self):
    return '{0}, {1}, {2}'.format(
        self.test_run, self.get_result_display(), self.count)


class Test(models.Model):
  name = models.TextField(
      help_text='Test suite name (eg. gcc.c-torture/compile/981001-2.c).')
  variant = models.TextField(
      null=True,
      help_text=('Several tests can be performed on a single file. This field '
                 'makes such tests distinguishable.'))

  def __unicode__(self):
    if not self.variant:
      return self.name
    else:
      return '{0} ({1})'.format(self.name, self.variant)


class TestResult(models.Model):
  test_run = models.ForeignKey(TestRun)
  test = models.ForeignKey(Test)
  result = models.CharField(max_length=1, choices=RESULT_CHOICES,
                            help_text='Test result (abbreviated).')

  def __unicode__(self):
    return '{0}: [{1}] {2}'.format(
        self.test_run, self.get_result_display(), self.test)


class TestResultRewriteRule(models.Model):
  build = models.ForeignKey(Build)
  test = models.ForeignKey(Test)
  old_result = models.CharField(
      max_length=1, choices=RESULT_CHOICES, default='F',
      help_text='If a test result has this value, the rule will be applied.')
  new_result = models.CharField(
      max_length=1, choices=RESULT_CHOICES, default='f',
      help_text='Value that will replace original test result value.')
  expires = models.DateTimeField(
      null=True,
      help_text='After this date the rule will not be applied.')
  owner = models.EmailField(
      help_text='Who added this rule.')
  reason = models.TextField(
      help_text='The reason for which this rule was added.')

  def __unicode__(self):
    expires = 'before {0} '.format(self.expires) if self.expires else ''

    return '{0}: [{1}] replace {2} with {3} {4}(by {5}: "{6}")'.format(
        self.build, self.test, self.get_old_result_display(),
        self.get_new_result_display(), expires, self.owner, self.reason)
