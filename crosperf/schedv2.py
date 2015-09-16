#!/usr/bin/python

# Copyright 2015 Google Inc. All Rights Reserved.

import sys
import test_flag
import traceback

from collections import defaultdict
from machine_image_manager import MachineImageManager
from threading import Lock
from threading import Thread
from utils import logger


class DutWorker(Thread):
    """Working thread for a dut."""

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

        # Test mode flag
        self._in_test_mode = test_flag.GetTestMode()

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
