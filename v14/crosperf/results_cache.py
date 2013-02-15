#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import glob
import hashlib
import os
import pickle
import re
from image_checksummer import ImageChecksummer
from utils import command_executer
from utils import logger

SCRATCH_DIR = "/home/%s/cros_scratch" % getpass.getuser()
PICKLE_FILE = "pickle.txt"


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
  def Init(self, chromeos_image, autotest_name, iteration,
           autotest_args, remote, cache_logger=None):
    self.chromeos_image = chromeos_image
    self.autotest_name = autotest_name
    self.iteration = iteration
    self.autotest_args = autotest_args,
    self.remote = remote
    if cache_logger:
      self._logger = cache_logger
    else:
      self._logger = logger.GetLogger()
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def GetCacheDir(self, remote=None, image_checksum=None):
    if not remote:
      remote = self.remote
    if not image_checksum:
      image_checksum = ImageChecksummer().Checksum(self.chromeos_image)
    ret = ("%s %s %s %s %s %s" %
           (hashlib.md5(self.chromeos_image).hexdigest(),
            self.autotest_name, self.iteration, ",".join(self.autotest_args),
            image_checksum, remote))

    return os.path.join(SCRATCH_DIR, self._ConvertToFilename(ret))

  def Read(self, cache_conditions):
    if CacheConditions.FALSE in cache_conditions:
      self._logger.LogOutput("Cache condition FALSE passed. Not using cache.")
      return None
    # Determine the path of the cached result.
    if not CacheConditions.REMOTES_MATCH in cache_conditions:
      remote = "*"
    else:
      remote = self.remote
    if not CacheConditions.CHECKSUMS_MATCH in cache_conditions:
      checksum = "*"
    else:
      checksum = ImageChecksummer().Checksum(self.chromeos_image)
    cache_dir = self.GetCacheDir(remote, checksum)
    matching_dirs = glob.glob(cache_dir)

    if matching_dirs:
      # Cache file found.
      if len(matching_dirs) > 1:
        self._logger.LogError("Multiple compatible cache files: %s." %
                              " ".join(matching_dirs))
      matching_dir = matching_dirs[0]
      cache_file = os.path.join(matching_dir, PICKLE_FILE)

      self._logger.LogOutput("Trying to read from cache file: %s" % cache_file)

      with open(cache_file, "rb") as f:
        retval = pickle.load(f)
        out = pickle.load(f)
        err = pickle.load(f)

        if (retval == 0 and
            CacheConditions.RUN_SUCCEEDED not in cache_conditions):
          return Result(out, err, retval)

    else:
      if CacheConditions.CACHE_FILE_EXISTS not in cache_conditions:
        # Cache file not found but just return a failure.
        return Result("", "", 1)
      return None

  def Store(self, result):
    checksum = ImageChecksummer().Checksum(self.chromeos_image)
    cache_dir = self.GetCacheDir(checksum)
    cache_file = os.path.join(cache_dir, PICKLE_FILE)
    command = "mkdir -p %s" % os.path.dirname(cache_file)
    ret = self._ce.RunCommand(command)
    assert ret == 0, "Couldn't create cache dir"
    with open(cache_file, "wb") as f:
      pickle.dump(result.retval, f)
      pickle.dump(result.out, f)
      pickle.dump(result.err, f)

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

  def GetCacheDir(self, *args):
    return ""

  def Read(self, *args):
    return None

  def Store(self, *args):
    pass
