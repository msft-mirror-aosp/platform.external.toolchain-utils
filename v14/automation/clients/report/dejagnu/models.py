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


class TestRun(models.Model):
  name = models.TextField()
  build = models.TextField()
  board = models.TextField()
  date = models.DateTimeField()
  host = models.TextField()
  target = models.TextField()

  def __str__(self):
    return ', '.join([self.name, self.build, self.board, str(self.date),
                      self.host, self.target])


class TestResultSummary(models.Model):
  test_run = models.ForeignKey(TestRun)
  result = models.CharField(max_length=1, choices=RESULT_CHOICES)
  count = models.IntegerField()

  def __str__(self):
    return ', '.join([
        str(self.test_run), RESULT_MAP[self.result], str(self.count)])


class TestSuite(models.Model):
  name = models.TextField()

  def __str__(self):
    return self.name


class TestFile(models.Model):
  name = models.TextField()

  def __str__(self):
    return self.name


class Test(models.Model):
  suite = models.ForeignKey(TestSuite)
  file = models.ForeignKey(TestFile)
  variant = models.TextField()

  def __str__(self):
    return ', '.join([str(self.suite), str(self.file), self.variant])


class TestResult(models.Model):
  test_run = models.ForeignKey(TestRun)
  test = models.ForeignKey(Test)
  result = models.CharField(max_length=1, choices=RESULT_CHOICES)

  def __str__(self):
    return ', '.join([
        str(self.test_run), str(self.test), RESULT_MAP[self.result]])
