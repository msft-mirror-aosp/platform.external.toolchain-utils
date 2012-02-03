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
           logger_to_use):
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.autotest_name = autotest_name
    self.iteration = iteration
    self.autotest_args = autotest_args,
    self.remote = remote
    self.board = board
    self.cache_conditions = cache_conditions
    self._logger = logger_to_use
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def _GetCacheDirForRead(self):
    glob_path = self._FormCacheDir(self._GetCacheKeyList(True))
    matching_dirs = glob.glob(glob_path)

    if matching_dirs:
      # Cache file found.
      if len(matching_dirs) > 1:
        self._logger.LogError("Multiple compatible cache files: %s." %
                              " ".join(matching_dirs))
      return matching_dirs[0]
    else:
      return None

  def _GetCacheDirForWrite(self):
    return self._FormCacheDir(self._GetCacheKeyList(False))

  def _FormCacheDir(self, list_of_strings):
    cache_key = " ".join(list_of_strings)
    cache_dir = self._ConvertToFilename(cache_key)
    cache_path = os.path.join(SCRATCH_DIR, cache_dir)
    return cache_path

  def _GetCacheKeyList(self, read):
    if read and CacheConditions.REMOTES_MATCH not in self.cache_conditions:
      remote = "*"
    else:
      remote = self.remote
    if read and CacheConditions.CHECKSUMS_MATCH not in self.cache_conditions:
      checksum = "*"
    else:
      checksum = ImageChecksummer().Checksum(self.chromeos_image)
    return (hashlib.md5(self.chromeos_image).hexdigest(),
            self.autotest_name, str(self.iteration),
            ",".join(self.autotest_args),
            checksum, remote)

  def ReadResult(self):
    if CacheConditions.FALSE in self.cache_conditions:
      return None
    cache_dir = self._GetCacheDirForRead()

    if not cache_dir:
      return None

    try:
      cache_file = os.path.join(cache_dir, RESULTS_FILE)

      self._logger.LogOutput("Trying to read from cache file: %s" % cache_file)

      with open(cache_file, "rb") as f:
        retval = pickle.load(f)
        out = pickle.load(f)
        err = pickle.load(f)

        if (retval == 0 or
            CacheConditions.RUN_SUCCEEDED not in self.cache_conditions):
          return Result(out, err, retval)

    except Exception, e:
      if CacheConditions.CACHE_FILE_EXISTS not in self.cache_conditions:
        # Cache file not found but just return a failure.
        return Result("", "", 1)
      raise e

  def StoreResult(self, result):
    cache_dir = self._GetCacheDirForWrite()
    cache_file = os.path.join(cache_dir, RESULTS_FILE)
    command = "mkdir -p %s" % cache_dir
    ret = self._ce.RunCommand(command)
    assert ret == 0, "Couldn't create cache dir"
    with open(cache_file, "wb") as f:
      pickle.dump(result.retval, f)
      pickle.dump(result.out, f)
      pickle.dump(result.err, f)

  def StoreAutotestOutput(self, results_dir):
    host_results_dir = os.path.join(self.chromeos_root, "chroot",
                                    results_dir[1:])
    tarball = os.path.join(self._GetCacheDirForWrite(), AUTOTEST_TARBALL)
    command = ("cd %s && tar cjf %s ." % (host_results_dir, tarball))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't store autotest output directory.")

  def ReadAutotestOutput(self, destination):
    cache_dir = self._GetCacheDirForRead()
    tarball = os.path.join(cache_dir, AUTOTEST_TARBALL)
    if not os.path.exists(tarball):
      raise Exception("Cached autotest tarball does not exist at '%s'." %
                      tarball)
    command = ("cd %s && tar xjf %s ." % (destination, tarball))
    ret = self._ce.RunCommand(command)
    if ret:
      raise Exception("Couldn't read autotest output directory.")

  def StorePerfResults(self, perf):
    perf_path = os.path.join(self._GetCacheDirForWrite(), PERF_RESULTS_FILE)
    with open(perf_path, "wb") as f:
      pickle.dump(perf.report, f)
      pickle.dump(perf.output, f)

  def ReadPerfResults(self):
    cache_dir = self._GetCacheDirForRead()
    perf_path = os.path.join(cache_dir, PERF_RESULTS_FILE)
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
