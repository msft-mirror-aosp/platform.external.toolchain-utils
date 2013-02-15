#!/usr/bin/python2.6
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Script to summarize the results of various log files."""

__author__ = "raymes@google.com (Raymes Khoury)"

import sys

class DejaGNUSummarizer:
  def Matches(self, log_file):
    for log_line in log_file:
      if log_line.find("""tests ===""") > -1:
        return True
    return False

  def Summarize(self, log_file):
    result = ""
    pass_statuses = ["PASS", "XPASS"]
    fail_statuses = ["FAIL", "XFAIL", "UNSUPPORTED", "ERROR", "WARNING"]
    for line in log_file:
      line = line.strip().split(":")
      if len(line) > 1 and (line[0] in pass_statuses or
                            line[0] in fail_statuses):
        test_name = (":".join(line[1:])).replace("\t", " ").strip()
        if line[0] in pass_statuses:
          test_result = "pass"
        else:
          test_result = "fail"
        result += "%s\t%s\n" % (test_name, test_result)
    return result

class AutoTestSummarizer:
  def Matches(self, log_file):
    for log_line in log_file:
      if log_line.find("""Installing autotest on""") > -1:
        return True
    return False

  def Summarize(self, log_file):
    result = ""
    pass_statuses = ["PASS"]
    fail_statuses = ["FAIL"]
    for line in log_file:
      line = line.strip().split(" ")
      if len(line) > 1 and (line[-1].strip() in pass_statuses or
                            line[-1].strip() in fail_statuses):
        test_name = (line[0].strip())
        if line[-1].strip() in pass_statuses:
          test_result = "pass"
        else:
          test_result = "fail"
        result += "%s\t%s\n" % (test_name, test_result)
    return result

def Usage():
  print "Usage: %s log_file" % sys.argv[0]
  sys.exit(1)


def SummarizeFile(filename):
  summarizers = [DejaGNUSummarizer(), AutoTestSummarizer()]
  f = open(filename, 'rb')
  for summarizer in summarizers:
    f.seek(0)
    if summarizer.Matches(f):
      f.seek(0)
      result = summarizer.Summarize(f)
      f.close()
      return result
  f.close()
  return None


def Main(argv):
  if len(argv) != 2:
    Usage()
  filename = argv[1]

  print SummarizeFile(filename)

if __name__ == "__main__":
  Main(sys.argv)

