#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import datetime
import time


class ExperimentStatus(object):
  def __init__(self, experiment):
    self.experiment = experiment
    self.num_total = len(self.experiment.benchmark_runs)

  def _GetProgressBar(self, num_complete, num_total):
    ret = "Done: %s%%" % int(100.0 * num_complete / num_total)
    bar_length = 50
    done_char = ">"
    undone_char = " "
    num_complete_chars = bar_length * num_complete / num_total
    num_undone_chars = bar_length - num_complete_chars
    ret += " [%s%s]" % (num_complete_chars * done_char, num_undone_chars *
                        undone_char)
    return ret

  def GetProgressString(self):
    current_time = time.time()
    elapsed_time = current_time - self.experiment.start_time
    try:
      eta_seconds = (float(self.num_total - self.experiment.num_complete) *
                     elapsed_time / self.experiment.num_complete)
      eta_seconds = int(eta_seconds)
      eta = datetime.timedelta(seconds=eta_seconds)
    except ZeroDivisionError:
      eta = "Unknown"
    strings = []
    strings.append("Current time: %s Elapsed: %s ETA: %s" %
                   (datetime.datetime.now(),
                    datetime.timedelta(seconds=int(elapsed_time)),
                    eta))
    strings.append(self._GetProgressBar(self.experiment.num_complete,
                                        self.num_total))
    return "\n".join(strings)

  def GetStatusString(self):
    status_bins = {}
    for benchmark_run in self.experiment.benchmark_runs:
      if benchmark_run.status not in status_bins:
        status_bins[benchmark_run.status] = []
      status_bins[benchmark_run.status].append(benchmark_run)

    status_strings = []
    for key, val in status_bins.items():
      status_strings.append("%s: %s" % (key, self._GetNamesAndIterations(val)))
    result = "Thread Status:\n%s" % "\n".join(status_strings)

    # Add the machine manager status.
    result += self.experiment.machine_manager.AsString() + "\n"

    return result

  def _GetNamesAndIterations(self, benchmark_runs):
    strings = []
    for benchmark_run in benchmark_runs:
      strings.append("%s:%s" % (benchmark_run.name,
                                benchmark_run.iteration))
    return " %s (%s)" % (len(strings), " ".join(strings))
