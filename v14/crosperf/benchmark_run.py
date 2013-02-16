#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import datetime
import os
import re
import threading
import time
import traceback
from results_cache import Result
from utils import logger
from utils import command_executer
from autotest_runner import AutotestRunner
from results_cache import ResultsCache


STATUS_FAILED = "FAILED"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_IMAGING = "IMAGING"
STATUS_RUNNING = "RUNNING"
STATUS_WAITING = "WAITING"
STATUS_PENDING = "PENDING"


class BenchmarkRun(threading.Thread):
  def __init__(self, name, benchmark_name, autotest_name, autotest_args,
               label_name, chromeos_root, chromeos_image, board, iteration,
               cache_conditions, outlier_range, profile_counters, profile_type,
               machine_manager,
               logger_to_use):
    threading.Thread.__init__(self)
    self.name = name
    self._logger = logger_to_use
    self.benchmark_name = benchmark_name
    self.autotest_name = autotest_name
    self.label_name = label_name
    self.chromeos_root = chromeos_root
    self.chromeos_image = os.path.expanduser(chromeos_image)
    self.board = board
    self.iteration = iteration
    self.result = None
    self.terminated = False
    self.retval = None
    self.status = STATUS_PENDING
    self.run_completed = False
    self.outlier_range = outlier_range
    self.profile_counters = profile_counters
    self.profile_type = profile_type
    self.machine_manager = machine_manager
    self.cache = ResultsCache()
    self.autotest_runner = AutotestRunner(self._logger)
    self.machine = None
    self.full_name = self.autotest_name
    self.cache_conditions = cache_conditions
    self.runs_complete = 0
    self.cache_hit = False
    self.failure_reason = ""
    self.autotest_args = "%s %s" % (autotest_args, self._GetExtraAutotestArgs())
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def run(self):
    try:
      # Just use the first machine for running the cached version,
      # without locking it.
      self.cache.Init(self.chromeos_image,
                      self.chromeos_root,
                      self.autotest_name,
                      self.iteration,
                      self.autotest_args,
                      self.machine_manager.GetMachines()[0].name,
                      self.board,
                      self.cache_conditions,
                      self._logger)

      self.result = self.cache.ReadResult()
      self.cache_hit = (self.result is not None)

      if self.result:
        self._logger.LogOutput("%s: Cache hit." % self.name)
        self._logger.LogOutput(self.result.out + "\n" + self.result.err)
      else:
        self._logger.LogOutput("%s: No cache hit." % self.name)
        self.status = STATUS_WAITING
        # Try to acquire a machine now.
        self.machine = self.AcquireMachine()
        self.cache.remote = self.machine.name
        self.result = self.RunTest(self.machine)
        self.cache.StoreResult(self.result)

      if self.terminated:
        return

      if not self.result.retval:
        self.status = STATUS_SUCCEEDED
      else:
        if self.status != STATUS_FAILED:
          self.status = STATUS_FAILED
          self.failure_reason = "Return value of autotest was non-zero."

    except Exception, e:
      self._logger.LogError("Benchmark run: '%s' failed: %s" % (self.name, e))
      traceback.print_exc()
      if self.status != STATUS_FAILED:
        self.status = STATUS_FAILED
        self.failure_reason = str(e)
    finally:
      if self.machine:
        self._logger.LogOutput("Releasing machine: %s" % self.machine.name)
        self.machine_manager.ReleaseMachine(self.machine)
        self._logger.LogOutput("Released machine: %s" % self.machine.name)

  def Terminate(self):
    self.terminated = True
    self.autotest_runner.Terminate()
    if self.status != STATUS_FAILED:
      self.status = STATUS_FAILED
      self.failure_reason = "Thread terminated."

  def AcquireMachine(self):
    while True:
      if self.terminated:
        raise Exception("Thread terminated while trying to acquire machine.")
      machine = self.machine_manager.AcquireMachine(self.chromeos_image)
      if machine:
        self._logger.LogOutput("%s: Machine %s acquired at %s" %
                               (self.name,
                                machine.name,
                                datetime.datetime.now()))
        break
      else:
        sleep_duration = 10
        time.sleep(sleep_duration)
    return machine

  def _GetExtraAutotestArgs(self):
    if self.profile_type:
      if self.profile_type == "record":
        perf_args = "record -a -e %s" % ",".join(self.profile_counters)
      elif self.profile_type == "stat":
        perf_args = "stat -a"
      else:
        raise Exception("profile_type must be either record or stat")
      extra_autotest_args = ["--profiler=custom_perf",
                             ("--profiler_args='perf_options=\"%s\"'" %
                              perf_args)]
      return " ".join(extra_autotest_args)
    else:
      return ""

  def RunTest(self, machine):
    self.status = STATUS_IMAGING
    self.machine_manager.ImageMachine(machine,
                                      self.chromeos_image,
                                      self.board)
    self.status = "%s %s" % (STATUS_RUNNING, self.autotest_name)
    [retval, out, err] = self.autotest_runner.Run(machine.name,
                                                  self.chromeos_root,
                                                  self.board,
                                                  self.autotest_name,
                                                  self.autotest_args)
    self.run_completed = True

    return Result.CreateFromRun(self._logger,
                                self.chromeos_root,
                                self.board,
                                out,
                                err,
                                retval)

  def SetCacheConditions(self, cache_conditions):
    self.cache_conditions = cache_conditions
