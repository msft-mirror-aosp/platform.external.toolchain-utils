#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
from utils import command_executer
from utils import utils


class PerfProcessor(object):
  def __init__(self):
    self._ce = command_executer.GetCommandExecuter()

  def GeneratePerfReport(self, results_dir, chromeos_root, board):
    perf_data_file = os.path.join(results_dir,
                                  os.path.basename(results_dir),
                                  "profiling/iteration.1/perf.data")

    # Attempt to build a perf report and keep it with the results.
    command = ("/usr/sbin/perf report --symfs=/build/%s"
               " -i %s --stdio" % (board, perf_data_file))
    _, out, _ = utils.ExecuteCommandInChroot(chromeos_root,
                                             command, return_output=True)
    return out


class MockPerfProcessor(object):
  def __init__(self):
    pass

  def GeneratePerfReport(self, *args):
    pass
