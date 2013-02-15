#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
from utils import command_executer


class PerfProcessor(object):
  def __init__(self):
    self._ce = command_executer.GetCommandExecuter()

  def StorePerf(self, location, cache_hit, result, autotest_args,
                chromeos_root, board, results_dir):
    # Copy results directory to the scratch dir
    if (not cache_hit and not result.retval and autotest_args and
        "--profile" in autotest_args):
      tarball = os.path.join(location,
                             os.path.basename(os.path.dirname(results_dir)))
      command = ("cd %s && tar cjf %s.tbz2 ." % (results_dir, tarball))
      self._ce.RunCommand(command)
      perf_data_file = os.path.join(results_dir,
                                    os.path.basename(results_dir),
                                    "profiling/iteration.1/perf.data")

      # Attempt to build a perf report and keep it with the results.
      command = ("cd %s/src/scripts &&"
                 " cros_sdk -- /usr/sbin/perf report --symfs=/build/%s"
                 " -i %s --stdio" % (chromeos_root, board,
                                     perf_data_file))
      _, out, _ = self._ce.RunCommand(command, return_output=True)
      with open(os.path.join(location, "perf.report"), "wb") as f:
        f.write(out)


class MockPerfProcessor(object):
  def __init__(self):
    pass

  def StorePerf(self, *args):
    pass
