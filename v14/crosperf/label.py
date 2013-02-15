#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.


from utils.file_utils import FileUtils


class Label(object):

  def __init__(self, name, chromeos_image, chromeos_root):
    self.name = name
    self.chromeos_image = chromeos_image
    self.chromeos_root = chromeos_root
    self.image_checksum = FileUtils().Md5File(chromeos_image)
