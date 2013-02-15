#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
from utils import utils
from utils import command_executer


class PerfProcessor(object):
  def __init__(self):
    self._ce = command_executer.GetCommandExecuter()

  def StorePerf(self, location, result, chromeos_root, board,
                results_dir, profile_counters):
    host_results_dir = os.path.join(chromeos_root, "chroot", results_dir)
    # Copy results directory to the scratch dir
    if not result.retval and profile_counters:
      tarball = os.path.join(location,
                             os.path.basename(os.path.dirname(results_dir)))
      command = ("cd %s && tar cjf %s.tbz2 ." % (host_results_dir, tarball))
      self._ce.RunCommand(command)
      perf_data_file = os.path.join(results_dir,
                                    os.path.basename(results_dir),
                                    "profiling/iteration.1/perf.data")

      # Attempt to build a perf report and keep it with the results.
      command = ("/usr/sbin/perf report --symfs=/build/%s"
                 " -i %s --stdio" % (board, perf_data_file))
      _, out, _ = utils.ExecuteCommandInChroot(chromeos_root,
                                               command, return_output=True)
      with open(os.path.join(location, "perf.report"), "wb") as f:
        f.write(out)


class MockPerfProcessor(object):
  def __init__(self):
    pass

  def StorePerf(self, *args):
    pass
