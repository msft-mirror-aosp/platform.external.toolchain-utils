# Copyright 2011 Google Inc. All Rights Reserved.
"""The class to show the banner."""

from __future__ import print_function

import datetime
import time


class ExperimentStatus(object):
  """The status class."""

  def __init__(self, experiment):
    self.experiment = experiment
    self.num_total = len(self.experiment.benchmark_runs)
    self.completed = 0
    self.new_job_start_time = time.time()
    self.log_level = experiment.log_level

  def _GetProgressBar(self, num_complete, num_total):
    ret = 'Done: %s%%' % int(100.0 * num_complete / num_total)
    bar_length = 50
    done_char = '>'
    undone_char = ' '
    num_complete_chars = bar_length * num_complete / num_total
    num_undone_chars = bar_length - num_complete_chars
    ret += ' [%s%s]' % (num_complete_chars * done_char,
                        num_undone_chars * undone_char)
    return ret

  def GetProgressString(self):
    """Get the elapsed_time, ETA."""
    current_time = time.time()
    if self.experiment.start_time:
      elapsed_time = current_time - self.experiment.start_time
    else:
      elapsed_time = 0
    try:
      if self.completed != self.experiment.num_complete:
        self.completed = self.experiment.num_complete
        self.new_job_start_time = current_time
      time_completed_jobs = (elapsed_time -
                             (current_time - self.new_job_start_time))
      # eta is calculated as:
      #   ETA = (num_jobs_not_yet_started * estimated_time_per_job)
      #          + time_left_for_current_job
      #
      #   where
      #        num_jobs_not_yet_started = (num_total - num_complete - 1)
      #
      #        estimated_time_per_job = time_completed_jobs / num_run_complete
      #
      #        time_left_for_current_job = estimated_time_per_job -
      #                                    time_spent_so_far_on_current_job
      #
      #  The biggest problem with this calculation is its assumption that
      #  all jobs have roughly the same running time (blatantly false!).
      #
      #  ETA can come out negative if the time spent on the current job is
      #  greater than the estimated time per job (e.g. you're running the
      #  first long job, after a series of short jobs).  For now, if that
      #  happens, we set the ETA to "Unknown."
      #
      eta_seconds = (float(self.num_total - self.experiment.num_complete - 1) *
                     time_completed_jobs / self.experiment.num_run_complete +
                     (time_completed_jobs / self.experiment.num_run_complete -
                      (current_time - self.new_job_start_time)))

      eta_seconds = int(eta_seconds)
      if eta_seconds > 0:
        eta = datetime.timedelta(seconds=eta_seconds)
      else:
        eta = 'Unknown'
    except ZeroDivisionError:
      eta = 'Unknown'
    strings = []
    strings.append('Current time: %s Elapsed: %s ETA: %s' %
                   (datetime.datetime.now(),
                    datetime.timedelta(seconds=int(elapsed_time)), eta))
    strings.append(self._GetProgressBar(self.experiment.num_complete,
                                        self.num_total))
    return '\n'.join(strings)

  def GetStatusString(self):
    """Get the status string of all the benchmark_runs."""
    status_bins = {}
    for benchmark_run in self.experiment.benchmark_runs:
      if benchmark_run.timeline.GetLastEvent() not in status_bins:
        status_bins[benchmark_run.timeline.GetLastEvent()] = []
      status_bins[benchmark_run.timeline.GetLastEvent()].append(benchmark_run)

    status_strings = []
    for key, val in status_bins.items():
      if key == 'RUNNING':
        status_strings.append('%s: %s' %
                              (key, self._GetNamesAndIterations(val)))
      else:
        status_strings.append('%s: %s' %
                              (key, self._GetCompactNamesAndIterations(val)))

    thread_status = ''
    thread_status_format = 'Thread Status: \n{}\n'
    if (self.experiment.schedv2() is None and
        self.experiment.log_level == 'verbose'):
      # Add the machine manager status.
      thread_status = thread_status_format.format(
          self.experiment.machine_manager.AsString())
    elif self.experiment.schedv2():
      # In schedv2 mode, we always print out thread status.
      thread_status = thread_status_format.format(self.experiment.schedv2(
      ).threads_status_as_string())

    result = '{}{}'.format(thread_status, '\n'.join(status_strings))

    return result

  def _GetNamesAndIterations(self, benchmark_runs):
    strings = []
    t = time.time()
    for benchmark_run in benchmark_runs:
      t_last = benchmark_run.timeline.GetLastEventTime()
      elapsed = str(datetime.timedelta(seconds=int(t - t_last)))
      strings.append("'{0}' {1}".format(benchmark_run.name, elapsed))
    return ' %s (%s)' % (len(strings), ', '.join(strings))

  def _GetCompactNamesAndIterations(self, benchmark_runs):
    output = ''
    labels = {}
    for benchmark_run in benchmark_runs:
      if benchmark_run.label.name not in labels:
        labels[benchmark_run.label.name] = []

    for label in labels:
      strings = []
      benchmark_iterations = {}
      for benchmark_run in benchmark_runs:
        if benchmark_run.label.name != label:
          continue
        benchmark_name = benchmark_run.benchmark.name
        if benchmark_name not in benchmark_iterations:
          benchmark_iterations[benchmark_name] = []
        benchmark_iterations[benchmark_name].append(benchmark_run.iteration)
      for key, val in benchmark_iterations.items():
        val.sort()
        iterations = ','.join(map(str, val))
        strings.append('{} [{}]'.format(key, iterations))
      output += '  ' + label + ': ' + ', '.join(strings) + '\n'

    return ' %s \n%s' % (len(benchmark_runs), output)
