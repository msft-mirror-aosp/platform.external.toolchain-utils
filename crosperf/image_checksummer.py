#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import os
import threading

from utils import logger
from utils.file_utils import FileUtils


class ImageChecksummer(object):
  class PerImageChecksummer(object):
    def __init__(self, label):
      self._lock = threading.Lock()
      self.label = label
      self._checksum = None

    def Checksum(self):
      with self._lock:
        if not self._checksum:
          logger.GetLogger().LogOutput("Acquiring checksum for '%s'." %
                                       self.label.name)
          self._checksum = None
          if self.label.image_type != "local":
            raise Exception("Called Checksum on non-local image!")
          if self.label.chromeos_image:
            if os.path.exists(self.label.chromeos_image):
              self._checksum = FileUtils().Md5File(self.label.chromeos_image)
              logger.GetLogger().LogOutput("Computed checksum is "
                                           ": %s" % self._checksum)
          if not self._checksum:
            if self.label.image_md5sum:
              self._checksum = self.label.image_md5sum
              logger.GetLogger().LogOutput("Checksum in experiment file is "
                                           ": %s" % self._checksum)
            else:
              raise Exception("Checksum computing error.")
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

  def Checksum(self, label):
    if label.image_type != "local":
      raise Exception("Attempt to call Checksum on non-local image.")
    with self._lock:
      if label.name not in self._per_image_checksummers:
        self._per_image_checksummers[label.name] = (ImageChecksummer.
                                                    PerImageChecksummer(label))
      checksummer = self._per_image_checksummers[label.name]

    try:
      return checksummer.Checksum()
    except Exception, e:
      logger.GetLogger().LogError("Could not compute checksum of image in label"
                                  " '%s'."% label.name)
      raise e
