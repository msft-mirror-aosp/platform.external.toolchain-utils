#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The experiment runner module."""
import getpass
import os
import random
import shutil
import sys
import time
import traceback

import afe_lock_machine
from machine_image_manager import MachineImageManager

from collections import defaultdict
from utils import command_executer
from utils import logger
from utils.email_sender import EmailSender
from utils.file_utils import FileUtils
from threading import Lock
from threading import Thread

import config
from experiment_status import ExperimentStatus
from results_cache import CacheConditions
from results_cache import ResultsCache
from results_report import HTMLResultsReport
from results_report import TextResultsReport
from results_report import JSONResultsReport


class ExperimentRunner(object):
  """ExperimentRunner Class."""

  STATUS_TIME_DELAY = 30
  THREAD_MONITOR_DELAY = 2

  def __init__(self, experiment, json_report, using_schedv2=False, log=None,
               cmd_exec=None):
    self._experiment = experiment
    self.l = log or logger.GetLogger(experiment.log_dir)
    self._ce = cmd_exec or command_executer.GetCommandExecuter(self.l)
    self._terminated = False
    self.json_report = json_report
    self.locked_machines = []
    if experiment.log_level != "verbose":
      self.STATUS_TIME_DELAY = 10

    # Setting this to True will use crosperf sched v2 (feature in progress).
    self._using_schedv2 = using_schedv2

  def _GetMachineList(self):
    """Return a list of all requested machines.

    Create a list of all the requested machines, both global requests and
    label-specific requests, and return the list.
    """
    machines = self._experiment.remote
    for l in self._experiment.labels:
      if l.remote:
        machines += l.remote
    return machines

  def _UpdateMachineList(self, locked_machines):
    """Update machines lists to contain only locked machines.

    Go through all the lists of requested machines, both global and
    label-specific requests, and remove any machine that we were not
    able to lock.

    Args:
      locked_machines: A list of the machines we successfully locked.
    """
    for m in self._experiment.remote:
      if m not in locked_machines:
        self._experiment.remote.remove(m)

    for l in self._experiment.labels:
      for m in l.remote:
        if m not in locked_machines:
          l.remote.remove(m)

  def _LockAllMachines(self, experiment):
    """Attempt to globally lock all of the machines requested for run.

    This method will use the AFE server to globally lock all of the machines
    requested for this crosperf run, to prevent any other crosperf runs from
    being able to update/use the machines while this experiment is running.
    """
    lock_mgr = afe_lock_machine.AFELockManager(
        self._GetMachineList(),
        "",
        experiment.labels[0].chromeos_root,
        None,
        log=self.l,
    )
    for m in lock_mgr.machines:
      if not lock_mgr.MachineIsKnown(m):
        lock_mgr.AddLocalMachine(m)
    machine_states = lock_mgr.GetMachineStates("lock")
    lock_mgr.CheckMachineLocks(machine_states, "lock")
    self.locked_machines = lock_mgr.UpdateMachines(True)
    self._experiment.locked_machines = self.locked_machines
    self._UpdateMachineList(self.locked_machines)
    self._experiment.machine_manager.RemoveNonLockedMachines(
        self.locked_machines)
    if len(self.locked_machines) == 0:
        raise RuntimeError("Unable to lock any machines.")

  def _UnlockAllMachines(self, experiment):
    """Attempt to globally unlock all of the machines requested for run.

    The method will use the AFE server to globally unlock all of the machines
    requested for this crosperf run.
    """
    if not self.locked_machines:
        return

    lock_mgr = afe_lock_machine.AFELockManager(
        self.locked_machines,
        "",
        experiment.labels[0].chromeos_root,
        None,
        log=self.l,
    )
    machine_states = lock_mgr.GetMachineStates("unlock")
    lock_mgr.CheckMachineLocks(machine_states, "unlock")
    lock_mgr.UpdateMachines(False)

  def _ClearCacheEntries(self, experiment):
    for br in experiment.benchmark_runs:
      cache = ResultsCache()
      cache.Init (br.label.chromeos_image, br.label.chromeos_root,
                  br.benchmark.test_name, br.iteration, br.test_args,
                  br.profiler_args, br.machine_manager, br.machine,
                  br.label.board, br.cache_conditions, br._logger, br.log_level,
                  br.label, br.share_cache, br.benchmark.suite,
                  br.benchmark.show_all_results, br.benchmark.run_local)
      cache_dir = cache._GetCacheDirForWrite()
      if os.path.exists(cache_dir):
        self.l.LogOutput("Removing cache dir: %s" % cache_dir)
        shutil.rmtree(cache_dir)

  def _Run(self, experiment):
    try:
      if not experiment.locks_dir:
        self._LockAllMachines(experiment)
      if self._using_schedv2:
        schedv2 = Schedv2(experiment)
        experiment.set_schedv2(schedv2)
      if CacheConditions.FALSE in experiment.cache_conditions:
        self._ClearCacheEntries(experiment)
      status = ExperimentStatus(experiment)
      experiment.Run()
      last_status_time = 0
      last_status_string = ""
      try:
        if experiment.log_level != "verbose":
          self.l.LogStartDots()
        while not experiment.IsComplete():
          if last_status_time + self.STATUS_TIME_DELAY < time.time():
            last_status_time = time.time()
            border = "=============================="
            if experiment.log_level == "verbose":
              self.l.LogOutput(border)
              self.l.LogOutput(status.GetProgressString())
              self.l.LogOutput(status.GetStatusString())
              self.l.LogOutput(border)
            else:
              current_status_string = status.GetStatusString()
              if (current_status_string != last_status_string):
                self.l.LogEndDots()
                self.l.LogOutput(border)
                self.l.LogOutput(current_status_string)
                self.l.LogOutput(border)
                last_status_string = current_status_string
              else:
                self.l.LogAppendDot()
          time.sleep(self.THREAD_MONITOR_DELAY)
      except KeyboardInterrupt:
        self._terminated = True
        self.l.LogError("Ctrl-c pressed. Cleaning up...")
        experiment.Terminate()
    finally:
      if not experiment.locks_dir:
        self._UnlockAllMachines(experiment)

  def _PrintTable(self, experiment):
    self.l.LogOutput(TextResultsReport(experiment).GetReport())

  def _Email(self, experiment):
    # Only email by default if a new run was completed.
    send_mail = False
    for benchmark_run in experiment.benchmark_runs:
      if not benchmark_run.cache_hit:
        send_mail = True
        break
    if (not send_mail and not experiment.email_to
        or config.GetConfig("no_email")):
      return

    label_names = []
    for label in experiment.labels:
      label_names.append(label.name)
    subject = "%s: %s" % (experiment.name, " vs. ".join(label_names))

    text_report = TextResultsReport(experiment, True).GetReport()
    text_report += ("\nResults are stored in %s.\n" %
                    experiment.results_directory)
    text_report = "<pre style='font-size: 13px'>%s</pre>" % text_report
    html_report = HTMLResultsReport(experiment).GetReport()
    attachment = EmailSender.Attachment("report.html", html_report)
    email_to = [getpass.getuser()] + experiment.email_to
    EmailSender().SendEmail(email_to,
                            subject,
                            text_report,
                            attachments=[attachment],
                            msg_type="html")

  def _StoreResults (self, experiment):
    if self._terminated:
      return
    results_directory = experiment.results_directory
    FileUtils().RmDir(results_directory)
    FileUtils().MkDirP(results_directory)
    self.l.LogOutput("Storing experiment file in %s." % results_directory)
    experiment_file_path = os.path.join(results_directory,
                                        "experiment.exp")
    FileUtils().WriteFile(experiment_file_path, experiment.experiment_file)

    self.l.LogOutput("Storing results report in %s." % results_directory)
    results_table_path = os.path.join(results_directory, "results.html")
    report = HTMLResultsReport(experiment).GetReport()
    if self.json_report:
      JSONResultsReport(experiment).GetReport(results_directory)
    FileUtils().WriteFile(results_table_path, report)

    self.l.LogOutput("Storing email message body in %s." % results_directory)
    msg_file_path = os.path.join(results_directory, "msg_body.html")
    text_report = TextResultsReport(experiment, True).GetReport()
    text_report += ("\nResults are stored in %s.\n" %
                    experiment.results_directory)
    msg_body = "<pre style='font-size: 13px'>%s</pre>" % text_report
    FileUtils().WriteFile(msg_file_path, msg_body)

    self.l.LogOutput("Storing results of each benchmark run.")
    for benchmark_run in experiment.benchmark_runs:
      if benchmark_run.result:
        benchmark_run_name = filter(str.isalnum, benchmark_run.name)
        benchmark_run_path = os.path.join(results_directory,
                                          benchmark_run_name)
        benchmark_run.result.CopyResultsTo(benchmark_run_path)
        benchmark_run.result.CleanUp(benchmark_run.benchmark.rm_chroot_tmp)

  def Run(self):
    self._Run(self._experiment)
    self._PrintTable(self._experiment)
    if not self._terminated:
      self._StoreResults(self._experiment)
      self._Email(self._experiment)

