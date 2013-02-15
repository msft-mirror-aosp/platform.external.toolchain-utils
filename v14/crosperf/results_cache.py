#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import glob
import os
import pickle
import re
from utils import command_executer
from utils import logger

SCRATCH_DIR = "/home/%s/cros_scratch" % getpass.getuser()
PICKLE_FILE = "pickle.txt"


class Result(object):
  def __init__(self, out, err, retval):
    self.out = out
    self.err = err
    self.retval = retval


class ResultsCache(object):
  def Init(self, image_checksum, autotest_name, iteration,
           autotest_args, remote, exact_remote, cache_logger=None):
    self.image_checksum = image_checksum
    self.autotest_name = autotest_name
    self.iteration = iteration,
    self.autotest_args = autotest_args,
    self.remote = remote
    self.exact_remote = exact_remote
    if cache_logger:
      self._logger = cache_logger
    else:
      self._logger = logger.GetLogger()
    self._ce = command_executer.GetCommandExecuter(self._logger)

  def GetCacheDir(self):
    ret = ("%s %s %s" %
           (self.image_checksum, self.autotest_name, self.iteration))
    if self.autotest_args:
      ret += " %s" % self.autotest_args
    if self.exact_remote:
      ret += "_%s" % self.remote
    return os.path.join(SCRATCH_DIR, self._ConvertToFilename(ret))

  def Read(self):
    # Determine the path of the cached result.
    cache_dir = self.GetCacheDir()
    if not self.exact_remote:
      cache_dir += "*"
    matching_dirs = glob.glob(cache_dir)

    # Cache file found.
    if matching_dirs:
      matching_dir = matching_dirs[0]
      cache_file = os.path.join(matching_dir, PICKLE_FILE)
      assert os.path.isfile(cache_file)

      self._logger.LogOutput("Trying to read from cache file: %s" % cache_file)

      with open(cache_file, "rb") as f:
        retval = pickle.load(f)
        out = pickle.load(f)
        err = pickle.load(f)
        return Result(out, err, retval)

      return None

  def Store(self, result):
    cache_dir = self.GetCacheDir()
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

  def GetCacheDir(self):
    return ""

  def Read(self):
    return None

  def Store(self, result):
    pass
