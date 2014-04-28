#!/usr/bin/python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from utils import command_executer

class ImageDownloader(object):

  def __init__(self, logger_to_use=None, log_level="verbose"):
    self._logger = logger_to_use
    self.log_level = log_level
    self._ce = command_executer.GetCommandExecuter(self._logger,
                                                   log_level = self.log_level)

  def Run(self, chromeos_root, xbuddy_label):
    # Get the translation of the xbuddy_label into the real Google Storage
    # image name.
    command = ("cd ~/trunk/src/third_party/toolchain-utils/crosperf; "
               "python translate_xbuddy.py '%s'" % xbuddy_label)
    retval, build_id_tuple_str, _ = self._ce.ChrootRunCommand(chromeos_root,
                                                          command, True)
    build_id_tuple = eval(build_id_tuple_str)
    build_id = build_id_tuple[0]

    if self.log_level == "average":
      self._logger.LogOutput ("Preparing to download %s image to local directory." % build_id)

    # Make sure the directory for downloading the image exists.
    download_path = os.path.join(chromeos_root, "chroot/tmp",
                                 build_id)
    image_path = os.path.join(download_path, "chromiumos_test_image.bin")
    if not os.path.exists(download_path):
      command = "mkdir -p %s" % download_path
      self._ce.RunCommand (command)

    # Check to see if the image has already been downloaded.  If not,
    # download the image.
    retval = 0
    if not os.path.exists(image_path):
      command = ("gsutil cp gs://chromeos-image-archive/%s"
                 "/chromiumos_test_image.tar.xz /tmp/%s" % (build_id,
                                                            build_id))

      if self.log_level != "verbose":
        self._logger.LogOutput ("CMD: %s" % command)
      retval = self._ce.ChrootRunCommand(chromeos_root, command)

      # Uncompress and untar the downloaded image.
      command = ("cd /tmp/%s ;unxz chromiumos_test_image.tar.xz; "
                 "tar -xvf chromiumos_test_image.tar" % build_id)
      if self.log_level != "verbose":
        self._logger.LogOutput("CMD: %s" % command)
        print("(Uncompressing and un-tarring may take a couple of minutes..."
              "please be patient.)")
      retval = self._ce.ChrootRunCommand(chromeos_root, command)

    if retval == 0 and self.log_level != "quiet":
      self._logger.LogOutput("Using image from %s." % image_path)

    return retval, image_path
