#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import hashlib
import os


class FileUtils(object):
  """Utilities for operations on files."""
  _instance = None
  DRY_RUN = False

  @classmethod
  def Configure(cls, dry_run):
    cls.DRY_RUN = dry_run

  def __new__(cls, *args, **kwargs):
    if not cls._instance:
      if cls.DRY_RUN:
        cls._instance = super(FileUtils, cls).__new__(MockFileUtils, *args,
                                                      **kwargs)
      else:
        cls._instance = super(FileUtils, cls).__new__(cls, *args,
                                                      **kwargs)
    return cls._instance

  def Md5File(self, filename, block_size=2 ** 10):
    md5 = hashlib.md5()

    with open(filename) as f:
      while True:
        data = f.read(block_size)
        if not data:
          break
        md5.update(data)

    return md5.hexdigest()

  def CanonicalizeChromeOSRoot(self, chromeos_root):
    chromeos_root = os.path.expanduser(chromeos_root)
    if os.path.isfile(os.path.join(chromeos_root,
                                   "src/scripts/enter_chroot.sh")):
      return chromeos_root
    else:
      return None

  def ChromeOSRootFromImage(self, chromeos_image):
    chromeos_root = os.path.join(os.path.dirname(chromeos_image),
                                 "../../../../..")
    return self.CanonicalizeChromeOSRoot(chromeos_root)


class MockFileUtils(FileUtils):
  """Mock class for file utilities."""

  def Md5File(self, filename, block_size=2 ** 10):
    return "d41d8cd98f00b204e9800998ecf8427e"

  def CanonicalizeChromeOSRoot(self, chromeos_root):
    return "/tmp/chromeos_root"

  def ChromeOSRootFromImage(self, chromeos_image):
    return "/tmp/chromeos_root"
