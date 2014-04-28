#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The label of benchamrks."""

import os
from utils.file_utils import FileUtils
from utils import misc


class Label(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, cache_dir, chrome_src=None):

    self.image_type = self._GetImageType(chromeos_image)

    # Expand ~
    chromeos_root = os.path.expanduser(chromeos_root)
    if self.image_type == "local":
      chromeos_image = os.path.expanduser(chromeos_image)

    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.image_args = image_args
    self.cache_dir = cache_dir

    if not chromeos_root:
      if self.image_type == "local":
        chromeos_root = FileUtils().ChromeOSRootFromImage(chromeos_image)
      if not chromeos_root:
        raise Exception("No ChromeOS root given for label '%s' and could not "
                        "determine one from image path: '%s'." %
                        (name, chromeos_image))
    else:
      chromeos_root = FileUtils().CanonicalizeChromeOSRoot(chromeos_root)
      if not chromeos_root:
        raise Exception("Invalid ChromeOS root given for label '%s': '%s'."
                        % (name, chromeos_root))

    self.chromeos_root = chromeos_root
    if not chrome_src:
      self.chrome_src = os.path.join(self.chromeos_root,
          ".cache/distfiles/target/chrome-src-internal")
      if not os.path.exists(self.chrome_src):
        self.chrome_src = os.path.join(self.chromeos_root,
          ".cache/distfiles/target/chrome-src")
    else:
      chromeos_src = misc.CanonicalizePath(chrome_src)
      if not chromeos_src:
        raise Exception("Invalid Chrome src given for label '%s': '%s'."
                        % (name, chrome_src))
      self.chrome_src = chromeos_src

  def _GetImageType(self, chromeos_image):
    image_type = None
    if chromeos_image.find("xbuddy://") < 0:
      image_type = "local"
    elif chromeos_image.find("trybot") >= 0:
      image_type = "trybot"
    else:
      image_type = "official"
    return image_type

class MockLabel(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args, cache_dir, chrome_src=None):
    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.cache_dir = cache_dir
    if not chromeos_root:
      self.chromeos_root = "/tmp/chromeos_root"
    else:
      self.chromeos_root = chromeos_root
    self.image_args = image_args
    self.chrome_src = chrome_src
