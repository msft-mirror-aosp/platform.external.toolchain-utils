#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


from utils import logger
from utils.file_utils import FileUtils


class ImageChecksum(object):
  def __init__(self, filename):
    self._image_checksum = None
    self.filename = filename

  def GetImageChecksum(self):
    if self._image_checksum is None:
      try:
        self._image_checksum = FileUtils().Md5File(self.filename)
      except Exception, e:
        logger.GetLogger().LogError("Could not compute MD5Sum of file '%s'."
                                    % self.filename)
        raise e
    return self._image_checksum

  def __str__(self):
    return self.GetImageChecksum()


class Label(object):
  def __init__(self, name, chromeos_image, chromeos_root):
    self.name = name
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.image_checksum = ImageChecksum(chromeos_image)
