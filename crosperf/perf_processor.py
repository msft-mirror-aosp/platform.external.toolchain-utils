#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
import re
from utils import command_executer
from utils import utils


class PerfProcessor(object):
  class PerfResults(object):
    def __init__(self, report, output):
      self.report = report
      self.output = output

  def __init__(self, logger_to_use=None):
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def GeneratePerfResults(self, results_dir, chromeos_root, board):
    perf_location = os.path.join(results_dir,
                                 os.path.basename(results_dir),
                                 "profiling/iteration.1")
    host_perf_location = os.path.join(chromeos_root, "chroot",
                                      perf_location.lstrip("/"))
    report = self._GeneratePerfReport(perf_location, chromeos_root, board)
    output = self._ReadPerfOutput(host_perf_location)
    return PerfProcessor.PerfResults(report, output)

  def ParseStatResults(self, results):
    output = results.output
    result = {}
    p = re.compile("\s*([0-9.]+) +(\S+)")
    for line in output.split("\n"):
      match = p.match(line)
      if match:
        result[match.group(2)] = match.group(1)
    return result

  def _ReadPerfOutput(self, perf_location):
    perf_output_file = os.path.join(perf_location, "perf.out")
    with open(perf_output_file, "rb") as f:
      return f.read()

  def _GeneratePerfReport(self, perf_location, chromeos_root, board):
    perf_data_file = os.path.join(perf_location, "perf.data")
    # Attempt to build a perf report and keep it with the results.
    command = ("/usr/sbin/perf report --symfs=/build/%s"
               " -i %s --stdio | head -n1000" % (board, perf_data_file))
    _, out, _ = self._ce.ChrootRunCommand(chromeos_root,
                                          command, return_output=True)
    return out


class MockPerfProcessor(object):
  def __init__(self):
    pass

  def GeneratePerfReport(self, *args):
    pass

  def ParseStatResults(self, *args):
    return {}
