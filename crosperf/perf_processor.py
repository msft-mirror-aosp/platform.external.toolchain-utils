#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

import os
import re

from utils import command_executer


class PerfProcessor(object):
  class PerfResults(object):
    def __init__(self, report, output):
      self.report = report
      self.output = output

  def __init__(self, results_dir, chromeos_root, board, logger_to_use=None):
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)
    self._results_dir = results_dir
    self._chromeos_root = chromeos_root
    self._board = board
    self._perf_relative_dir = os.path.basename(self._results_dir)
    self.host_data_file = self.FindSingleFile(
                            "perf.data", os.path.join(
                              chromeos_root,
                              "chroot",
                              self._results_dir.lstrip("/")))
    self.perf_out = self.FindSingleFile(
                            "perf.out", os.path.join(
                              chromeos_root,
                              "chroot",
                              self._results_dir.lstrip("/")))

  def FindSingleFile(self, name, path):
    find_command = ("find %s -name %s" % (path, name))
    ret, out, err = self._ce.RunCommand(find_command, return_output=True)
    if ret == 0:
      data_files = out.splitlines()
      if len(data_files) == 0:
         # No data file, no report to generate.
         data_file = None
      else:
         assert len(data_files) == 1, "More than 1 perf.out file found"
         data_file = data_files[0]
    return data_file


  def GeneratePerfResults(self):
    perf_location = os.path.join(self._results_dir,
                                 self._perf_relative_dir)
    if self.perf_out != None:
      output = self._ReadPerfOutput()

    if self.host_data_file != None:
      perf_location = os.path.join(self._results_dir,
                                   self._perf_relative_dir)
      host_perf_location = os.path.dirname(self.host_data_file)
      report = self._GeneratePerfReport(perf_location,
                                        self._chromeos_root,
                                        self._board)
    else:
      # lets make perf.report have output of stat...
      report = output
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

  def _ReadPerfOutput(self):
    with open(self.perf_out, "rb") as f:
      return f.read()

  def _GeneratePerfReport(self, perf_location, chromeos_root, board):
    perf_data_file = os.path.join(perf_location, "perf.data")
    # Attempt to build a perf report and keep it with the results.
    command = ("/usr/sbin/perf report --symfs=/build/%s"
               " --vmlinux /build/%s/usr/lib/debug/boot/vmlinux"
               " --kallsyms /build/%s/boot/System.map-*"
               " -i %s --stdio | head -n1000" % (board, board, board,
                                                 perf_data_file))
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
