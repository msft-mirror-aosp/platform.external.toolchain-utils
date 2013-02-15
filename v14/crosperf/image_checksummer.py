#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import traceback
import threading
from utils import logger
from utils.file_utils import FileUtils


class ImageChecksummer(object):
  _instance = None
  _lock = threading.Lock()
  _checksums = {}

  def __new__(cls, *args, **kwargs):
    with cls._lock:
      if not cls._instance:
        cls._instance = super(ImageChecksummer, cls).__new__(cls,
                                                             *args, **kwargs)
      return cls._instance

  def Checksum(self, filename):
    with self._lock:
      if filename in self._checksums:
        return self._checksums[filename]
      try:
#        traceback.print_stack()
        logger.GetLogger().LogOutput("Computing checksum for '%s'." % filename)
        checksum = FileUtils().Md5File(filename)
        self._checksums[filename] = checksum
        return checksum

      except Exception, e:
        logger.GetLogger().LogError("Could not compute checksum of file '%s'."
                                    % filename)
        raise e
