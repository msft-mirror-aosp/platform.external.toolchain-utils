#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.
# Author: kbaclawski@google.com (Krystian Baclawski)
#

from datetime import timedelta

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

RESULT_MAP = dict(RESULT_CHOICES)
RESULT_REVMAP = dict(zip(RESULT_MAP.values(), RESULT_MAP.keys()))
RESULT_NAME = {
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


def GetResultName(name):
  if name.startswith('!'):
    name = name[1:]

  try:
    return RESULT_NAME[name]
  except KeyError:
    raise ValueError('Unknown result: "%s"' % name)


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

  @classmethod
  def Select(cls, build, day, boards=None):
    builds = Build.objects.filter(name=build)

    if boards:
      builds = builds.filter(board__in=boards)

    return cls.objects.filter(
        build__in=builds,
        date__gte=day,
        date__lt=day + timedelta(days=1))

  def __unicode__(self):
    return '{0} on {1}'.format(self.build, self.date)


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