class DutWorker(Thread):

    def __init__(self, dut, sched):
        super(DutWorker, self).__init__(name='DutWorker-{}'.format(dut.name))
        self._dut = dut
        self._sched = sched
        self._stat_num_br_run = 0
        self._stat_num_reimage = 0
        self._stat_annotation = ""
        self._l = logger.GetLogger(self._sched._experiment.log_dir)
        self.daemon = True
        self._terminated = False
        self._active_br = None
        # Race condition accessing _active_br between _execute_benchmark_run and
        # _terminate, so lock it up.
        self._active_br_lock = Lock()

    def terminate(self):
        self._terminated = True
        with self._active_br_lock:
            if self._active_br is not None:
                # BenchmarkRun.Terminate() terminates any running testcase via
                # suite_runner.Terminate and updates timeline.
                self._active_br.Terminate()

    def run(self):
        """Do the "run-test->(optionally reimage)->run-test" chore.

        Note - 'br' below means 'benchmark_run'.
        """

        self._setup_dut_label()
        try:
            self._l.LogOutput("{} started.".format(self))
            while not self._terminated:
                br = self._sched.get_benchmark_run(self._dut)
                if br is None:
                    # No br left for this label. Considering reimaging.
                    label = self._sched.allocate_label(self._dut)
                    if label is None:
                        # No br even for other labels. We are done.
                        self._l.LogOutput("ImageManager found no label "
                                          "for dut, stopping working "
                                          "thread {}.".format(self))
                        break
                    if self._reimage(label):
                        # Reimage to run other br fails, dut is doomed, stop
                        # this thread.
                        self._l.LogWarning("Re-image failed, dut "
                                           "in an unstable state, stopping "
                                           "working thread {}.".format(self))
                        break
                else:
                    # Execute the br.
                    self._execute_benchmark_run(br)
        finally:
            self._stat_annotation = "finished"
            # Thread finishes. Notify scheduler that I'm done.
            self._sched.dut_worker_finished(self)

    def _reimage(self, label):
        """Reimage image to label.

        Args:
          label: the label to remimage onto dut.

        Returns:
          0 if successful, otherwise 1.
        """

        # Termination could happen anywhere, check it.
        if self._terminated:
            return 1

        self._l.LogOutput('Reimaging {} using {}'.format(self, label))
        self._stat_num_reimage += 1
        self._stat_annotation = 'reimaging using "{}"'.format(label.name)
        try:
            # Note, only 1 reimage at any given time, this is guaranteed in
            # ImageMachine, so no sync needed below.
            retval = self._sched._experiment.machine_manager.ImageMachine(
                self._dut, label)
            if retval:
                return 1
        except:
            return 1

        self._dut.label = label
        return 0

    def _execute_benchmark_run(self, br):
        """Execute a single benchmark_run.

        Note - this function never throws exceptions.
        """

        # Termination could happen anywhere, check it.
        if self._terminated:
            return

        self._l.LogOutput('{} started working on {}'.format(self, br))
        self._stat_num_br_run += 1
        self._stat_annotation = 'executing {}'.format(br)
        # benchmark_run.run does not throws, but just play it safe here.
        try:
            assert br.owner_thread is None
            br.owner_thread = self
            with self._active_br_lock:
                self._active_br = br
            br.run()
        finally:
            self._sched._experiment.BenchmarkRunFinished(br)
            with self._active_br_lock:
                self._active_br = None

    def _setup_dut_label(self):
        """Try to match dut image with a certain experiment label.

        If such match is found, we just skip doing reimage and jump to execute
        some benchmark_runs.
        """

        checksum_file = "/usr/local/osimage_checksum_file"
        try:
            rv, checksum, _ = command_executer.GetCommandExecuter().\
                CrosRunCommand(
                    "cat " + checksum_file,
                    return_output=True,
                    chromeos_root=self._sched._labels[0].chromeos_root,
                    machine=self._dut.name)
            if rv == 0:
                checksum = checksum.strip()
                for l in self._sched._labels:
                    if l.checksum == checksum:
                        self._l.LogOutput(
                            "Dut '{}' is pre-installed with '{}'".format(
                                self._dut.name, l))
                        self._dut.label = l
                        return
        except:
            traceback.print_exc(file=sys.stdout)
            self._dut.label = None

    def __str__(self):
        return 'DutWorker[dut="{}", label="{}"]'.format(
            self._dut.name, self._dut.label.name if self._dut.label else "None")

    def dut(self):
        return self._dut

    def status_str(self):
      """Report thread status."""

      return ('Worker thread "{}", label="{}", benchmark_run={}, '
              'reimage={}, now {}'.format(
                self._dut.name,
                'None' if self._dut.label is None else self._dut.label.name,
                self._stat_num_br_run,
                self._stat_num_reimage,
                self._stat_annotation))


