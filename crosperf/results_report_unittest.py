#!/usr/bin/python2
#
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittest for the results reporter."""

from __future__ import division
from __future__ import print_function

from StringIO import StringIO

import os
import test_flag
import unittest

from benchmark_run import MockBenchmarkRun
from cros_utils import logger
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from machine_manager import MockMachineManager
from results_cache import MockResult
from results_report import JSONResultsReport
from results_report import ParseChromeosImage


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

  @staticmethod
  def _InjectSuccesses(experiment, how_many, keyvals, for_benchmark=0,
                       label=None):
    if label is None:
      # Pick an arbitrary label
      label = experiment.benchmark_runs[0].label
    bench = experiment.benchmarks[for_benchmark]
    num_configs = len(experiment.benchmarks) * len(experiment.labels)
    num_runs = len(experiment.benchmark_runs) // num_configs

    # TODO(gbiv): Centralize the mocking of these, maybe? (It's also done in
    # benchmark_run_unittest)
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

  def testJSONReportOutputWithSuccesses(self):
    success_keyvals = {
        'retval': 0,
        'a_float': '2.3',
        'many_floats': [['1.0', '2.0'], ['3.0']],
        'machine': "i'm a pirate"
    }

    # 2 is arbitrary.
    num_passes = 2
    # copy success_keyvals so we can catch something trying to mutate it.
    experiment = self._InjectSuccesses(MakeMockExperiment(), num_passes,
                                       dict(success_keyvals))
    _, results = self._GetResultsFor(experiment, FakePath('results'))
    self._CheckRequiredKeys(results)
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
