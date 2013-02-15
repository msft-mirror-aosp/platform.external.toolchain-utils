#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import datetime
import getpass
import glob
import os
import pickle
import re
import threading
import time
from utils import command_executer
from utils import logger


SCRATCH_DIR = "/home/%s/cros_scratch" % getpass.getuser()
PICKLE_FILE = "pickle.txt"
VERSION = "1"


def ConvertToFilename(text):
  ret = text
  ret = re.sub("/", "__", ret)
  ret = re.sub(" ", "_", ret)
  ret = re.sub("=", "", ret)
  ret = re.sub("\"", "", ret)
  return ret


class BenchmarkRun(threading.Thread):
  def __init__(self, autotest_name, autotest_args, chromeos_root,
               chromeos_image, board, iteration, image_checksum,
               exact_remote, rerun, rerun_if_failed,
               outlier_range, machine_manager):
    self.autotest_name = autotest_name
    self.autotest_args = autotest_args
    self.chromeos_root = chromeos_root
    self.chromeos_image = chromeos_image
    self.board = board
    self.iteration = iteration
    if not image_checksum:
      raise Exception("Checksum shouldn't be None")
    self.image_checksum = image_checksum
    self.results = {}
    threading.Thread.__init__(self)
    self.terminate = False
    self.retval = None
    self.status = "PENDING"
    self.run_completed = False
    self.exact_remote = exact_remote
    self.rerun = rerun
    self.rerun_if_failed = rerun_if_failed
    self.outlier_range = outlier_range
    self.machine_manager = machine_manager

  def MeanExcludingOutliers(self, array, outlier_range):
    """Return the arithmetic mean excluding outliers."""
    mean = sum(array) / len(array)
    array2 = []

    for v in array:
      if mean != 0 and abs(v - mean) / mean < outlier_range:
        array2.append(v)

    if array2:
      return sum(array2) / len(array2)
    else:
      return mean

  def ParseResults(self, output):
    p = re.compile("^-+.*?^-+", re.DOTALL | re.MULTILINE)
    matches = p.findall(output)
    for i in range(len(matches)):
      results = matches[i]
      results_dict = {}
      for line in results.splitlines()[1:-1]:
        mo = re.match("(.*\S)\s+\[\s+(PASSED|FAILED)\s+\]", line)
        if mo:
          results_dict[mo.group(1)] = mo.group(2)
          continue
        mo = re.match("(.*\S)\s+(.*)", line)
        if mo:
          results_dict[mo.group(1)] = mo.group(2)

      break

    return results_dict

  def GitResultsDir(self, output):
    mo = re.search("Results placed in (\S+)", output)
    if mo:
      return mo.group(1)

  def GetCacheHashBase(self):
    ret = ("%s %s %s" %
           (self.image_checksum, self.autotest_name, self.iteration))
    if self.autotest_args:
      ret += " %s" % self.autotest_args
    ret += "-%s" % VERSION
    return ret

  def GetLabel(self):
    ret = "%s %s remote:%s" % (self.chromeos_image, self.autotest_name,
                               self.remote)
    return ret

  def RunCached(self):
    if self.rerun:
      self._logger.LogOutput("rerun set. Not using cached results.")
      return None

    # Determine the path of the cached result.
    base = self.GetCacheHashBase()
    if self.exact_remote:
      if not self.remote:
        return None
      cache_dir_glob = "%s_%s" % (ConvertToFilename(base), self.remote)
    else:
      cache_dir_glob = "%s*" % ConvertToFilename(base)
    cache_path_glob = os.path.join(SCRATCH_DIR, cache_dir_glob)
    matching_dirs = glob.glob(cache_path_glob)

    # Cache file found.
    if matching_dirs:
      matching_dir = matching_dirs[0]
      cache_file = os.path.join(matching_dir, PICKLE_FILE)
      assert os.path.isfile(cache_file)
      self._logger.LogOutput("Trying to read from cache file: %s" % cache_file)
      res = self.ReadFromCache(cache_file)

      if self.rerun_if_failed and self.retval:
        self._logger.LogOutput("rerun_if_failed set and existing test "
                               "failed. Rerunning...")
        return False
      else:
        return res
    else:
      self._logger.LogOutput("Cache miss. AM going to run: %s for: %s" %
                             (self.autotest_name, self.chromeos_image))
      return False

  def ReadFromCache(self, cache_file):
    with open(cache_file, "rb") as f:
      self.retval = pickle.load(f)
      self.out = pickle.load(f)
      self.err = pickle.load(f)
      self._logger.LogOutput(self.out)
      return True
    return False

  def StoreToCache(self):
    base = self.GetCacheHashBase()
    self.cache_dir = os.path.join(SCRATCH_DIR, "%s_%s" % (
        ConvertToFilename(base),
        self.remote))
    cache_file = os.path.join(self.cache_dir, PICKLE_FILE)
    command = "mkdir -p %s" % os.path.dirname(cache_file)
    ret = self._ce.RunCommand(command)
    assert ret == 0, "Couldn't create cache dir"
    with open(cache_file, "wb") as f:
      pickle.dump(self.retval, f)
      pickle.dump(self.out, f)
      pickle.dump(self.err, f)

  def run(self):
    self._logger = logger.Logger(
        os.path.dirname(__file__),
        "%s.%s" % (os.path.basename(__file__),
                   self.name), True)
    self._ce = command_executer.GetCommandExecuter(self._logger)

    self.status = "WAITING"

    cache_hit = self.RunCached()
    if not cache_hit:
      self.RunTest()

    if not self.retval:
      self.status = "SUCCEEDED"
    else:
      self.status = "FAILED"

    self.results = self.ParseResults(self.out)

    self.StorePerf(cache_hit)

    return self.retval

  def StorePerf(self, cache_hit):
    results_dir = self.GitResultsDir(self.out)
    # Copy results directory to the scratch dir
    if (not cache_hit and not self.retval and self.autotest_args and
        "--profile" in self.autotest_args):
      results_dir = os.path.join(self.chromeos_root, "chroot",
                                 results_dir.lstrip("/"))
      tarball = os.path.join(
          self.cache_dir,
          os.path.basename(os.path.dirname(results_dir)))
      command = ("cd %s && tar cjf %s.tbz2 ." % (results_dir, tarball))
      self._ce.RunCommand(command)
      perf_data_file = os.path.join(results_dir,
                                    os.path.basename(results_dir),
                                    "profiling/iteration.1/perf.data")

      # Attempt to build a perf report and keep it with the results.
      command = ("cd %s/src/scripts &&"
                 " cros_sdk -- /usr/sbin/perf report --symfs=/build/%s"
                 " -i %s --stdio" % (self.chromeos_root, self.board,
                                     perf_data_file))
      _, out, _ = self._ce.RunCommand(command, return_output=True)
      with open(os.path.join(self.cache_dir, "perf.report"), "wb") as f:
        f.write(out)

  def AcquireMachine(self):
    while True:
      if self.terminate:
        return None
      machine = self.machine_manager.AcquireMachine(self.image_checksum)
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

  def RunTest(self):
    machine = self.AcquireMachine()
    if not machine:
      return
    try:
      self.remote = machine.name

      if machine.checksum != self.image_checksum:
        self.status = "IMAGING"
        self.retval = self.machine_manager.ImageMachine(machine.name,
                                                        self.chromeos_root,
                                                        self.chromeos_image,
                                                        self.board)
        if self.retval:
          return self.retval
        machine.checksum = self.image_checksum
        machine.image = self.chromeos_image
      self.status = "RUNNING: %s" % self.autotest_name
      [self.retval, self.out, self.err] = self.RunTestOn(machine.name)
      self.run_completed = True

    finally:
      self._logger.LogOutput("Releasing machine: %s" % machine.name)
      self.machine_manager.ReleaseMachine(machine)
      self._logger.LogOutput("Released machine: %s" % machine.name)

    self.StoreToCache()

  def RunTestOn(self, machine_name):
    command = "cd %s/src/scripts" % self.chromeos_root
    options = ""
    if self.board:
      options += " --board=%s" % self.board
    if self.autotest_args:
      options += " %s" % self.autotest_args
    command += ("&& cros_sdk -- ./run_remote_tests.sh --remote=%s %s %s" %
                (machine_name,
                 options,
                 self.autotest_name))
    return self._ce.RunCommand(command, True)
