#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to  compare a baseline results file to a new results file."""

__author__ = "raymes@google.com (Raymes Khoury)"

import sys


PASS = "pass"
FAIL = "fail"
NOT_EXECUTED = "not executed"

def Usage():
  print "Usage: %s baseline_results new_results1 new_results2 ..." % sys.argv[0]
  sys.exit(1)


def parse_results(results_filenames):
  results = []
  for filename in results_filenames:
    results_file = open(filename, 'rb')
    for line in results_file:
      if line.strip() != "":
        results.append(line.strip().split("\t"))
    results_file.close()
  return results

def ParseResults(baseline_file, new_result_files):
  baseline_results = parse_results([baseline_file])
  new_results = parse_results(new_result_files)

  test_status = {}

  for new_result in new_results:
    test_status[new_result[0]] = (new_result[1], NOT_EXECUTED)

  for baseline_result in baseline_results:
    if baseline_result[0] in test_status:
      test_status[baseline_result[0]][0] = baseline_result[1]
    else:
      test_status[baseline_result[0]] = (NOT_EXECUTED, baseline_result[1])

  regressions = []
  for result in test_status.keys():
    if test_status[result][0] != test_status[result][1]:
      regressions.append(result)

  return (baseline_results, new_results, test_status, regressions)

def GenerateResultsStatistics(baseline_file, new_result_files):
  (baseline_results, new_results,
   test_status, regressions) = ParseResults(baseline_file, new_result_files)

  num_tests_executed = len(new_results)
  num_regressions = len(regressions)
  num_passes = 0
  num_failures = 0
  for result in new_results:
    if result[1] == PASS:
      num_passes += 1
    else:
      num_failures += 1

  return (num_tests_executed, num_passes, num_failures, num_regressions)

def GenerateResultsReport(baseline_file, new_result_files):
  (baseline_results, new_results,
   test_status, regressions) = ParseResults(baseline_file, new_result_files)

  num_tests_executed = len(new_results)
  num_regressions = len(regressions)
  num_passes = 0
  num_failures = 0
  for result in new_results:
    if result[1] == PASS:
      num_passes += 1
    else:
      num_failures += 1

  report = ""
  report += "Test summary\n"
  report += "Tests executed: " + str(num_tests_executed) + "\n"
  report += "Passes: " + str(num_passes) + "\n"
  report += "Failures: " + str(num_failures) + "\n"
  report += "Regressions: " + str(num_regressions) + "\n\n"
  report += "-------------------------\n\n"
  report += "Regressions\n"
  report += "Test name\t\tExpected result\t\tActual result\n"
  for regression in regressions:
    report += "%s\t\t%s\t\t%s\n" % (regression, test_status[regression][1],
                              test_status[regression][0])
  report += "\n"
  report += "-------------------------\n\n"
  report += "All tests\n"
  report += "Test name\t\tExpected result\t\tActual result\n"
  for result in test_status.keys():
    report += "%s\t\t%s\t\t%s\n" % (result, test_status[result][1],
                              test_status[result][0])
  return report

def Main(argv):
  if len(argv) < 2:
    Usage()

  print GenerateResultsReport(argv[1], argv[2:])











if __name__ == "__main__":
  Main(sys.argv)
