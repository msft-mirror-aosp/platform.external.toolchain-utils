#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""The label of benchamrks."""

from utils.file_utils import FileUtils


class Label(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args):
    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    self.image_args = image_args

    if not chromeos_root:
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


class MockLabel(object):
  def __init__(self, name, chromeos_image, chromeos_root, board, remote,
               image_args):
    self.name = name
    self.chromeos_image = chromeos_image
    self.board = board
    self.remote = remote
    if not chromeos_root:
      self.chromeos_root = "/tmp/chromeos_root"
    else:
      self.chromeos_root = chromeos_root
    self.image_args = image_args
