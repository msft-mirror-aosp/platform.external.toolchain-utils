#!/usr/bin/python2
#
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittest for the results reporter."""

from __future__ import division
from __future__ import print_function

from StringIO import StringIO

import collections
import mock
import os
import test_flag
import unittest

from benchmark_run import MockBenchmarkRun
from cros_utils import logger
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from machine_manager import MockCrosMachine
from machine_manager import MockMachineManager
from results_cache import MockResult
from results_report import HTMLResultsReport
from results_report import JSONResultsReport
from results_report import ParseChromeosImage
from results_report import TextResultsReport


class FreeFunctionsTest(unittest.TestCase):
  """Tests for any free functions in results_report."""

  def testParseChromeosImage(self):
    # N.B. the cases with blank versions aren't explicitly supported by
    # ParseChromeosImage. I'm not sure if they need to be supported, but the
    # goal of this was to capture existing functionality as much as possible.
    base_case = '/my/chroot/src/build/images/x86-generic/R01-1.0.date-time' \
        '/chromiumos_test_image.bin'
    self.assertEqual(ParseChromeosImage(base_case), ('R01-1.0', base_case))

    dir_base_case = os.path.dirname(base_case)
    self.assertEqual(ParseChromeosImage(dir_base_case), ('', dir_base_case))

    buildbot_case = '/my/chroot/chroot/tmp/buildbot-build/R02-1.0.date-time' \
        '/chromiumos_test_image.bin'
    buildbot_img = buildbot_case.split('/chroot/tmp')[1]

    self.assertEqual(ParseChromeosImage(buildbot_case),
                     ('R02-1.0', buildbot_img))
    self.assertEqual(ParseChromeosImage(os.path.dirname(buildbot_case)),
                     ('', os.path.dirname(buildbot_img)))

    # Ensure we don't act completely insanely given a few mildly insane paths.
    fun_case = '/chromiumos_test_image.bin'
    self.assertEqual(ParseChromeosImage(fun_case), ('', fun_case))

    fun_case2 = 'chromiumos_test_image.bin'
    self.assertEqual(ParseChromeosImage(fun_case2), ('', fun_case2))


# There are many ways for this to be done better, but the linter complains
# about all of them (that I can think of, at least).
_fake_path_number = [0]
def FakePath(ext):
  """Makes a unique path that shouldn't exist on the host system.

  Each call returns a different path, so if said path finds its way into an
  error message, it may be easier to track it to its source.
  """
  _fake_path_number[0] += 1
  prefix = '/tmp/should/not/exist/%d/' % (_fake_path_number[0], )
  return os.path.join(prefix, ext)


def MakeMockExperiment(compiler='gcc'):
  """Mocks an experiment using the given compiler."""
  mock_experiment_file = StringIO("""
      board: x86-alex
      remote: 127.0.0.1
      perf_args: record -a -e cycles
      benchmark: PageCycler {
        iterations: 3
      }

      image1 {
        chromeos_image: %s
      }

      image2 {
        remote: 127.0.0.2
        chromeos_image: %s
      }
      """ % (FakePath('cros_image1.bin'), FakePath('cros_image2.bin')))
  efile = ExperimentFile(mock_experiment_file)
  experiment = ExperimentFactory().GetExperiment(efile,
                                                 FakePath('working_directory'),
                                                 FakePath('log_dir'))
  for label in experiment.labels:
    label.compiler = compiler
  return experiment


def _InjectSuccesses(experiment, how_many, keyvals, for_benchmark=0,
                     label=None):
  """Injects successful experiment runs (for each label) into the experiment."""
  # Defensive copy of keyvals, so if it's modified, we'll know.
  keyvals = dict(keyvals)
  num_configs = len(experiment.benchmarks) * len(experiment.labels)
  num_runs = len(experiment.benchmark_runs) // num_configs

  # TODO(gbiv): Centralize the mocking of these, maybe? (It's also done in
  # benchmark_run_unittest)
  bench = experiment.benchmarks[for_benchmark]
  cache_conditions = []
  log_level = 'average'
  share_cache = ''
  locks_dir = ''
  log = logger.GetLogger()
  machine_manager = MockMachineManager(FakePath('chromeos_root'), 0,
                                       log_level, locks_dir)
  machine_manager.AddMachine('testing_machine')
  machine = next(m for m in machine_manager.GetMachines()
                 if m.name == 'testing_machine')
  for label in experiment.labels:
    def MakeSuccessfulRun(n):
      run = MockBenchmarkRun('mock_success%d' % (n, ), bench, label,
                             1 + n + num_runs, cache_conditions,
                             machine_manager, log, log_level, share_cache)
      mock_result = MockResult(log, label, log_level, machine)
      mock_result.keyvals = keyvals
      run.result = mock_result
      return run

    experiment.benchmark_runs.extend(MakeSuccessfulRun(n)
                                     for n in xrange(how_many))
  return experiment


class TextResultsReportTest(unittest.TestCase):
  """Tests that the output of a text report contains the things we pass in.

  At the moment, this doesn't care deeply about the format in which said
  things are displayed. It just cares that they're present.
  """

  def _checkReport(self, email):
    num_success = 2
    success_keyvals = {'retval': 0, 'machine': 'some bot', 'a_float': 3.96}
    experiment = _InjectSuccesses(MakeMockExperiment(), num_success,
                                  success_keyvals)
    text_report = TextResultsReport(experiment, email=email).GetReport()
    self.assertIn(str(success_keyvals['a_float']), text_report)
    self.assertIn(success_keyvals['machine'], text_report)
    self.assertIn(MockCrosMachine.CPUINFO_STRING, text_report)
    return text_report


  def testOutput(self):
    email_report = self._checkReport(email=True)
    text_report = self._checkReport(email=False)

    # Ensure that the reports somehow different. Otherwise, having the
    # distinction is useless.
    self.assertNotEqual(email_report, text_report)


class HTMLResultsReportTest(unittest.TestCase):
  """Tests that the output of a HTML report contains the things we pass in.

  At the moment, this doesn't care deeply about the format in which said
  things are displayed. It just cares that they're present.
  """

  _TestOutput = collections.namedtuple('TestOutput', ['summary_table',
                                                      'perf_html',
                                                      'charts',
                                                      'table_html',
                                                      'experiment_file'])

  @staticmethod
  def _TupleToTestOutput(to_what):
    fields = {}
    # to_what has 13 fields. So, dealing with it can be unfun.
    it = iter(to_what)
    next(it) # perf_init
    next(it) # chart_javascript
    fields['summary_table'] = next(it) # HTML summary
    next(it) # plaintext summary
    next(it) # TSV summary
    next(it) # tab menu summary
    fields['perf_html'] = next(it)
    fields['charts'] = next(it)
    fields['table_html'] = next(it)
    next(it) # full table plain text
    next(it) # full table TSV
    next(it) # full tab menu
    fields['experiment_file'] = next(it)

    remaining_fields = list(it)
    if not remaining_fields:
      return HTMLResultsReportTest._TestOutput(**fields)

    raise RuntimeError('Initialization missed field(s): %s' %
                       (remaining_fields, ))

  def _GetOutput(self, experiment):
    with mock.patch('results_report.HTMLResultsReport.HTML') as standin:
      HTMLResultsReport(experiment).GetReport()
      mod_mock = standin.__mod__
    self.assertEquals(mod_mock.call_count, 1)
    fmt_args = mod_mock.call_args[0][0]
    return self._TupleToTestOutput(fmt_args)

  def testNoSuccessOutput(self):
    output = self._GetOutput(MakeMockExperiment())
    self.assertIn('no result', output.summary_table)
    self.assertEqual(output.charts, '')

  def testSuccessfulOutput(self):
    num_success = 2
    success_keyvals = {'retval': 0, 'a_float': 3.96}
    output = self._GetOutput(_InjectSuccesses(MakeMockExperiment(), num_success,
                                              success_keyvals))

    self.assertNotIn('no result', output.summary_table)
    #self.assertIn(success_keyvals['machine'], output.summary_table)
    self.assertIn('a_float', output.summary_table)
    self.assertIn(str(success_keyvals['a_float']), output.summary_table)
    # The _ in a_float is filtered out when we're generating HTML.
    self.assertIn('afloat', output.charts)


class JSONResultsReportTest(unittest.TestCase):
  """Tests JSONResultsReport."""
  REQUIRED_REPORT_KEYS = ('date', 'time', 'board', 'label', 'chromeos_image',
                          'chromeos_version', 'chrome_version', 'compiler',
                          'test_name', 'pass')

  # JSONResultsReport.GetReport was initially made to write to disk; unless we
  # refactor it, testing is... a bit awkward.
  def _GetResultsFor(self, experiment, results_dir, date=None, time=None):
    """Gets a JSON report, given an experiment and results_dir.

    Returns [filename, result_as_python_datastructures].
    """
    # Linters complain if this isn't populated with precisely two things.
    test_results = [None, None]
    def grab_results(filename, results):
      test_results[0] = filename
      test_results[1] = results
    report = JSONResultsReport(experiment, date=date, time=time)
    report.GetReport(results_dir, write_results=grab_results)
    self.assertNotIn(None, test_results)
    return test_results

  def testJSONReportOutputFileNameInfo(self):
    date, time = '1/1/2001', '01:02:03'
    results_dir = FakePath('results')
    experiment = MakeMockExperiment(compiler='gcc')
    board = experiment.labels[0].board
    out_path, _ = self._GetResultsFor(experiment, results_dir, date, time)

    self.assertTrue(out_path.startswith(results_dir))
    self.assertTrue(out_path.endswith('.json'))
    out_file = out_path[len(results_dir):]

    # This should replace : in time with something else, since : is a path sep.
    # At the moment, it's '.'.
    self.assertIn(time.replace(':', '.'), out_file)
    self.assertIn(date, out_file)
    self.assertIn(board, out_file)
    self.assertIn('gcc', out_file)

    out_path, _ = self._GetResultsFor(MakeMockExperiment(compiler='llvm'),
                                      results_dir, date, time)
    self.assertIn('llvm', out_path)

    # Comments say that if *any* compiler used was LLVM, then LLVM must be in
    # the file name, instead of gcc.
    experiment = MakeMockExperiment(compiler='gcc')
    experiment.labels[len(experiment.labels)//2].compiler = 'llvm'
    out_path, _ = self._GetResultsFor(experiment, results_dir, date, time)
    self.assertIn('llvm', out_path)

  def _CheckRequiredKeys(self, test_output):
    for output in test_output:
      for key in JSONResultsReportTest.REQUIRED_REPORT_KEYS:
        self.assertIn(key, output)

  def testAllFailedJSONReportOutput(self):
    _, results = self._GetResultsFor(MakeMockExperiment(), FakePath('results'))
    self._CheckRequiredKeys(results)
    # Nothing succeeded; we don't send anything more than what's required.
    for result in results:
      self.assertItemsEqual(result.iterkeys(), self.REQUIRED_REPORT_KEYS)

  def testJSONReportOutputWithSuccesses(self):
    success_keyvals = {
        'retval': 0,
        'a_float': '2.3',
        'many_floats': [['1.0', '2.0'], ['3.0']],
        'machine': "i'm a pirate"
    }

    # 2 is arbitrary.
    num_success = 2
    experiment = _InjectSuccesses(MakeMockExperiment(), num_success,
                                  success_keyvals)
    _, results = self._GetResultsFor(experiment, FakePath('results'))
    self._CheckRequiredKeys(results)

    num_passes = num_success * len(experiment.labels)
    non_failures = [r for r in results if r['pass']]
    self.assertEqual(num_passes, len(non_failures))

    # TODO(gbiv): ...Is the 3.0 *actually* meant to be dropped?
    expected_detailed = {'a_float': 2.3, 'many_floats': [1.0, 2.0]}
    for pass_ in non_failures:
      self.assertIn('detailed_results', pass_)
      self.assertDictEqual(expected_detailed, pass_['detailed_results'])
      self.assertIn('machine', pass_)
      self.assertEqual(success_keyvals['machine'], pass_['machine'])


if __name__ == '__main__':
  test_flag.SetTestMode(True)
  unittest.main()
