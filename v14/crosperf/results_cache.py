#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import glob
import hashlib
import os
import pickle
import re
from image_checksummer import ImageChecksummer
from perf_processor import PerfProcessor
from utils import command_executer
from utils import logger
from utils import utils

SCRATCH_DIR = "/home/%s/cros_scratch" % getpass.getuser()
RESULTS_FILE = "results.txt"
AUTOTEST_TARBALL = "autotest.tbz2"
PERF_RESULTS_FILE = "perf-results.txt"


class Result(object):
  def __init__(self, out, err, retval):
    self.out = out
    self.err = err
    self.retval = retval


class CacheConditions(object):
  # Cache hit only if the result file exists.
  CACHE_FILE_EXISTS = 0

  # Cache hit if the ip address of the cached result and the new run match.
  REMOTES_MATCH = 1

  # Cache hit if the image checksum of the cached result and the new run match.
  CHECKSUMS_MATCH = 2

  # Cache hit only if the cached result was successful
  RUN_SUCCEEDED = 3

  # Never a cache hit.
  FALSE = 4


class ResultsCache(object):
  def Init(self, chromeos_image, chromeos_root, autotest_name, iteration,
           autotest_args, remote, board, cache_conditions,
           cache_logger=None):
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.autotest_name = autotest_name
    self.iteration = iteration
    self.autotest_args = autotest_args,
    self.remote = remote
    self.board = board
    self.cache_conditions = cache_conditions
    if cache_logger:
      self._logger = cache_logger
    else:
      self._logger = logger.GetLogger()
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def _GetCacheDir(self, read=False):
    if read and CacheConditions.REMOTES_MATCH not in self.cache_conditions:
      remote = "*"
    else:
      remote = self.remote
    if read and CacheConditions.CHECKSUMS_MATCH not in self.cache_conditions:
      checksum = "*"
    else:
      checksum = ImageChecksummer().Checksum(self.chromeos_image)
    ret = ("%s %s %s %s %s %s" %
           (hashlib.md5(self.chromeos_image).hexdigest(),
            self.autotest_name, self.iteration, ",".join(self.autotest_args),
            checksum, remote))

    return os.path.join(SCRATCH_DIR, self._ConvertToFilename(ret))

  def ReadResult(self):
    if CacheConditions.FALSE in self.cache_conditions:
      self._logger.LogOutput("Cache condition FALSE passed. Not using cache.")
      return None
    cache_dir = self._GetCacheDir(True)
    matching_dirs = glob.glob(cache_dir)

    if matching_dirs:
      # Cache file found.
      if len(matching_dirs) > 1:
        self._logger.LogError("Multiple compatible cache files: %s." %
                              " ".join(matching_dirs))
      matching_dir = matching_dirs[0]
      cache_file = os.path.join(matching_dir, RESULTS_FILE)

      self._logger.LogOutput("Trying to read from cache file: %s" % cache_file)

      with open(cache_file, "rb") as f:
        retval = pickle.load(f)
        out = pickle.load(f)
        err = pickle.load(f)

        if (retval == 0 and
            CacheConditions.RUN_SUCCEEDED not in self.cache_conditions):
          return Result(out, err, retval)

    else:
      if CacheConditions.CACHE_FILE_EXISTS not in self.cache_conditions:
        # Cache file not found but just return a failure.
        return Result("", "", 1)
      return None

  def StoreResult(self, result):
    cache_dir = self._GetCacheDir()
    cache_file = os.path.join(cache_dir, RESULTS_FILE)
    command = "mkdir -p %s" % os.path.dirname(cache_file)
    ret = self._ce.RunCommand(command)
    assert ret == 0, "Couldn't create cache dir"
    with open(cache_file, "wb") as f:
      pickle.dump(result.retval, f)
      pickle.dump(result.out, f)
      pickle.dump(result.err, f)

  def StoreAutotestOutput(self, results_dir):
    host_results_dir = os.path.join(self.chromeos_root, "chroot",
                                    results_dir[1:])
    tarball = os.path.join(self._GetCacheDir(), AUTOTEST_TARBALL)
    command = ("cd %s && tar cjf %s ." % (host_results_dir, tarball))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't store autotest output directory.")

  def ReadAutotestOutput(self, destination):
    tarball = os.path.join(self._GetCacheDir(True), AUTOTEST_TARBALL)
    command = ("cd %s && tar xjf %s ." % (destination, tarball))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't read autotest output directory.")

  def StorePerfResults(self, perf):
    perf_path = os.path.join(self._GetCacheDir(), PERF_RESULTS_FILE)
    with open(perf_path, "wb") as f:
      pickle.dump(perf.report, f)
      pickle.dump(perf.output, f)

  def ReadPerfResults(self):
    perf_path = os.path.join(self._GetCacheDir(), PERF_RESULTS_FILE)
    with open(perf_path, "rb") as f:
      report = pickle.load(f)
      output = pickle.load(f)

    return PerfProcessor.PerfResults(report, output)

  def _ConvertToFilename(self, text):
    ret = text
    ret = re.sub("/", "__", ret)
    ret = re.sub(" ", "_", ret)
    ret = re.sub("=", "", ret)
    ret = re.sub("\"", "", ret)
    return ret


class MockResultsCache(object):
  def Init(self, *args):
    pass

  def ReadResult(self):
    return Result("Results placed in /tmp/test", "", 0)

  def StoreResult(self, result):
    pass

  def StoreAutotestOutput(self, results_dir):
    pass

  def ReadAutotestOutput(self, destination):
    pass

  def StorePerfResults(self, perf):
    pass

  def ReadPerfResults(self):
    return PerfProcessor.PerfResults("", "")