class Schedv2(object):
    """New scheduler for crosperf."""

    def __init__(self, experiment):
        self._experiment = experiment
        self._l = logger.GetLogger(experiment.log_dir)

        # Create shortcuts to nested data structure. "_duts" points to a list of
        # locked machines. _labels points to a list of all labels.
        self._duts = self._experiment.machine_manager._all_machines
        self._labels = self._experiment.labels

        # Mapping from label to a list of benchmark_runs.
        self._label_brl_map = dict([(l, []) for l in self._labels])
        for br in self._experiment.benchmark_runs:
            assert br.label in self._label_brl_map
            self._label_brl_map[br.label].append(br)

        # Use machine image manager to calculate initial label allocation.
        self._mim = MachineImageManager(self._labels, self._duts)
        self._mim.compute_initial_allocation()

        # Create worker thread, 1 per dut.
        self._active_workers = [DutWorker(dut, self) for dut in self._duts]
        self._finished_workers = []

        # Bookkeeping for synchronization.
        self._workers_lock = Lock()
        self._lock_map = defaultdict(lambda: Lock())

        # Termination flag.
        self._terminated = False

    def run_sched(self):
        """Start all dut worker threads and return immediately."""
        [w.start() for w in self._active_workers]

    def get_benchmark_run(self, dut):
        """Get a benchmark_run (br) object for a certain dut.

        Arguments:
          dut: the dut for which a br is returned.

        Returns:
          A br with its label matching that of the dut. If no such br could be
          found, return None (this usually means a reimage is required for the
          dut).
        """

        # If terminated, stop providing any br.
        if self._terminated:
            return None

        # If dut bears an unrecognized label, return None.
        if dut.label is None:
            return None

        # If br list for the dut's label is empty (that means all brs for this
        # label have been done) , return None.
        with self._lock_on(dut.label):
            brl = self._label_brl_map[dut.label]
            if not brl:
                return None
            # Return the first br.
            return brl.pop(0)

    def allocate_label(self, dut):
        """Allocate a label to a dut.

        The work is delegated to MachineImageManager.

        The dut_worker calling this method is responsible for reimage the dut to
        this label.

        Arguments:
          dut: the new label that is to be reimaged onto the dut.

        Returns:
          The label or None.
        """

        if self._terminated:
            return None

        return self._mim.allocate(dut, self)

    def dut_worker_finished(self, dut_worker):
        """Notify schedv2 that the dut_worker thread finished.

        Arguemnts:
          dut_worker: the thread that is about to end."""

        self._l.LogOutput("{} finished.".format(dut_worker))
        with self._workers_lock:
            self._active_workers.remove(dut_worker)
            self._finished_workers.append(dut_worker)

    def is_complete(self):
      return len(self._active_workers) == 0

    def _lock_on(self, object):
        return self._lock_map[object]

    def terminate(self):
        """Mark flag so we stop providing br/reimages.

        Also terminate each DutWorker, so they refuse to execute br or reimage.
        """

        self._terminated = True
        for dut_worker in self._active_workers:
            dut_worker.terminate()

    def threads_status_as_string(self):
      """Report the dut worker threads status."""

      status = "{} active threads, {} finished threads.\n".format(
        len(self._active_workers), len(self._finished_workers))
      status += "  Active threads:"
      for dw in self._active_workers:
        status += '\n    ' + dw.status_str()
      if self._finished_workers:
        status += "\n  Finished threads:"
        for dw in self._finished_workers:
          status += '\n    ' + dw.status_str()
      return status


class MockExperimentRunner(ExperimentRunner):
  """Mocked ExperimentRunner for testing."""

  def __init__(self, experiment):
    super(MockExperimentRunner, self).__init__(experiment)

  def _Run(self, experiment):
    self.l.LogOutput("Would run the following experiment: '%s'." %
                     experiment.name)

  def _PrintTable(self, experiment):
    self.l.LogOutput("Would print the experiment table.")

  def _Email(self, experiment):
    self.l.LogOutput("Would send result email.")

  def _StoreResults(self, experiment):
    self.l.LogOutput("Would store the results.")
