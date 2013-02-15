#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import threading
from utils import logger
from utils.file_utils import FileUtils


class ImageChecksummer(object):
  class PerImageChecksummer(object):
    def __init__(self, filename):
      self._lock = threading.Lock()
      self.filename = filename
      self._checksum = None

    def Checksum(self):
      with self._lock:
        if not self._checksum:
          logger.GetLogger().LogOutput("Computing checksum for '%s'." %
                                       self.filename)
          self._checksum = FileUtils().Md5File(self.filename)
          logger.GetLogger().LogOutput("Checksum is: %s" % self._checksum)
        return self._checksum

  _instance = None
  _lock = threading.Lock()
  _per_image_checksummers = {}

  def __new__(cls, *args, **kwargs):
    with cls._lock:
      if not cls._instance:
        cls._instance = super(ImageChecksummer, cls).__new__(cls,
                                                             *args, **kwargs)
      return cls._instance

  def Checksum(self, filename):
    with self._lock:
      if filename not in self._per_image_checksummers:
        self._per_image_checksummers[filename] = (ImageChecksummer.
                                                  PerImageChecksummer(filename))
      checksummer = self._per_image_checksummers[filename]

    try:
      return checksummer.Checksum()
    except Exception, e:
      logger.GetLogger().LogError("Could not compute checksum of file '%s'."
                                  % filename)
      raise e
